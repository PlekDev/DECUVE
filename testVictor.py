import tkinter as tk
from tkinter import ttk, scrolledtext, IntVar, messagebox
import threading
import time
import random
from groq import Groq  # For Groq API (pip install groq)
from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_streams

# Groq setup (free developer token from console.groq.com - sign up required, no payment)
GROQ_API_KEY = ""  # Replace with your actual token
client = Groq(api_key=GROQ_API_KEY)

# Conversation history for maintaining flow
conversation_history = []

# Decision tree structure (learning graph approach)
decision_tree = {
    "root": {
        "options": ["Science", "History", "Technology", "Custom"],
        "next": {
            "Science": {
                "options": ["Physics", "Biology"],
                "next": {
                    "Physics": {"prompt": "What is quantum computing?"},
                    "Biology": {"prompt": "What is DNA?"}
                }
            },
            "History": {
                "options": ["Ancient", "Modern"],
                "next": {
                    "Ancient": {"prompt": "Who built the pyramids?"},
                    "Modern": {"prompt": "What caused WWII?"}
                }
            },
            "Technology": {
                "options": ["AI", "Robotics"],
                "next": {
                    "AI": {"prompt": "What is machine learning?"},
                    "Robotics": {"prompt": "How do robots work?"}
                }
            },
            "Custom": {"mode": "speller"}  # Switch to speller for custom input
        }
    }
}

# GUI Setup with dark theme
root = tk.Tk()
root.title("BCI Chat Interface with Groq")
root.geometry("700x800")
root.configure(bg="#2E2E2E")  # Dark gray background

# Style configuration
style = ttk.Style()
try:
    style.theme_use("clam")  # Modern theme
    style.configure("TButton", font=("Arial", 12, "bold"), padding=10, background="#4CAF50", foreground="white")
    style.map("TButton", background=[("active", "#45A049")])  # Hover effect
    style.configure("TLabel", font=("Arial", 14), background="#2E2E2E", foreground="white")
    style.configure("TRadiobutton", font=("Arial", 12), background="#2E2E2E", foreground="white")
    style.configure("TCheckbutton", font=("Arial", 12), background="#2E2E2E", foreground="white")
except Exception as e:
    print(f"Style setup error: {e}")

# Mode selection frame
mode_frame = tk.Frame(root, bg="#2E2E2E")
mode_frame.pack(pady=10)
ttk.Label(mode_frame, text="Select Mode:", style="TLabel").pack()
mode_var = IntVar(value=0)  # 0: Speller, 1: Graph
ttk.Radiobutton(mode_frame, text="Speller Mode (Letter by Letter)", variable=mode_var, value=0, command=lambda: switch_mode(), style="TRadiobutton").pack(anchor="w")
ttk.Radiobutton(mode_frame, text="Graph Mode (Decision Tree)", variable=mode_var, value=1, command=lambda: switch_mode(), style="TRadiobutton").pack(anchor="w")

# Debug checkbox
debug_var = IntVar(value=1)  # Default to debug on
ttk.Checkbutton(root, text="Debug Mode (Simulate with Clicks)", variable=debug_var, command=lambda: toggle_debug(), style="TCheckbutton").pack(pady=5)

# Prompt display with instruction
prompt_frame = tk.Frame(root, bg="#2E2E2E")
prompt_frame.pack(pady=10)
prompt_label = ttk.Label(prompt_frame, text="Building Prompt:", style="TLabel")
prompt_label.pack()
prompt_text = ttk.Entry(prompt_frame, width=50, font=("Arial", 12))
prompt_text.pack(pady=5)
instruction_label = ttk.Label(prompt_frame, text="Focus on a letter or click in debug mode", font=("Arial", 10), style="TLabel")
instruction_label.pack()

# Conversation display
chat_display = scrolledtext.ScrolledText(root, width=80, height=20, font=("Arial", 11), bg="#1E1E1E", fg="white", insertbackground="white")
chat_display.pack(pady=10)

# Control buttons
control_frame = tk.Frame(root, bg="#2E2E2E")
control_frame.pack(pady=10)
start_button = ttk.Button(control_frame, text="Start")
start_button.pack(side="left", padx=5)
submit_button = ttk.Button(control_frame, text="Submit Prompt")
submit_button.pack(side="left", padx=5)
reset_button = ttk.Button(control_frame, text="Reset")
reset_button.pack(side="left", padx=5)

# Dynamic frame for Speller/Grid or Graph Options
dynamic_frame = tk.Frame(root, bg="#2E2E2E")
dynamic_frame.pack(pady=10)

# Status bar
status_label = ttk.Label(root, text="Status: Ready (Debug Mode)", font=("Arial", 10), style="TLabel", anchor="w")
status_label.pack(fill="x", pady=5)

# Global variables
current_mode = "speller"  # "speller" or "graph"
current_node = decision_tree["root"]
breadcrumb_trail = ["Root"]  # For graph mode navigation
buttons = []
alphabet = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _.,?!")
is_running = False
debug_mode = True  # Initial debug on

# Placeholder for Unicorn (adapt from g.tec Python package)
class MockUnicorn:
    def connect(self):
        pass
    def read_eeg(self):
        return [random.random() for _ in range(8)]  # Mock 8-channel signal

unicorn = MockUnicorn()  # Replace with real: from pyunicorn import Unicorn; unicorn = Unicorn()

def switch_mode():
    global current_mode, current_node, breadcrumb_trail
    current_mode = "graph" if mode_var.get() == 1 else "speller"
    current_node = decision_tree["root"]
    breadcrumb_trail = ["Root"]
    instruction_label.config(text="Focus on a letter or click in debug mode" if current_mode == "speller" else "Select an option or click in debug mode")
    status_label.config(text=f"Status: Switched to {current_mode.capitalize()} Mode {'(Debug)' if debug_mode else ''}")
    create_dynamic_interface()

def toggle_debug():
    global debug_mode
    debug_mode = bool(debug_var.get())
    status_label.config(text=f"Status: Debug Mode {'On' if debug_mode else 'Off'}")

def create_dynamic_interface():
    # Clear previous buttons
    for widget in dynamic_frame.winfo_children():
        widget.destroy()
    global buttons
    buttons = []

    try:
        if current_mode == "speller":
            # 5x8 Speller Grid (larger, more visible)
            for i in range(5):
                for j in range(8):
                    idx = i * 8 + j
                    if idx < len(alphabet):
                        char = alphabet[idx]
                        btn = ttk.Button(dynamic_frame, text=char, width=4, style="TButton")
                        if debug_mode:
                            btn.configure(command=lambda c=char: process_selection(c))
                        btn.grid(row=i, column=j, padx=3, pady=3)
                        buttons.append(btn)
        elif current_mode == "graph":
            # Graph Options with breadcrumb
            ttk.Label(dynamic_frame, text=f"Path: {' > '.join(breadcrumb_trail)}", font=("Arial", 10), style="TLabel").pack(pady=5)
            if "options" in current_node:
                for option in current_node["options"]:
                    btn = ttk.Button(dynamic_frame, text=option, style="TButton")
                    if debug_mode:
                        btn.configure(command=lambda opt=option: process_selection(opt))
                    btn.pack(pady=5, fill="x")
                    buttons.append(btn)
            # Back button for graph mode
            if len(breadcrumb_trail) > 1:
                back_button = ttk.Button(dynamic_frame, text="Back", command=go_back)
                back_button.pack(pady=5)
    except Exception as e:
        status_label.config(text=f"Status: Interface Error - {str(e)}")

def go_back():
    global current_node, breadcrumb_trail
    if len(breadcrumb_trail) > 1:
        breadcrumb_trail.pop()  # Remove current level
        current_node = decision_tree["root"]
        for step in breadcrumb_trail[1:]:  # Navigate back
            current_node = current_node["next"][step]
        create_dynamic_interface()

def flash_interface():
    while is_running:
        if not debug_mode:
            # Flash random row/column or option (simulated for P300)
            if current_mode == "speller":
                row = random.randint(0, 4)
                for btn in buttons[row*8:(row+1)*8]:
                    btn.config(style="TButton", background="#4CAF50")
                time.sleep(0.2)
                for btn in buttons:
                    btn.config(style="TButton", background="#4CAF50")
                root.update()
            elif current_mode == "graph":
                if buttons:
                    idx = random.randint(0, len(buttons)-1)
                    buttons[idx].config(style="TButton", background="#4CAF50")
                    time.sleep(0.2)
                    for btn in buttons:
                        btn.config(style="TButton", background="#4CAF50")
                    root.update()
        time.sleep(0.8)  # Inter-stimulus interval

def run_interface():
    global is_running
    is_running = True
    try:
        unicorn.connect()
        status_label.config(text="Status: EEG Connected" if not debug_mode else "Status: Debug Mode On")
    except:
        status_label.config(text="Status: EEG Connection Failed")
    
    # LSL Outlet
    info = StreamInfo('BCIInterface', 'Markers', 1, 0, 'string', 'bci_marker')
    outlet = StreamOutlet(info)
    
    while is_running:
        if not debug_mode:
            signal = unicorn.read_eeg()
            selected = detect_p300(signal)
            if selected:
                outlet.push_sample([selected])
                process_selection(selected)
        time.sleep(0.1)  # Small delay to prevent CPU overload

def detect_p300(signal):
    # Placeholder P300 detection (adapt from Unicorn Suite)
    if current_mode == "speller":
        return random.choice(alphabet)
    elif current_mode == "graph" and "options" in current_node:
        return random.choice(current_node["options"])
    return None

def process_selection(selected):
    global current_node, breadcrumb_trail
    current_prompt = prompt_text.get()
    if current_mode == "speller":
        current_prompt += selected
    elif current_mode == "graph":
        if selected == "Custom":
            switch_mode()
            return
        if not ("next" in current_node and selected in current_node["next"]):
            messagebox.showerror("Error", "Invalid selection! Resetting to root.")
            current_node = decision_tree["root"]
            breadcrumb_trail = ["Root"]
            create_dynamic_interface()
            return
        current_node = current_node["next"][selected]
        breadcrumb_trail.append(selected)
        if "prompt" in current_node:
            current_prompt = current_node["prompt"]
            current_node = decision_tree["root"]
            breadcrumb_trail = ["Root"]
        create_dynamic_interface()
    prompt_text.delete(0, tk.END)
    prompt_text.insert(0, current_prompt)

def chat_handler():
    current_prompt = ""
    while True:
        try:
            streams = resolve_streams('name', 'BCIInterface')
            inlet = StreamInlet(streams[0])
            while True:
                sample, _ = inlet.pull_sample(timeout=1.0)
                if sample:
                    char = sample[0]
                    current_prompt += char
                    prompt_text.delete(0, tk.END)
                    prompt_text.insert(0, current_prompt)
                    if char in [' ', '_']:
                        status_label.config(text="Status: Sending to Groq...")
                        response = send_to_chat_api(current_prompt.strip())
                        chat_display.tag_configure("user", foreground="#4CAF50")
                        chat_display.tag_configure("ai", foreground="#BBBBBB")
                        chat_display.insert(tk.END, f"You: {current_prompt}\n", "user")
                        chat_display.insert(tk.END, f"AI: {response}\n\n", "ai")
                        chat_display.see(tk.END)
                        current_prompt = ""
                        status_label.config(text="Status: Ready")
        except Exception:
            status_label.config(text="Status: LSL Stream Not Found, Retrying...")
            time.sleep(1)

def send_to_chat_api(prompt):
    global conversation_history
    conversation_history.append({"role": "user", "content": prompt})
    
    full_response = ""
    try:
        stream = client.chat.completions.create(
            model="llama3-8b-8192",  # Fast free model on Groq
            messages=conversation_history,
            stream=True,
            temperature=0.7,
            max_tokens=500
        )
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                full_response += content
                chat_display.insert(tk.END, content, "ai")
                chat_display.see(tk.END)
                root.update()
    except Exception as e:
        full_response = f"Error: {str(e)}"
        messagebox.showerror("API Error", f"Failed to connect to Groq: {str(e)}")
        status_label.config(text="Status: API Error")
    
    conversation_history.append({"role": "assistant", "content": full_response})
    return full_response

def reset():
    global conversation_history, current_node, breadcrumb_trail
    conversation_history = []
    current_node = decision_tree["root"]
    breadcrumb_trail = ["Root"]
    prompt_text.delete(0, tk.END)
    chat_display.delete(1.0, tk.END)
    create_dynamic_interface()
    status_label.config(text="Status: Reset Complete")

def start():
    threading.Thread(target=run_interface, daemon=True).start()
    threading.Thread(target=flash_interface, daemon=True).start()
    threading.Thread(target=chat_handler, daemon=True).start()

start_button.config(command=start)
submit_button.config(command=lambda: submit_prompt())
reset_button.config(command=reset)

def submit_prompt():
    prompt = prompt_text.get()
    if prompt:
        status_label.config(text="Status: Sending to Groq...")
        response = send_to_chat_api(prompt)
        chat_display.tag_configure("user", foreground="#4CAF50")
        chat_display.tag_configure("ai", foreground="#BBBBBB")
        chat_display.insert(tk.END, f"You: {prompt}\n", "user")
        chat_display.insert(tk.END, f"AI: {response}\n\n", "ai")
        prompt_text.delete(0, tk.END)
        status_label.config(text="Status: Ready")

# Initial setup
create_dynamic_interface()
root.mainloop()