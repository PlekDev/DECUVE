import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import IntVar, messagebox, Listbox, END
import threading
import time
import random
import configparser
import socket
import struct
import queue
import unicodedata

# Groq client import
try:
    from groq import Groq
except Exception:
    Groq = None

# pylsl imports
try:
    from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_stream
except Exception:
    StreamInfo = StreamOutlet = StreamInlet = resolve_stream = None

# --------- API KEY LOADING ----------
GROQ_API_KEY = " "

# Validate API key
if not GROQ_API_KEY or len(GROQ_API_KEY) < 10:
    print("⚠️ WARNING: No valid Groq API key found")
    client = None
else:
    if Groq is not None:
        try:
            client = Groq(api_key=GROQ_API_KEY)
            print("✓ Groq client initialized successfully")
        except Exception as e:
            print(f"❌ Groq client init error: {e}")
            client = None
    else:
        print("⚠️ 'groq' module not installed. Use: pip install groq")
        client = None

# --------- Global State ----------
conversation_history = []
decision_tree = {"root": {"options": [], "next": {}}}
current_mode = "speller"
current_node = decision_tree["root"]
breadcrumb_trail = ["Root"]
buttons = []
alphabet = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _.,?!")
is_running = False
debug_mode = True
unicorn = None

# Globals for Intendix Speller integration
buffered_text = ""
pending_char_queue = queue.Queue()
pending_phrase_queue = queue.Queue()
listener_thread = None

# NEW: Question menu state for speller-based selection
current_question_map = {}
waiting_for_selection = False

class BoardItem:
    def __init__(self):
        self.enabled = False
        self.removable = False
        self.supports_double_security = False
        self.name = ""
        self.text = ""
        self.output_text = ""
        self.flash_image_filename = ""
        self.dark_image_filename = ""

def read_uleb128(data, offset):
    result = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
    else:
        return 0, offset
    return result, offset

def parse_dotnet_string(data, offset):
    if offset >= len(data):
        return None, offset
    
    if data[offset] == 0x06:
        offset += 1
        if offset >= len(data):
            return None, offset
        
        length, offset = read_uleb128(data, offset)
        
        if offset + length > len(data):
            return None, offset
        
        string_bytes = data[offset:offset + length]
        offset += length
        
        try:
            return string_bytes.decode('utf-8'), offset
        except UnicodeDecodeError:
            return None, offset
    
    return None, offset

def clean_character(char):
    """Cleans and validates a character, removing control or non-printable characters"""
    if not char:
        return None
    
    # Remove Unicode control characters (category C)
    cleaned = ''.join(c for c in char if unicodedata.category(c)[0] != 'C')
    
    # Take only the first character if multiple
    if cleaned:
        cleaned = cleaned[0]
    else:
        return None
    
    # Whitelist of allowed characters
    allowed = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,;:?!¿¡áéíóúÁÉÍÓÚñÑüÜ')
    
    if cleaned in allowed:
        return cleaned
    
    return None

def deserialize_board_item(data):
    """Deserializes a BoardItem from received bytes"""
    try:
        item = BoardItem()
        strings_found = []
        
        for i in range(len(data) - 50):
            if data[i] == 0x06:
                string_val, _ = parse_dotnet_string(data, i)
                if string_val is not None:
                    strings_found.append(string_val)
        
        if len(strings_found) >= 3:
            raw_char = strings_found[2]
            cleaned_char = clean_character(raw_char)
            
            if cleaned_char:
                item.output_text = cleaned_char
                return item
        
        return None
        
    except Exception as e:
        print(f"   Error deserializing: {e}")
        return None

def intendix_listener():
    """Intendix Speller Listener"""
    global buffered_text
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 1000))
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    print("Waiting for data from Intendix Speller...")
    print("Type something in the Speller and end with '!'")
    print("=" * 60)
    print()

    packet_count = 0

    while is_running:
        try:
            data, addr = sock.recvfrom(12264)
            packet_count += 1
            
            # Main extraction
            item = deserialize_board_item(data)
            if item and item.output_text:
                char = item.output_text
                
                print(f"✓ Valid character received: '{char}'")
                
                pending_char_queue.put(char)
                buffered_text += char
                print(f"   Buffer: '{buffered_text}'")
                
                if char == '!':
                    phrase = buffered_text.replace('!', '').strip()
                    if phrase:
                        print(f"\n✓ Complete phrase: '{phrase}'")
                        print("=" * 60)
                        pending_phrase_queue.put(phrase)
                    buffered_text = ""
            
            # Backup: Extraction from third string
            else:
                strings_found_debug = []
                for i in range(len(data) - 50):
                    if data[i] == 0x06:
                        string_val, _ = parse_dotnet_string(data, i)
                        if string_val is not None:
                            strings_found_debug.append(string_val)
                
                if len(strings_found_debug) >= 3:
                    raw_char = strings_found_debug[2]
                    cleaned_char = clean_character(raw_char)
                    
                    if cleaned_char:
                        print(f"✓ Character extracted (backup): '{cleaned_char}'")
                        
                        if not buffered_text.endswith(cleaned_char):
                            pending_char_queue.put(cleaned_char)
                            buffered_text += cleaned_char
                            print(f"   Buffer: '{buffered_text}'")
                        
                        if cleaned_char == '!':
                            phrase = buffered_text.replace('!', '').strip()
                            if phrase:
                                print(f"\n✓ Complete phrase: '{phrase}'")
                                print("=" * 60)
                                pending_phrase_queue.put(phrase)
                            buffered_text = ""
                    else:
                        if raw_char:
                            hex_repr = ' '.join(f'{ord(c):04x}' for c in raw_char)
                            print(f"⚠ Invalid character rejected: {repr(raw_char)} (hex: {hex_repr})")
            
        except Exception as e:
            print(f"❌ Error in listener: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(0.1)

# Mock Unicorn
class MockUnicorn:
    def connect(self): pass
    def read_eeg(self): return [random.random() for _ in range(8)]
unicorn = MockUnicorn()

# --------- GUI ----------
app = tb.Window(themename="darkly")
app.title("BCI Chat Interface with Groq - Hackathon")
app.geometry("900x720")
app.minsize(900, 600)

left_frame = tb.Frame(app)
left_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=8, pady=8)

right_frame = tb.Frame(app, width=360)
right_frame.pack(side=RIGHT, fill=Y, padx=8, pady=8)

# Chat display
chat_display = tb.Text(left_frame, width=60, height=40, font=("Arial", 11), wrap=WORD, insertbackground="white")
chat_display.pack(fill=BOTH, expand=True)
chat_display.tag_configure("user", foreground="#4CAF50")
chat_display.tag_configure("ai", foreground="#BBBBBB")
chat_display.tag_configure("system", foreground="#FFA500")

# Controls
tb.Label(right_frame, text="Mode:").pack(anchor="w", pady=(4,0))
mode_var = IntVar(value=0)
tb.Radiobutton(right_frame, text="Speller (type letter)", variable=mode_var, value=0, command=lambda: switch_mode()).pack(anchor="w")
tb.Radiobutton(right_frame, text="Graph (suggestions)", variable=mode_var, value=1, command=lambda: switch_mode()).pack(anchor="w")

debug_var = IntVar(value=1)
tb.Checkbutton(right_frame, text="Debug (simulate clicks)", variable=debug_var, command=lambda: toggle_debug()).pack(fill=X, pady=6)

# API Key configuration
api_frame = tb.Labelframe(right_frame, text="API Configuration")
api_frame.pack(fill=X, pady=6)

api_status = tb.Label(api_frame, text="API: Not configured" if not client else "API: ✓ Connected", 
                      bootstyle=DANGER if not client else SUCCESS)
api_status.pack(pady=4)

def open_api_config():
    api_window = tb.Toplevel(app)
    api_window.title("Configure Groq API Key")
    api_window.geometry("500x250")
    
    tb.Label(api_window, text="Enter your Groq API Key:", font=("Arial", 12)).pack(pady=10)
    
    api_entry = tb.Entry(api_window, width=50, font=("Arial", 10))
    api_entry.pack(pady=10)
    api_entry.insert(0, GROQ_API_KEY if GROQ_API_KEY else "")
    
    tb.Label(api_window, text="Get your free API key at:\nhttps://console.groq.com/keys", 
             bootstyle=SUCCESS, font=("Arial", 9)).pack(pady=5)
    
    def save_api_key():
        global GROQ_API_KEY, client
        new_key = api_entry.get().strip()
        if not new_key or len(new_key) < 10:
            messagebox.showerror("Error", "Invalid API key")
            return
        
        GROQ_API_KEY = new_key
        
        try:
            if Groq is not None:
                client = Groq(api_key=GROQ_API_KEY)
                api_status.config(text="API: ✓ Connected", bootstyle=SUCCESS)
                messagebox.showinfo("Success", "API Key configured successfully")
                api_window.destroy()
            else:
                messagebox.showerror("Error", "'groq' module not installed.\nUse: pip install groq")
        except Exception as e:
            messagebox.showerror("Error", f"Error connecting to Groq:\n{e}")
    
    tb.Button(api_window, text="Save and Connect", bootstyle=SUCCESS, command=save_api_key).pack(pady=10)
    tb.Button(api_window, text="Cancel", bootstyle=SECONDARY, command=api_window.destroy).pack()

tb.Button(api_frame, text="Configure API Key", bootstyle=PRIMARY, command=open_api_config).pack(pady=4)

tb.Label(right_frame, text="Keyword / Concept (keywords separated by commas):").pack(anchor="w")
prompt_text = tb.Entry(right_frame, width=40, font=("Arial", 12))
prompt_text.pack(pady=6)
prompt_text.bind("<KeyRelease>", lambda e: suggest_auto_completion())

# Auto-completion listbox
suggestion_list = Listbox(right_frame, height=5, font=("Arial", 10), bg="#1E1E1E", fg="white")
suggestion_list.pack(fill=X, pady=2)
suggestion_list.bind("<<ListboxSelect>>", lambda e: select_suggestion(e))
suggestion_list.pack_forget()

common_suggestions = [
    "who","what","how","when","where","why","AI","care","health","education","finances",
    "blockchain","cryptocurrencies","marriage","sex","addictions","volcanoes","physics","biology"
]

# Dynamic area
dynamic_frame = tb.Frame(right_frame)
dynamic_frame.pack(fill=BOTH, expand=False, pady=8)

# Buttons
control_frame = tb.Frame(right_frame)
control_frame.pack(fill=X, pady=4)
start_button = tb.Button(control_frame, text="Start Interface", bootstyle=SUCCESS, command=lambda: start_interface())
start_button.pack(side=LEFT, padx=4)
submit_button = tb.Button(control_frame, text="Generate Questions", bootstyle=INFO, command=lambda: on_generate_questions())
submit_button.pack(side=LEFT, padx=4)
reset_button = tb.Button(control_frame, text="Reset", bootstyle=DANGER, command=lambda: reset_all())
reset_button.pack(side=LEFT, padx=4)

status_label = tb.Label(right_frame, text="Status: Ready (Debug)", anchor=W)
status_label.pack(fill=X, pady=(8,0))

# ----------------- UI Functions -----------------
def update_status(text):
    try:
        status_label.config(text=text)
    except:
        pass

def switch_mode():
    global current_mode, current_node, breadcrumb_trail, waiting_for_selection, current_question_map
    current_mode = "graph" if mode_var.get() == 1 else "speller"
    current_node = decision_tree["root"]
    breadcrumb_trail = ["Root"]
    waiting_for_selection = False
    current_question_map = {}
    instruction = "Type or use autocomplete (Speller)" if current_mode == "speller" else "Enter keywords and press 'Generate Questions'"
    update_status(f"Mode: {current_mode} – {instruction}")
    create_dynamic_interface()

def toggle_debug():
    global debug_mode
    debug_mode = bool(debug_var.get())
    update_status(f"Debug {'ON' if debug_mode else 'OFF'}")
    create_dynamic_interface()

def create_dynamic_interface():
    for w in dynamic_frame.winfo_children():
        w.destroy()
    global buttons
    buttons = []
    
    if current_mode == "speller":
        # Speller grid
        rows, cols = 5, 8
        for i in range(rows):
            rowframe = tb.Frame(dynamic_frame)
            rowframe.pack()
            for j in range(cols):
                idx = i*cols + j
                if idx < len(alphabet):
                    ch = alphabet[idx]
                    b = tb.Button(rowframe, text=ch, width=3, bootstyle=SECONDARY, 
                                 command=(lambda c=ch: process_selection(c)) if debug_mode else None)
                    b.pack(side=LEFT, padx=1, pady=1)
                    buttons.append(b)
    else:
        # Graph mode - show breadcrumb and questions
        breadcrumb_label = tb.Label(dynamic_frame, text=f"📍 Path: {' > '.join(breadcrumb_trail)}", 
                                   bootstyle=SUCCESS, font=("Arial", 10, "bold"))
        breadcrumb_label.pack(anchor="w", pady=(0,8))
        
        root_opts = decision_tree["root"].get("options", [])
        
        if not root_opts:
            tb.Label(dynamic_frame, text="❌ No questions generated", 
                     bootstyle=DANGER, font=("Arial", 11, "bold")).pack(anchor="w", pady=4)
            tb.Label(dynamic_frame, text="Enter keywords above and\npress 'Generate Questions'", 
                     bootstyle=SECONDARY, font=("Arial", 10), justify="left").pack(anchor="w", pady=2)
        else:
            instruction_text = "Click on a question to select it (or use Speller with number)"
            tb.Label(dynamic_frame, text=instruction_text, 
                     bootstyle=WARNING, font=("Arial", 9), wraplength=320, justify="left").pack(anchor="w", pady=(0,8))
            
            # Show questions as buttons
            for i, opt in enumerate(root_opts, 1):
                is_selected = (len(breadcrumb_trail) > 1 and breadcrumb_trail[-1] == opt)
                
                button_text = f"{i}. {opt}"
                if is_selected:
                    button_text = f"✓ {button_text}"
                
                b = tb.Button(dynamic_frame, text=button_text, width=45, 
                              bootstyle=SUCCESS if is_selected else PRIMARY,
                              command=(lambda o=opt: process_selection(o)) if debug_mode else None)
                b.pack(pady=2)
                buttons.append(b)
            
            tb.Frame(dynamic_frame, height=2, bootstyle="dark").pack(fill=X, pady=8)
            
            if len(breadcrumb_trail) > 1:
                selected_text = breadcrumb_trail[-1]
                
                selection_frame = tb.Frame(dynamic_frame, bootstyle="dark", relief="groove", borderwidth=2)
                selection_frame.pack(fill=X, pady=(0,8), padx=4)
                
                tb.Label(selection_frame, text="Selected Question:", 
                         bootstyle=SUCCESS, font=("Arial", 9, "bold")).pack(anchor="w", padx=8, pady=(6,2))
                tb.Label(selection_frame, text=f'"{selected_text}"', 
                         bootstyle="light", font=("Arial", 9), wraplength=300, justify="left").pack(anchor="w", padx=8, pady=(0,6))
                
                send_btn = tb.Button(dynamic_frame, text="✉ Send this question to Chat", 
                                    bootstyle=PRIMARY, command=send_current_question_to_chat)
                send_btn.pack(pady=(0,6), fill=X)
            else:
                tb.Label(dynamic_frame, text="👆 Select a question above", 
                         bootstyle=SECONDARY, font=("Arial", 9, "italic")).pack(anchor="w", pady=4)
            
            if len(breadcrumb_trail) > 1:
                back = tb.Button(dynamic_frame, text="⬅ Back", bootstyle=SECONDARY, command=go_back)
                back.pack(pady=(3,0), fill=X)
                
    app.update_idletasks()

def go_back():
    global current_node, breadcrumb_trail
    if len(breadcrumb_trail) > 1:
        breadcrumb_trail = ["Root"]
        current_node = decision_tree["root"]
        create_dynamic_interface()
        update_status("Returned to start")

def process_selection(selected):
    global current_node, breadcrumb_trail
    
    if current_mode == "speller":
        # In speller mode, add character to input
        cur = prompt_text.get()
        prompt_text.delete(0, END)
        prompt_text.insert(0, cur + selected)
        return
    
    # Graph mode selection
    if selected == "Custom":
        switch_mode()
        return
    
    breadcrumb_trail = ["Root", selected]
    
    if selected in decision_tree["root"]["next"]:
        current_node = decision_tree["root"]["next"][selected]
    else:
        decision_tree["root"]["next"][selected] = {"options": [], "next": {}}
        current_node = decision_tree["root"]["next"][selected]
    
    create_dynamic_interface()
    update_status(f"✓ Question selected")

def send_current_question_to_chat():
    if len(breadcrumb_trail) <= 1:
        messagebox.showinfo("Information", "First select a question by clicking on it.")
        return
    
    current_question = breadcrumb_trail[-1]
    send_selected_question_to_chat(current_question)

def send_selected_question_to_chat(question):
    if client is None:
        response = messagebox.askyesno(
            "API Not Configured",
            "No Groq API key configured.\n\n"
            "Do you want to configure it now to get real responses?\n\n"
            "(If you select 'No', a simulated response will be used)"
        )
        if response:
            open_api_config()
            return
    
    # Show in chat
    chat_display.insert(END, f"\nQuestion: {question}\n\n", "user")
    chat_display.see(END)
    
    threading.Thread(target=send_question_thread, args=(question,), daemon=True).start()

def send_question_thread(question):
    update_status("⏳ Sending question to Groq...")
    response = send_to_chat_api(question)
    
    def update_chat():
        chat_display.insert(END, f"\n{'='*60}\n\n", "ai")
        chat_display.see(END)
        update_status("✓ Response received. Type new query or select another question.")
    
    app.after(0, update_chat)

def process_phrase(phrase):
    """Called when user completes a phrase with '!' in speller"""
    global waiting_for_selection, current_question_map
    
    print(f"[DEBUG] process_phrase called with raw: {repr(phrase)}")
    
    # DEEP CLEANING
    cleaned = ''.join(c for c in phrase if unicodedata.category(c)[0] != 'C' or c == ' ')
    allowed = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,;:?!¿¡áéíóúÁÉÍÓÚñÑüÜ')
    cleaned = ''.join(c for c in cleaned if c in allowed)
    cleaned = cleaned.strip()
    
    print(f"[DEBUG] Cleaned phrase: '{cleaned}'")
    
    if cleaned:
        # Show what user typed
        chat_display.insert(END, f"\nYou wrote: {cleaned}\n", "user")
        chat_display.see(END)
        
        # Put in text field
        prompt_text.delete(0, END)
        prompt_text.insert(0, cleaned)
        
        update_status(f"Generating questions for: '{cleaned}'...")
        
        # Generate questions
        threading.Thread(target=generate_initial_questions_thread, args=(cleaned,), daemon=True).start()
    else:
        print(f"⚠ Empty phrase after cleaning")
        update_status("⚠ Invalid phrase")

def process_char(char):
    """Called for each character from speller"""
    global current_question_map, waiting_for_selection
    
    print(f"[DEBUG] process_char called with: {repr(char)}")
    
    cleaned = clean_character(char)
    if not cleaned:
        return
    
    # Check if we're in selection mode (numbered menu active)
    if waiting_for_selection and cleaned in current_question_map:
        selected_question = current_question_map[cleaned]
        
        # Show selection in chat
        chat_display.insert(END, f"\n✓ You selected option {cleaned}: {selected_question}\n\n", "system")
        chat_display.insert(END, "="*60 + "\n\n", "system")
        chat_display.see(END)
        
        # Clear selection state
        waiting_for_selection = False
        current_question_map = {}
        
        # Update graph mode to show selection
        if current_mode == "graph":
            process_selection(selected_question)
        
        # Send to chat
        send_selected_question_to_chat(selected_question)
        
        update_status("Question sent. Type new query with '!' or select another.")
        return
    
    # Normal mode: add character to input buffer
    if current_mode == "speller":
        print(f"[DEBUG] Adding character to input: '{cleaned}'")
        cur = prompt_text.get()
        prompt_text.delete(0, END)
        prompt_text.insert(0, cur + cleaned)
        update_status(f"Typing... (end with '!' to generate questions)")

def handle_pending_input():
    """Process chars/phrases from speller queues"""
    try:
        # Check for complete phrases first
        try:
            phrase = pending_phrase_queue.get_nowait()
            print(f"[DEBUG] Queue phrase retrieved: {phrase}")
            app.after(0, lambda p=phrase: process_phrase(p))
            return
        except queue.Empty:
            pass
        
        # Then single characters
        try:
            char = pending_char_queue.get_nowait()
            print(f"[DEBUG] Queue char retrieved: {char}")
            app.after(0, lambda c=char: process_char(c))
        except queue.Empty:
            pass
    except Exception as e:
        print(f"Error handling input: {e}")
        import traceback
        traceback.print_exc()

# ----------------- Question Generation -----------------
def on_generate_questions():
    """Manual trigger for question generation"""
    print(f"[DEBUG] on_generate_questions called")
    
    if client is None:
        response = messagebox.askyesno(
            "API Not Configured",
            "No Groq API key configured.\n\n"
            "Do you want to configure it now?\n\n"
            "(If you select 'No', example questions will be used)"
        )
        if response:
            open_api_config()
            return
    
    raw = prompt_text.get().strip()
    print(f"[DEBUG] Raw input: '{raw}'")
    
    if not raw:
        messagebox.showwarning("Attention", "Enter at least one keyword or short phrase.")
        return
    
    keywords = [k.strip() for k in raw.replace(";", ",").split(",") if k.strip()]
    if not keywords:
        messagebox.showwarning("Attention", "Enter at least one keyword or short phrase.")
        return
    
    submit_button.config(state="disabled")
    update_status("Generating questions...")
    
    blended = ", ".join(keywords)
    print(f"[DEBUG] Blended keywords: '{blended}'")
    threading.Thread(target=generate_initial_questions_thread, args=(blended,), daemon=True).start()

def generate_initial_questions_thread(keyword):
    """Generate initial questions from keywords"""
    print(f"[DEBUG] Generating questions for: {keyword}")
    update_status("Generating questions... (AI)")
    
    try:
        suggestions = generate_questions_from_keyword(keyword, context="initial")
    except Exception as e:
        print(f"Error generating questions: {e}")
        suggestions = fallback_generate_questions(keyword)
    
    # Limit to 9 questions (for digits 1-9)
    suggestions = suggestions[:9]
    
    decision_tree["root"]["options"] = suggestions
    decision_tree["root"]["next"] = {opt: {"options": [], "next": {}} for opt in suggestions}
    print(f"[DEBUG] Generated {len(suggestions)} suggestions")
    
    app.after(0, lambda: finish_question_generation(keyword, suggestions))

def finish_question_generation(keyword, suggestions):
    """Finalize question generation and show menu"""
    global current_node, breadcrumb_trail, current_mode, current_question_map, waiting_for_selection
    
    print(f"[DEBUG] Finishing generation for: {keyword}")
    
    current_node = decision_tree["root"]
    breadcrumb_trail = ["Root"]
    
    # Switch to graph mode to show questions
    current_mode = "graph"
    mode_var.set(1)
    
    submit_button.config(state="normal")
    
    # Create numbered question map for speller selection
    current_question_map = {}
    menu_text = "\n" + "="*60 + "\n"
    menu_text += "GENERATED QUESTIONS\n"
    menu_text += "="*60 + "\n\n"
    
    for i, q in enumerate(suggestions, 1):
        current_question_map[str(i)] = q
        menu_text += f"  {i}. {q}\n\n"
    
    menu_text += "="*60 + "\n"
    menu_text += f"Type the number (1-{len(suggestions)}) using the Speller to select.\n\n"
    
    # Show in chat
    chat_display.insert(END, menu_text, "system")
    chat_display.see(END)
    
    # Activate selection mode
    waiting_for_selection = True
    
    update_status(f"Questions generated. Click or type number (1-{len(suggestions)}) with Speller")
    create_dynamic_interface()

def generate_questions_from_keyword(keyword, context="initial"):
    """Call Groq to generate questions"""
    if context == "initial":
        system_msg = "You are an assistant that generates short and useful questions in English from keywords or phrases. Include questions like: what, how, when, where, why and 2-3 related conceptual questions. Return only the list, no long explanations."
        user_msg = f"Topics: {keyword}. Generate 6 short questions (max 10 words each) in English that combine the ideas."
    else:
        system_msg = "You are an assistant that generates concise variations and follow-up questions in English from a short question or topic."
        user_msg = f"Topic or question: {keyword}. Generate 5 short variations / follow-up questions that deepen the topic."

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
                if len(questions) >= 9:
                    break
                if len(l) > 3:
                    questions.append(l)
            if not questions:
                raise ValueError("No questions obtained from the API.")
            return questions[:9]
        except Exception as e:
            print(f"Groq API error: {e}")
    return fallback_generate_questions(keyword) if context == "initial" else fallback_generate_more(keyword)

def fallback_generate_questions(keyword):
    basic = [
        f"What is {keyword}?",
        f"How does {keyword} work?",
        f"When is {keyword} applied?",
        f"Where is {keyword} observed?",
        f"Why is {keyword} relevant?"
    ]
    conceptual = [
        f"Common examples of {keyword}",
        f"Benefits and risks of {keyword}"
    ]
    suggestions = basic + conceptual
    return suggestions[:9]

def fallback_generate_more(selected_option):
    return [
        f"Explain more about {selected_option}",
        f"Common problems related to {selected_option}",
        f"How to measure the impact of {selected_option}",
        f"Practical recommendations on {selected_option}",
        f"Use cases for {selected_option}"
    ]

# ----------------- Autocompletion -----------------
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

# ----------------- Interface Runtime -----------------
def start_interface():
    global is_running, listener_thread
    if is_running:
        update_status("Interface already running.")
        return
    is_running = True
    
    listener_thread = threading.Thread(target=intendix_listener, daemon=True)
    listener_thread.start()
    
    t = threading.Thread(target=run_interface, daemon=True)
    t.start()
    
    # Welcome message
    welcome = "\n" + "="*60 + "\n"
    welcome += "WELCOME TO BCI CHAT SYSTEM\n"
    welcome += "="*60 + "\n\n"
    welcome += "INSTRUCTIONS:\n\n"
    welcome += "SPELLER MODE (with Intendix):\n"
    welcome += "1. Use the Speller to write your query\n"
    welcome += "2. End with '!' to generate questions\n"
    welcome += "3. A numbered menu will be shown\n"
    welcome += "4. Type the number (1-9) with the Speller\n"
    welcome += "5. Read the AI response\n\n"
    welcome += "GRAPH MODE (with clicks):\n"
    welcome += "1. Type keywords in the text field\n"
    welcome += "2. Press 'Generate Questions'\n"
    welcome += "3. Click on questions to select\n"
    welcome += "4. Press 'Send this question to Chat'\n\n"
    welcome += "="*60 + "\n\n"
    
    chat_display.insert(END, welcome, "system")
    chat_display.see(END)
    
    update_status("Interface started. Speller listening on UDP 1000.")

def stop_interface():
    global is_running
    is_running = False
    update_status("Interface stopped.")

def run_interface():
    outlet = None
    if StreamInfo is not None:
        try:
            info = StreamInfo('BCIInterface', 'Markers', 1, 0, 'string', 'bci_marker')
            outlet = StreamOutlet(info)
        except Exception as e:
            print("LSL outlet error:", e)
    
    try:
        while is_running:
            handle_pending_input()
            
            if debug_mode:
                time.sleep(1.2)
                if buttons and current_mode == "speller":
                    idx = random.randint(0, len(buttons)-1)
                    try:
                        btn = buttons[idx]
                        label = btn.cget("text")
                        app.after(0, lambda s=label: process_selection(s))
                        if outlet:
                            outlet.push_sample([label])
                    except Exception as e:
                        print("Simulated click error:", e)
            else:
                if current_mode == "graph":
                    try:
                        signal = unicorn.read_eeg()
                        sel = detect_p300(signal)
                        if sel:
                            app.after(0, lambda s=sel: process_selection(s))
                            if outlet:
                                outlet.push_sample([sel])
                    except Exception as e:
                        print(f"EEG read error: {e}")
                time.sleep(0.1)
    except Exception as e:
        print("Error run_interface:", e)
    finally:
        is_running = False
        update_status("Interface finished.")

def detect_p300(signal):
    if current_mode == "speller":
        return None
    else:
        opts = current_node.get("options", [])
        if opts:
            return random.choice(opts)
    return None

# ----------------- Chat API -----------------
def send_to_chat_api(prompt):
    global conversation_history
    conversation_history.append({"role": "user", "content": prompt + " Instruction: Respond briefly and in the language of the prompt."})
    full_response = ""
    if client is None:
        full_response = f"(Simulated response for '{prompt}')"
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
                    def insert_piece(p=piece):
                        chat_display.tag_configure("ai", foreground="#BBBBBB")
                        chat_display.insert(END, p, "ai")
                        chat_display.see(END)
                    app.after(0, insert_piece)
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
        messagebox.showerror("API Error", f"Failed to connect to Groq: {e}")
        update_status("Status: API Error")
    conversation_history.append({"role": "assistant", "content": full_response})
    return full_response

# ----------------- Reset -----------------
def reset_all():
    global conversation_history, decision_tree, current_node, breadcrumb_trail, current_mode, buffered_text
    global current_question_map, waiting_for_selection
    
    conversation_history = []
    decision_tree = {"root": {"options": [], "next": {}}}
    current_node = decision_tree["root"]
    breadcrumb_trail = ["Root"]
    current_mode = "speller"
    mode_var.set(0)
    buffered_text = ""
    current_question_map = {}
    waiting_for_selection = False
    
    prompt_text.delete(0, END)
    chat_display.delete("1.0", END)
    
    update_status("Reset completed. Ready for new query.")
    create_dynamic_interface()

# ---------- UI Start ----------
create_dynamic_interface()

def periodic_update():
    handle_pending_input()
    app.after(50, periodic_update)

app.after(50, periodic_update)

try:
    app.mainloop()
except Exception as e:
    print("Error mainloop:", e)
