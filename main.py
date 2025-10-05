import tkinter as tk
from tkinter import ttk, scrolledtext, IntVar, messagebox, Listbox
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
try:
    config = configparser.ConfigParser()
    config.read("key.ini")
    api_key = config["keys"]["key"]
except Exception as e:
    print(f"Error reading key.ini: {e}")
    api_key = ""

# Inicializa cliente Groq si está disponible
if Groq is not None:
    try:
        client = Groq(api_key=api_key)
    except Exception as e:
        print(f"Groq client init error: {e}")
        client = None
else:
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

# --------- GUI ----------
root = tk.Tk()
root.title("BCI Chat Interface with Groq - Hackathon")
root.geometry("900x720")
root.configure(bg="#2E2E2E")

style = ttk.Style()
try:
    style.theme_use("clam")
    style.configure("TButton", font=("Arial", 11, "bold"), padding=6)
    style.configure("TLabel", font=("Arial", 12), background="#2E2E2E", foreground="white")
    style.configure("TRadiobutton", font=("Arial", 11), background="#2E2E2E", foreground="white")
    style.configure("TCheckbutton", font=("Arial", 11), background="#2E2E2E", foreground="white")
    style.configure("TScrollbar", background="#2E2E2E", troughcolor="#1E1E1E", arrowcolor="white")
except Exception as e:
    print(f"Style setup error: {e}")

# Layout: left = console, right = controls
left_frame = tk.Frame(root, bg="#2E2E2E")
left_frame.pack(side="left", fill="both", expand=True, padx=8, pady=8)

right_frame = tk.Frame(root, width=360, bg="#2E2E2E")
right_frame.pack(side="right", fill="y", padx=8, pady=8)

# Chat display
chat_display = scrolledtext.ScrolledText(left_frame, width=60, height=40, font=("Arial", 11), bg="#111111", fg="white", insertbackground="white")
chat_display.pack(fill="both", expand=True)

# Controls on right
ttk.Label(right_frame, text="Modo:").pack(anchor="w", pady=(4,0))
mode_var = IntVar(value=0)
ttk.Radiobutton(right_frame, text="Speller (teclear letra)", variable=mode_var, value=0, command=lambda: switch_mode()).pack(anchor="w")
ttk.Radiobutton(right_frame, text="Graph (sugerencias)", variable=mode_var, value=1, command=lambda: switch_mode()).pack(anchor="w")

debug_var = IntVar(value=1)
ttk.Checkbutton(right_frame, text="Debug (simulación clics)", variable=debug_var, command=lambda: toggle_debug()).pack(fill="x", pady=6)

ttk.Label(right_frame, text="Palabra clave / Concepto (keywords separadas por comas):").pack(anchor="w")
prompt_text = ttk.Entry(right_frame, width=40, font=("Arial", 12))
prompt_text.pack(pady=6)
prompt_text.bind("<KeyRelease>", lambda e: suggest_auto_completion())

# Auto-completion listbox
suggestion_list = Listbox(right_frame, height=5, font=("Arial", 10), bg="#1E1E1E", fg="white")
suggestion_list.pack(fill="x", pady=2)
suggestion_list.bind("<<ListboxSelect>>", lambda e: select_suggestion(e))
suggestion_list.pack_forget()

# Common suggestions client-side (mejoradas)
common_suggestions = [
    "quién","qué","cómo","cuándo","dónde","por qué","AI","cuidados","salud","educación","finanzas",
    "blockchain","criptomonedas","marriage","sexo","adicciones","volcanes","física","biología"
]

# Dynamic area (para el grid / opciones)
dynamic_frame = tk.Frame(right_frame, bg="#2E2E2E")
dynamic_frame.pack(fill="both", expand=False, pady=8)

# Buttons
control_frame = tk.Frame(right_frame, bg="#2E2E2E")
control_frame.pack(fill="x", pady=4)
start_button = ttk.Button(control_frame, text="Start Interface", command=lambda: start_interface())
start_button.pack(side="left", padx=4)
submit_button = ttk.Button(control_frame, text="Generar Preguntas", command=lambda: on_generate_questions())
submit_button.pack(side="left", padx=4)
reset_button = ttk.Button(control_frame, text="Reset", command=lambda: reset_all())
reset_button.pack(side="left", padx=4)

status_label = ttk.Label(right_frame, text="Status: Listo (Debug)", style="TLabel", anchor="w")
status_label.pack(fill="x", pady=(8,0))

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
    update_status(f"Modo: {current_mode} — {instruction}")
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
            rowframe = tk.Frame(dynamic_frame, bg="#2E2E2E")
            rowframe.pack()
            for j in range(cols):
                idx = i*cols + j
                if idx < len(alphabet):
                    ch = alphabet[idx]
                    b = ttk.Button(rowframe, text=ch, width=3, command=(lambda c=ch: process_selection(c)) if debug_mode else None)
                    b.pack(side="left", padx=1, pady=1)
                    buttons.append(b)
    else:
        # Mostrar ruta (breadcrumb)
        tk.Label(dynamic_frame, text=f"Ruta: {' > '.join(breadcrumb_trail)}", bg="#2E2E2E", fg="white", font=("Arial", 10)).pack(anchor="w", pady=(0,6))
        # Mostrar opciones del nodo actual
        opts = current_node.get("options", [])
        if not opts:
            tk.Label(dynamic_frame, text="No hay preguntas generadas. Introduce palabras clave y pulsa 'Generar Preguntas'.", bg="#2E2E2E", fg="#BBBBBB", wraplength=320, justify="left").pack(anchor="w")
        else:
            for opt in opts:
                b = ttk.Button(dynamic_frame, text=opt, width=40, command=(lambda o=opt: process_selection(o)) if debug_mode else None)
                b.pack(pady=3)
                buttons.append(b)
            # Continue / Back
            cont = ttk.Button(dynamic_frame, text="Continuar (Generar más a partir de la selección)", command=generate_more_questions)
            cont.pack(pady=(8,3))
            if len(breadcrumb_trail) > 1:
                back = ttk.Button(dynamic_frame, text="Regresar", command=go_back)
                back.pack(pady=(0,3))
    root.update_idletasks()

def go_back():
    global current_node, breadcrumb_trail
    if len(breadcrumb_trail) > 1:
        breadcrumb_trail.pop()
        # reconstruir current_node desde root
        current_node = decision_tree["root"]
        for step in breadcrumb_trail[1:]:
            current_node = current_node["next"].get(step, decision_tree["root"])
        create_dynamic_interface()

def process_selection(selected):
    global current_node, breadcrumb_trail
    # Si estamos en speller, append al entry
    if current_mode == "speller":
        cur = prompt_text.get()
        prompt_text.delete(0, tk.END)
        prompt_text.insert(0, cur + selected)
        return
    # graph mode selection
    if selected == "Custom":
        switch_mode()
        return
    # si la selección existe en next, navega
    if "next" in current_node and selected in current_node["next"]:
        current_node = current_node["next"][selected]
        breadcrumb_trail.append(selected)
    else:
        # Crear nuevo nodo para la selección si no existe
        current_node["next"].setdefault(selected, {"options": [], "next": {}})
        current_node = current_node["next"][selected]
        breadcrumb_trail.append(selected)
    # Si el nodo tiene un prompt (pregunta final), rellenarlo en la entrada
    if "prompt" in current_node:
        # Get the final prompt
        current_prompt = current_node["prompt"]

        # Display and send to the chat AI
        status_label.config(text="Status: Sending to Groq...")
        chat_display.tag_configure("user", foreground="#4CAF50")
        chat_display.tag_configure("ai", foreground="#BBBBBB")
        chat_display.insert(tk.END, f"You: {current_prompt}\n", "user")
        response = send_to_chat_api(current_prompt)
        chat_display.insert(tk.END, f"AI: {response}\n\n", "ai")
        chat_display.see(tk.END)

        # Reset to root after sending
        current_node = decision_tree["root"]
        breadcrumb_trail = ["Root"]
        create_dynamic_interface()
        status_label.config(text="Status: Ready")
        return
    create_dynamic_interface()

# ----------------- Generación de preguntas (IA o fallback) -----------------
def on_generate_questions():
    """
    Acción cuando el usuario pulsa 'Generar Preguntas': tomar las palabras clave
    y pedir a la IA preguntas básicas. Acepta múltiples keywords separadas por comas.
    """
    raw = prompt_text.get().strip()
    if not raw:
        messagebox.showwarning("Atención", "Introduce al menos una palabra clave o frase corta.")
        return
    # Normalizar y extraer keywords separadas por comas
    keywords = [k.strip() for k in raw.replace(";", ",").split(",") if k.strip()]
    if not keywords:
        messagebox.showwarning("Atención", "Introduce al menos una palabra clave o frase corta.")
        return
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
    # Mostrar las sugerencias de conceptos para que el usuario elija
    decision_tree["root"]["options"] = []
    decision_tree["root"]["next"] = {}
    show_concept_selection(concepts, blended_keywords)

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
    # Reiniciar navegación
    global current_node, breadcrumb_trail, current_mode
    current_node = decision_tree["root"]
    breadcrumb_trail = ["Root"]
    # Cambiar a modo graph para mostrar opciones
    current_mode = "graph"
    mode_var.set(1)
    update_status(f"Preguntas generadas para '{keyword}'. Elige una.")
    create_dynamic_interface()

def generate_more_questions():
    """
    Genera preguntas adicionales basadas en la última selección (breadcrumb last).
    Si no hay selección, se usa la última opción seleccionada en breadcrumb.
    """
    if len(breadcrumb_trail) <= 1:
        messagebox.showinfo("Info", "Selecciona primero una pregunta o concepto para generar más variaciones.")
        return
    last = breadcrumb_trail[-1]
    update_status(f"Generando más preguntas basadas en: {last} ...")
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
                model="openai/gpt-oss-120b",
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
                model="openai/gpt-oss-120b",
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

# ----------------- Concept selection UI -----------------
def show_concept_selection(concepts, keywords):
    for w in dynamic_frame.winfo_children():
        w.destroy()
    ttk.Label(dynamic_frame, text=f"Conceptos sugeridos para: {keywords}", background="#2E2E2E", foreground="white").pack(anchor="w", pady=4)
    selected_concepts = []

    def toggle_concept(concept, chk_var):
        if chk_var.get():
            if concept not in selected_concepts:
                selected_concepts.append(concept)
        else:
            if concept in selected_concepts:
                selected_concepts.remove(concept)

    # Mostrar cada concepto con un Checkbutton
    chk_vars = []
    for c in concepts:
        v = tk.IntVar(value=0)
        chk = ttk.Checkbutton(dynamic_frame, text=c, variable=v, command=lambda c=c, v=v: toggle_concept(c, v))
        chk.pack(anchor="w", padx=2, pady=2)
        chk_vars.append(v)

    def confirm_selection():
        if not selected_concepts:
            messagebox.showinfo("Info", "Selecciona al menos un concepto para generar preguntas.")
            return
        combo = ", ".join(selected_concepts)
        prompt_text.delete(0, tk.END)
        prompt_text.insert(0, combo)
        # Generar preguntas a partir de la selección combinada
        threading.Thread(target=generate_initial_questions_thread, args=(combo,), daemon=True).start()

    def add_more_keywords():
        prompt_text.focus_set()

    btn_frame = tk.Frame(dynamic_frame, bg="#2E2E2E")
    btn_frame.pack(fill="x", pady=6)
    ttk.Button(btn_frame, text="Confirmar selección y generar preguntas", command=confirm_selection).pack(side="left", padx=2)
    ttk.Button(btn_frame, text="Agregar más palabras clave", command=add_more_keywords).pack(side="left", padx=2)
    root.update_idletasks()

# ----------------- Autocompletado client-side -----------------
def suggest_auto_completion(event=None):
    text = prompt_text.get().strip().lower()
    if not text:
        suggestion_list.pack_forget()
        return
    matches = [s for s in common_suggestions if s.lower().startswith(text)]
    suggestion_list.delete(0, tk.END)
    for m in matches[:8]:
        suggestion_list.insert(tk.END, m)
    if matches:
        suggestion_list.pack(fill="x", pady=2)
    else:
        suggestion_list.pack_forget()

def select_suggestion(event):
    if suggestion_list.curselection():
        sel = suggestion_list.get(suggestion_list.curselection())
        prompt_text.delete(0, tk.END)
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
        chat_display.tag_configure("ai", foreground="#BBBBBB")
        chat_display.insert(tk.END, f"AI: {full_response}\n\n", "ai")
        chat_display.see(tk.END)
        conversation_history.append({"role": "assistant", "content": full_response})
        return full_response
    try:
        try:
            stream = client.chat.completions.create(
                model="openai/gpt-oss-120b",
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
                    chat_display.insert(tk.END, piece, "ai")
                    chat_display.see(tk.END)
                    root.update()
        except Exception:
            resp = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=conversation_history,
                stream=False,
                temperature=0.7,
                max_tokens=500
            )
            try:
                full_response = resp.choices[0].message.content
            except Exception:
                full_response = getattr(resp.choices[0], "text", str(resp))
            chat_display.tag_configure("ai", foreground="#BBBBBB")
            chat_display.insert(tk.END, f"AI: {full_response}\n\n", "ai")
            chat_display.see(tk.END)
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
    prompt_text.delete(0, tk.END)
    chat_display.delete("1.0", tk.END)
    update_status("Reset completado.")
    create_dynamic_interface()

# ---------- Inicio UI ----------
create_dynamic_interface()

# Ejecutar mainloop
try:
    root.mainloop()
except Exception as e:
    print("GUI error:", e)
