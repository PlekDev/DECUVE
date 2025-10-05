import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import IntVar, messagebox, Listbox
import threading
import time
import random
import configparser

# Groq client import (si no está disponible, se usa fallback mock)
try:
    from groq import Groq  # For Groq API (pip install groq)
except Exception:
    Groq = None

# pylsl imports (si no instalado, la app sigue en modo debug)
try:
    from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_stream
except Exception:
    StreamInfo = StreamOutlet = StreamInlet = resolve_stream = None

# --------- CARGA DE API KEY ----------
# OPCIÓN 1: Poner tu API key directamente aquí (recomendado para testing)
GROQ_API_KEY = ""  # <-- Pon tu API key aquí

# OPCIÓN 2: Leer desde archivo key.ini (comentar OPCIÓN 1 si usas esta)
# try:
#     config = configparser.ConfigParser()
#     config.read("key.ini")
#     GROQ_API_KEY = config["keys"]["key"]
# except Exception as e:
#     print(f"Error reading key.ini: {e}")
#     GROQ_API_KEY = ""

# OPCIÓN 3: Usar variable de entorno (más seguro para producción)
# import os
# GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Validar que tengamos una API key
if not GROQ_API_KEY or len(GROQ_API_KEY) < 10:
    print("⚠️ WARNING: No se encontró una API key válida de Groq")
    print("Por favor configura tu API key en el código (variable GROQ_API_KEY)")
    client = None
else:
    # Inicializa cliente Groq si está disponible
    if Groq is not None:
        try:
            client = Groq(api_key=GROQ_API_KEY)
            print("✓ Cliente Groq inicializado correctamente")
        except Exception as e:
            print(f"❌ Groq client init error: {e}")
            client = None
    else:
        print("⚠️ Módulo 'groq' no está instalado. Usa: pip install groq")
        client = None

# --------- Estado global ----------
conversation_history = []  # historial para API si se necesita
decision_tree = {"root": {"options": [], "next": {}}}
current_mode = "speller"  # "speller" o "graph"
current_node = decision_tree["root"]
breadcrumb_trail = ["Root"]
buttons = []
alphabet = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _.,?!")
is_running = False
debug_mode = True  # empezar en debug (simulación)
unicorn = None  # placeholder

# ---------- Mock Unicorn ----------
class MockUnicorn:
    def connect(self): pass
    def read_eeg(self): return [random.random() for _ in range(8)]
unicorn = MockUnicorn()

# --------- GUI con ttkbootstrap ----------
app = tb.Window(themename="darkly")
app.title("BCI Chat Interface with Groq - Hackathon")
app.geometry("900x720")
app.minsize(900, 600)

# Layout: left = console, right = controls
left_frame = tb.Frame(app)
left_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=8, pady=8)

right_frame = tb.Frame(app, width=360)
right_frame.pack(side=RIGHT, fill=Y, padx=8, pady=8)

# Chat display
chat_display = tb.Text(left_frame, width=60, height=40, font=("Arial", 11), wrap=WORD, insertbackground="white")
chat_display.pack(fill=BOTH, expand=True)
chat_display.tag_configure("user", foreground="#4CAF50")
chat_display.tag_configure("ai", foreground="#BBBBBB")

# Controls on right
tb.Label(right_frame, text="Modo:").pack(anchor="w", pady=(4,0))
mode_var = IntVar(value=0)
tb.Radiobutton(right_frame, text="Speller (teclear letra)", variable=mode_var, value=0, command=lambda: switch_mode()).pack(anchor="w")
tb.Radiobutton(right_frame, text="Graph (sugerencias)", variable=mode_var, value=1, command=lambda: switch_mode()).pack(anchor="w")

debug_var = IntVar(value=1)
tb.Checkbutton(right_frame, text="Debug (simulación clics)", variable=debug_var, command=lambda: toggle_debug()).pack(fill=X, pady=6)

# API Key configuration
api_frame = tb.Labelframe(right_frame, text="Configuración API")
api_frame.pack(fill=X, pady=6)

api_status = tb.Label(api_frame, text="API: No configurada" if not client else "API: ✓ Conectada", 
                      bootstyle=DANGER if not client else SUCCESS)
api_status.pack(pady=4)

def open_api_config():
    api_window = tb.Toplevel(app)
    api_window.title("Configurar API Key de Groq")
    api_window.geometry("500x250")
    
    tb.Label(api_window, text="Ingresa tu API Key de Groq:", font=("Arial", 12)).pack(pady=10)
    
    api_entry = tb.Entry(api_window, width=50, font=("Arial", 10))
    api_entry.pack(pady=10)
    api_entry.insert(0, GROQ_API_KEY if GROQ_API_KEY else "")
    
    tb.Label(api_window, text="Obtén tu API key gratuita en:\nhttps://console.groq.com/keys", 
             bootstyle=SUCCESS, font=("Arial", 9)).pack(pady=5)
    
    def save_api_key():
        global GROQ_API_KEY, client
        new_key = api_entry.get().strip()
        if not new_key or len(new_key) < 10:
            messagebox.showerror("Error", "API key inválida")
            return
        
        GROQ_API_KEY = new_key
        
        # Intentar inicializar cliente
        try:
            if Groq is not None:
                client = Groq(api_key=GROQ_API_KEY)
                api_status.config(text="API: ✓ Conectada", bootstyle=SUCCESS)
                messagebox.showinfo("Éxito", "API Key configurada correctamente")
                api_window.destroy()
            else:
                messagebox.showerror("Error", "Módulo 'groq' no instalado.\nUsa: pip install groq")
        except Exception as e:
            messagebox.showerror("Error", f"Error al conectar con Groq:\n{e}")
    
    tb.Button(api_window, text="Guardar y Conectar", bootstyle=SUCCESS, command=save_api_key).pack(pady=10)
    tb.Button(api_window, text="Cancelar", bootstyle=SECONDARY, command=api_window.destroy).pack()

tb.Button(api_frame, text="Configurar API Key", bootstyle=PRIMARY, command=open_api_config).pack(pady=4)

tb.Label(right_frame, text="Palabra clave / Concepto (keywords separadas por comas):").pack(anchor="w")
prompt_text = tb.Entry(right_frame, width=40, font=("Arial", 12))
prompt_text.pack(pady=6)
prompt_text.bind("<KeyRelease>", lambda e: suggest_auto_completion())

# Auto-completion listbox
suggestion_list = Listbox(right_frame, height=5, font=("Arial", 10), bg="#1E1E1E", fg="white")
suggestion_list.pack(fill=X, pady=2)
suggestion_list.bind("<<ListboxSelect>>", lambda e: select_suggestion(e))
suggestion_list.pack_forget()

# Common suggestions client-side
common_suggestions = [
    "quién","qué","cómo","cuándo","dónde","por qué","AI","cuidados","salud","educación","finanzas",
    "blockchain","criptomonedas","marriage","sexo","adicciones","volcanes","física","biología"
]

# Dynamic area (para el grid / opciones)
dynamic_frame = tb.Frame(right_frame)
dynamic_frame.pack(fill=BOTH, expand=False, pady=8)

# Buttons
control_frame = tb.Frame(right_frame)
control_frame.pack(fill=X, pady=4)
start_button = tb.Button(control_frame, text="Start Interface", bootstyle=SUCCESS, command=lambda: start_interface())
start_button.pack(side=LEFT, padx=4)
submit_button = tb.Button(control_frame, text="Generar Preguntas", bootstyle=INFO, command=lambda: on_generate_questions())
submit_button.pack(side=LEFT, padx=4)
reset_button = tb.Button(control_frame, text="Reset", bootstyle=DANGER, command=lambda: reset_all())
reset_button.pack(side=LEFT, padx=4)

status_label = tb.Label(right_frame, text="Status: Listo (Debug)", anchor=W)
status_label.pack(fill=X, pady=(8,0))

# ----------------- Funciones de UI y flujo -----------------
def update_status(text):
    try:
        status_label.config(text=text)
    except:
        pass

def switch_mode():
    global current_mode, current_node, breadcrumb_trail
    current_mode = "graph" if mode_var.get() == 1 else "speller"
    current_node = decision_tree["root"]
    breadcrumb_trail = ["Root"]
    instruction = "Teclea o usa autocompletado (Speller)" if current_mode == "speller" else "Introduce palabras clave y pulsa 'Generar Preguntas'"
    update_status(f"Modo: {current_mode} – {instruction}")
    create_dynamic_interface()

def toggle_debug():
    global debug_mode
    debug_mode = bool(debug_var.get())
    update_status(f"Debug {'ON' if debug_mode else 'OFF'}")
    create_dynamic_interface()

def create_dynamic_interface():
    # limpia dynamic_frame
    for w in dynamic_frame.winfo_children():
        w.destroy()
    global buttons
    buttons = []
    if current_mode == "speller":
        # un grid pequeño con letras (para debug)
        rows, cols = 5, 8
        for i in range(rows):
            rowframe = tb.Frame(dynamic_frame)
            rowframe.pack()
            for j in range(cols):
                idx = i*cols + j
                if idx < len(alphabet):
                    ch = alphabet[idx]
                    b = tb.Button(rowframe, text=ch, width=3, bootstyle=SECONDARY, command=(lambda c=ch: process_selection(c)) if debug_mode else None)
                    b.pack(side=LEFT, padx=1, pady=1)
                    buttons.append(b)
    else:
        # Mostrar ruta (breadcrumb)
        breadcrumb_label = tb.Label(dynamic_frame, text=f"📍 Ruta: {' > '.join(breadcrumb_trail)}", 
                                   bootstyle=SUCCESS, font=("Arial", 10, "bold"))
        breadcrumb_label.pack(anchor="w", pady=(0,8))
        
        # Obtener opciones del nodo ROOT, no del nodo actual
        root_opts = decision_tree["root"].get("options", [])
        
        if not root_opts:
            tb.Label(dynamic_frame, text="❌ No hay preguntas generadas", 
                     bootstyle=DANGER, font=("Arial", 11, "bold")).pack(anchor="w", pady=4)
            tb.Label(dynamic_frame, text="Introduce palabras clave arriba y\npulsa 'Generar Preguntas'", 
                     bootstyle=SECONDARY, font=("Arial", 10), justify="left").pack(anchor="w", pady=2)
        else:
            # Instrucción
            instruction_text = "Haz clic en una pregunta para seleccionarla"
            tb.Label(dynamic_frame, text=instruction_text, 
                     bootstyle=WARNING, font=("Arial", 9), wraplength=320, justify="left").pack(anchor="w", pady=(0,8))
            
            # Mostrar preguntas del ROOT (las generadas inicialmente)
            for opt in root_opts:
                # Resaltar la pregunta si está seleccionada
                is_selected = (len(breadcrumb_trail) > 1 and breadcrumb_trail[-1] == opt)
                
                b = tb.Button(dynamic_frame, text=f"✓ {opt}" if is_selected else opt, width=45, 
                              bootstyle=SUCCESS if is_selected else PRIMARY,
                              command=(lambda o=opt: process_selection(o)) if debug_mode else None)
                b.pack(pady=2)
                buttons.append(b)
            
            # Separador
            tb.Frame(dynamic_frame, height=2, bootstyle="dark").pack(fill=X, pady=8)
            
            # Mostrar sección de acciones solo si hay algo seleccionado
            if len(breadcrumb_trail) > 1:
                selected_text = breadcrumb_trail[-1]
                
                # Mostrar selección actual
                selection_frame = tb.Frame(dynamic_frame, bootstyle="dark", relief="groove", borderwidth=2)
                selection_frame.pack(fill=X, pady=(0,8), padx=4)
                
                tb.Label(selection_frame, text="Pregunta seleccionada:", 
                         bootstyle=SUCCESS, font=("Arial", 9, "bold")).pack(anchor="w", padx=8, pady=(6,2))
                tb.Label(selection_frame, text=f'"{selected_text}"', 
                         bootstyle="light", font=("Arial", 9), wraplength=300, justify="left").pack(anchor="w", padx=8, pady=(0,6))
                
                # Botón para enviar la selección actual al chat
                send_btn = tb.Button(dynamic_frame, text="✉ Enviar esta pregunta al Chat", 
                                    bootstyle=PRIMARY, command=send_current_question_to_chat)
                send_btn.pack(pady=(0,6), fill=X)
            else:
                # Mensaje si no hay selección
                tb.Label(dynamic_frame, text="👆 Selecciona una pregunta arriba", 
                         bootstyle=SECONDARY, font=("Arial", 9, "italic")).pack(anchor="w", pady=4)
            
            # Botón regresar siempre disponible si no estamos en root
            if len(breadcrumb_trail) > 1:
                back = tb.Button(dynamic_frame, text="⬅ Regresar", bootstyle=SECONDARY, command=go_back)
                back.pack(pady=(3,0), fill=X)
                
    app.update_idletasks()

def go_back():
    global current_node, breadcrumb_trail
    if len(breadcrumb_trail) > 1:
        # Volver al root
        breadcrumb_trail = ["Root"]
        current_node = decision_tree["root"]
        create_dynamic_interface()
        update_status("Regresado al inicio")

def process_selection(selected):
    global current_node, breadcrumb_trail
    # Si estamos en speller, append al entry
    if current_mode == "speller":
        cur = prompt_text.get()
        prompt_text.delete(0, END)
        prompt_text.insert(0, cur + selected)
        return
    # graph mode selection
    if selected == "Custom":
        switch_mode()
        return
    
    # Resetear breadcrumb cuando se selecciona desde el root
    breadcrumb_trail = ["Root", selected]
    
    # Navegar al nodo o crearlo si no existe
    if selected in decision_tree["root"]["next"]:
        current_node = decision_tree["root"]["next"][selected]
    else:
        decision_tree["root"]["next"][selected] = {"options": [], "next": {}}
        current_node = decision_tree["root"]["next"][selected]
    
    # Actualizar interfaz para mostrar la selección
    create_dynamic_interface()
    update_status(f"✓ Pregunta seleccionada")

def send_current_question_to_chat():
    """
    Envía la pregunta/concepto actual (última en breadcrumb) al chat.
    """
    if len(breadcrumb_trail) <= 1:
        messagebox.showinfo("Información", "Primero selecciona una pregunta haciendo clic en ella.")
        return
    
    # Tomar la última selección del breadcrumb como la pregunta
    current_question = breadcrumb_trail[-1]
    send_selected_question_to_chat(current_question)

def send_selected_question_to_chat(question):
    """
    Envía una pregunta específica al chat.
    """
    # Validar que tengamos API
    if client is None:
        response = messagebox.askyesno(
            "API No Configurada",
            "No hay una API key de Groq configurada.\n\n"
            "¿Deseas configurarla ahora para obtener respuestas reales?\n\n"
            "(Si seleccionas 'No', se usará una respuesta simulada)"
        )
        if response:
            open_api_config()
            return
    
    # Mostrar en el chat display
    chat_display.tag_configure("user", foreground="#4CAF50")
    chat_display.tag_configure("ai", foreground="#BBBBBB")
    chat_display.insert(END, f"You: {question}\n", "user")
    chat_display.see(END)
    
    # Enviar a la API en un thread separado
    threading.Thread(target=send_question_thread, args=(question,), daemon=True).start()

def send_question_thread(question):
    """
    Thread para enviar la pregunta al chat API y mostrar la respuesta.
    """
    update_status("⏳ Enviando pregunta a Groq...")
    response = send_to_chat_api(question)
    
    # Actualizar UI desde el hilo principal
    def update_chat():
        chat_display.tag_configure("ai", foreground="#BBBBBB")
        chat_display.insert(END, f"\n{'='*60}\n\n", "ai")
        chat_display.see(END)
        update_status("✓ Respuesta recibida. Puedes hacer otra pregunta.")
    
    app.after(0, update_chat)

# ----------------- Generación de preguntas (IA o fallback) -----------------
def on_generate_questions():
    """
    Acción cuando el usuario pulsa 'Generar Preguntas': tomar las palabras clave
    y pedir a la IA preguntas básicas. Acepta múltiples keywords separadas por comas.
    """
    # Validar que tengamos API key configurada
    if client is None:
        response = messagebox.askyesno(
            "API No Configurada",
            "No hay una API key de Groq configurada.\n\n"
            "¿Deseas configurarla ahora?\n\n"
            "(Si seleccionas 'No', se usarán preguntas de ejemplo)"
        )
        if response:
            open_api_config()
            return
    
    raw = prompt_text.get().strip()
    if not raw:
        messagebox.showwarning("Atención", "Introduce al menos una palabra clave o frase corta.")
        return
    # Normalizar y extraer keywords separadas por comas
    keywords = [k.strip() for k in raw.replace(";", ",").split(",") if k.strip()]
    if not keywords:
        messagebox.showwarning("Atención", "Introduce al menos una palabra clave o frase corta.")
        return
    
    # DESHABILITAR BOTÓN
    submit_button.config(state="disabled")
    update_status("Generando preguntas...")
    
    # Blend all keywords into a single topic string
    blended = ", ".join(keywords)
    threading.Thread(target=generate_concepts_thread, args=(blended,), daemon=True).start()

def generate_concepts_thread(blended_keywords):
    update_status("Generando conceptos relacionados...")
    try:
        concepts = generate_concepts_from_keywords(blended_keywords)
    except Exception as e:
        print("Error generando conceptos:", e)
        concepts = fallback_generate_concepts(blended_keywords)
    # Ir directamente a generar preguntas sin mostrar selección de conceptos
    app.after(0, lambda: generate_initial_questions_direct(blended_keywords))

def generate_initial_questions_thread(keyword):
    """
    Genera preguntas iniciales a partir de la cadena combinada de keywords.
    Llena decision_tree root con las preguntas resultantes.
    """
    update_status("Generando preguntas... (IA)")
    try:
        suggestions = generate_questions_from_keyword(keyword, context="initial")
    except Exception as e:
        print(f"Error generando preguntas: {e}")
        suggestions = fallback_generate_questions(keyword)
    
    # Poblamos el decision_tree root con opciones
    decision_tree["root"]["options"] = suggestions
    decision_tree["root"]["next"] = {opt: {"options": [], "next": {}} for opt in suggestions}
    
    # Usar app.after para actualizar UI desde el thread principal
    app.after(0, lambda: finish_question_generation(keyword))

def generate_initial_questions_direct(keyword):
    """
    Versión que se ejecuta directamente desde el hilo principal.
    """
    threading.Thread(target=generate_initial_questions_thread, args=(keyword,), daemon=True).start()

def finish_question_generation(keyword):
    """
    Finaliza la generación de preguntas y actualiza la UI.
    Debe ejecutarse en el hilo principal de Tkinter.
    """
    global current_node, breadcrumb_trail, current_mode
    
    # Reiniciar navegación
    current_node = decision_tree["root"]
    breadcrumb_trail = ["Root"]
    
    # Cambiar a modo graph para mostrar opciones
    current_mode = "graph"
    mode_var.set(1)
    
    # REHABILITAR BOTÓN
    submit_button.config(state="normal")
    
    update_status(f"Preguntas generadas para '{keyword}'. Elige una.")
    create_dynamic_interface()

def generate_more_questions():
    """
    Genera preguntas adicionales basadas en la última selección (breadcrumb last).
    Si no hay selección, se usa la última opción seleccionada en breadcrumb.
    """
    if len(breadcrumb_trail) <= 1:
        messagebox.showinfo("Información", "Primero selecciona una pregunta haciendo clic en ella.\nLuego podrás generar preguntas relacionadas.")
        return
    last = breadcrumb_trail[-1]
    
    # DESHABILITAR BOTÓN mientras procesa
    submit_button.config(state="disabled")
    
    update_status(f"Generando más preguntas basadas en: {last[:30]}...")
    threading.Thread(target=generate_more_questions_thread, args=(last,), daemon=True).start()

def generate_more_questions_thread(selected_option):
    try:
        suggestions = generate_questions_from_keyword(selected_option, context="expand")
    except Exception as e:
        print(f"Error generando más preguntas: {e}")
        suggestions = fallback_generate_more(selected_option)
    # Añadir a current_node en decision_tree
    node = decision_tree["root"]
    for step in breadcrumb_trail[1:]:
        node = node["next"].get(step, node)
    node_options = node.get("options", [])
    for s in suggestions:
        if s not in node_options:
            node_options.append(s)
            node["next"].setdefault(s, {"options": [], "next": {}})
    node["options"] = node_options
    
    # Actualizar UI desde el hilo principal
    app.after(0, lambda: finish_more_questions())

def finish_more_questions():
    """
    Finaliza la generación de más preguntas y actualiza la UI.
    """
    # REHABILITAR BOTÓN
    submit_button.config(state="normal")
    
    update_status("Más preguntas generadas. Revisa las opciones.")
    create_dynamic_interface()

# ---------- Llamadas a Groq (o fallback local) ----------
def generate_concepts_from_keywords(keywords):
    """
    Genera 5–8 conceptos o temas relacionados con múltiples palabras clave.
    Devuelve una lista de strings.
    """
    if client is not None:
        try:
            system_msg = "Eres un asistente que genera conceptos o temas relacionados con una lista de palabras clave. Devuelve solo una lista corta, sin numerar ni explicaciones, en español."
            user_msg = f"Palabras clave: {keywords}. Devuelve entre 5 y 8 temas o conceptos relacionados, separados por saltos de línea."
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.5,
                max_tokens=150,
                stream=False
            )
            content = ""
            try:
                content = resp.choices[0].message.content
            except Exception:
                content = getattr(resp.choices[0], "text", "") or str(resp)
            lines = [l.strip("-. \n\t") for l in content.splitlines() if len(l.strip()) > 2]
            return lines[:8] if lines else fallback_generate_concepts(keywords)
        except Exception as e:
            print("Groq concept generation error:", e)
    return fallback_generate_concepts(keywords)

def fallback_generate_concepts(keywords):
    kws = [k.strip().capitalize() for k in keywords.split(",")][:3]
    base_concepts = []
    for k in kws:
        base_concepts += [
            f"Historia de {k}",
            f"Tecnología en {k}",
            f"Impacto social de {k}",
            f"Problemas comunes en {k}",
            f"Soluciones modernas sobre {k}"
        ]
    # deduplicate while preserving order
    seen = set()
    out = []
    for c in base_concepts:
        if c not in seen:
            out.append(c)
            seen.add(c)
    return out[:8]

def generate_questions_from_keyword(keyword, context="initial"):
    """
    Llama a Groq (si está disponible) para generar preguntas cortas.
    context: "initial" (desde palabra/frases mezcladas) o "expand" (generar variaciones)
    Retorna lista de strings (preguntas).
    """
    if context == "initial":
        system_msg = "Eres un asistente que genera preguntas cortas y útiles en español a partir de palabras clave o frases. Incluye preguntas tipo: qué, cómo, cuándo, dónde, por qué y 2-3 preguntas conceptuales relacionadas. Devuelve solo la lista, sin explicaciones largas."
        user_msg = f"Temas: {keyword}. Genera 6 preguntas cortas (máx. 10 palabras cada una) en español que combinen las ideas."
    else:
        system_msg = "Eres un asistente que genera variaciones y preguntas de seguimiento concisas en español a partir de una pregunta o tema corto."
        user_msg = f"Tema o pregunta: {keyword}. Genera 5 variaciones / preguntas de seguimiento cortas que profundicen el tema."

    if client is not None:
        try:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.6,
                max_tokens=200,
                stream=False
            )
            content = ""
            try:
                content = resp.choices[0].message.content
            except Exception:
                content = getattr(resp.choices[0], "text", "") or str(resp)
            lines = [l.strip("-. \n\t") for l in content.splitlines() if l.strip()]
            questions = []
            for l in lines:
                if len(questions) >= 8:
                    break
                if len(l) > 3:
                    questions.append(l)
            if not questions:
                raise ValueError("No se obtuvieron preguntas de la API.")
            return questions[:8]
        except Exception as e:
            print(f"Groq API error: {e}")
    return fallback_generate_questions(keyword) if context == "initial" else fallback_generate_more(keyword)

def fallback_generate_questions(keyword):
    basic = [
        f"¿Qué es {keyword}?",
        f"¿Cómo funciona {keyword}?",
        f"¿Cuándo se aplica {keyword}?",
        f"¿Dónde se observa {keyword}?",
        f"¿Por qué es relevante {keyword}?"
    ]
    conceptual = [
        f"Ejemplos comunes de {keyword}",
        f"Beneficios y riesgos de {keyword}"
    ]
    suggestions = basic + conceptual
    return suggestions[:7]

def fallback_generate_more(selected_option):
    return [
        f"Explica más sobre {selected_option}",
        f"Problemas comunes relacionados con {selected_option}",
        f"Cómo medir el impacto de {selected_option}",
        f"Recomendaciones prácticas sobre {selected_option}",
        f"Casos de uso de {selected_option}"
    ]

# ----------------- Concept selection UI (SIMPLIFICADA) -----------------
def show_concept_selection(concepts, keywords):
    """
    FUNCIÓN REMOVIDA - Ahora se generan preguntas directamente
    """
    pass

# ----------------- Autocompletado client-side -----------------
def suggest_auto_completion(event=None):
    text = prompt_text.get().strip().lower()
    if not text:
        suggestion_list.pack_forget()
        return
    matches = [s for s in common_suggestions if s.lower().startswith(text)]
    suggestion_list.delete(0, END)
    for m in matches[:8]:
        suggestion_list.insert(END, m)
    if matches:
        suggestion_list.pack(fill=X, pady=2)
    else:
        suggestion_list.pack_forget()

def select_suggestion(event):
    if suggestion_list.curselection():
        sel = suggestion_list.get(suggestion_list.curselection())
        prompt_text.delete(0, END)
        prompt_text.insert(0, sel)
        suggestion_list.pack_forget()

# ----------------- Interface runtime (unicorn / LSL) -----------------
def start_interface():
    global is_running
    if is_running:
        update_status("La interfaz ya está corriendo.")
        return
    is_running = True
    t = threading.Thread(target=run_interface, daemon=True)
    t.start()
    update_status("Interfaz iniciada.")

def stop_interface():
    global is_running
    is_running = False
    update_status("Interfaz detenida.")

def run_interface():
    try:
        unicorn.connect()
        update_status("EEG conectado (o mock) - esperando estímulos")
    except Exception:
        update_status("Fallo al conectar EEG, usando modo simulación")
    outlet = None
    if StreamInfo is not None:
        try:
            info = StreamInfo('BCIInterface', 'Markers', 1, 0, 'string', 'bci_marker')
            outlet = StreamOutlet(info)
        except Exception as e:
            print("LSL outlet error:", e)
    try:
        while is_running:
            if debug_mode:
                time.sleep(1.2)
                if buttons:
                    idx = random.randint(0, len(buttons)-1)
                    try:
                        btn = buttons[idx]
                        label = btn.cget("text")
                        process_selection(label)
                    except Exception as e:
                        print("Simulación click error:", e)
            else:
                try:
                    signal = unicorn.read_eeg()
                    sel = detect_p300(signal)
                    if sel:
                        if outlet:
                            outlet.push_sample([sel])
                        process_selection(sel)
                except Exception as e:
                    print("Error lectura EEG:", e)
                time.sleep(0.1)
    except Exception as e:
        print("Error run_interface:", e)
    update_status("Interfaz finalizada.")

def detect_p300(signal):
    if current_mode == "speller":
        return random.choice(alphabet)
    else:
        opts = current_node.get("options", [])
        if opts:
            return random.choice(opts)
    return None

# ----------------- Chat API envio directo (cuando quieras enviar prompt) -----------------
def send_to_chat_api(prompt):
    global conversation_history
    conversation_history.append({"role": "user", "content": prompt + " Instrucción: Responde breve y en el idioma del prompt."})
    full_response = ""
    if client is None:
        full_response = f"(Respuesta simulada para '{prompt}')"
        conversation_history.append({"role": "assistant", "content": full_response})
        return full_response
    try:
        try:
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=conversation_history,
                stream=True,
                temperature=0.7,
                max_tokens=500
            )
            for chunk in stream:
                try:
                    piece = chunk.choices[0].delta.content
                except Exception:
                    piece = getattr(chunk.choices[0].delta, "content", "")
                if piece:
                    full_response += piece
                    chat_display.tag_configure("ai", foreground="#BBBBBB")
                    chat_display.insert(END, piece, "ai")
                    chat_display.see(END)
                    app.update()
        except Exception:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=conversation_history,
                stream=False,
                temperature=0.7,
                max_tokens=500
            )
            try:
                full_response = resp.choices[0].message.content
            except Exception:
                full_response = getattr(resp.choices[0], "text", str(resp))
    except Exception as e:
        full_response = f"Error: {e}"
        messagebox.showerror("API Error", f"Fallo al conectar con Groq: {e}")
        update_status("Status: API Error")
    conversation_history.append({"role": "assistant", "content": full_response})
    return full_response

# ----------------- Reset -----------------
def reset_all():
    global conversation_history, decision_tree, current_node, breadcrumb_trail, current_mode
    conversation_history = []
    decision_tree = {"root": {"options": [], "next": {}}}
    current_node = decision_tree["root"]
    breadcrumb_trail = ["Root"]
    current_mode = "speller"
    mode_var.set(0)
    prompt_text.delete(0, END)
    chat_display.delete("1.0", END)
    update_status("Reset completado.")
    create_dynamic_interface()

# ---------- Inicio UI ----------
create_dynamic_interface()

# Ejecutar mainloop
try:
    app.mainloop()
except Exception as e:
    print("Error mainloop:", e)