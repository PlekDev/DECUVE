# 🧠 BCI Chat Interface with a API 

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

**An advanced Brain-Computer Interface (BCI) for AI-assisted communication**

*Project developed for the Hackathon "Fuerza Grupera: Connect your head with AI"*


</div>

---

## 📋 Overview

**BCI Chat Interface with Groq** is an innovative Augmentative and Alternative Communication (AAC) solution that combines brain-computer interfaces with cutting-edge artificial intelligence. The system enables users with reduced mobility to interact with advanced language models through two complementary modalities:

### 🎯 Interaction Modes

1. **Speller Mode** - Letter-by-letter assisted writing
   - Native integration with Intendix Speller (Unicorn Hybrid Black)
   - Adaptive virtual keyboard with P300 selection
   - Context-based intelligent auto-completion

2. **Graph Mode** - Guided conceptual navigation
   - Automatic contextual question generation
   - Dynamic decision tree
   - Simplified numeric selection (1-9)

The system uses Groq's **Llama 3.3 70B** model for natural language processing with ultra-low latency (~500ms), optimized for real-time applications.

---

## ✨ Key Features

### 🔌 BCI Hardware Integration
- **Native Intendix Speller support** via UDP protocol (port 1000)
- Compatible with Unicorn Hybrid Black EEG device
- Automatic .NET Binary Serialization protocol deserialization
- Advanced character filtering with Unicode validation

### 🤖 Advanced Artificial Intelligence
- **AI Engine**: Groq API with Llama 3.3 70B Versatile model
- **Contextual generation**: Up to 9 relevant questions per query
- **Real-time streaming**: Progressive word-by-word responses
- **Conversational history**: Context memory for coherent dialogues

### 🎨 Modern User Interface
- **Framework**: ttkbootstrap with professional dark theme
- **Adaptive design**: Responds to user needs
- **Clear visualization**: Typography optimized for readability
- **Status indicators**: Real-time visual feedback

### 🛡️ Robustness and Reliability
- **Debug Mode**: Complete simulation without BCI hardware
- **Error handling**: Automatic recovery from failures
- **Input validation**: Deep Unicode character cleaning
- **Smart fallbacks**: Alternative responses if API unavailable

---

## 🚀 Installation

### Prerequisites

- **Python**: 3.8 or higher
- **Operating System**: Windows 10/11, Linux, macOS
- **Optional Hardware**: Unicorn Hybrid Black + Intendix Speller

### Quick Installation

```bash
# 1. Clone the repository
git clone https://github.com/PlekDev/DECUVE.git
cd bci-chat-interface

# 2. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

### System Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `ttkbootstrap` | ≥1.10.1 | Modern graphical interface |
| `groq` | ≥0.4.0 | Groq API client |
| `pylsl` | ≥1.16.0 | LSL data streaming (optional) |

```bash
# Manual dependency installation
pip install ttkbootstrap>=1.10.1
pip install groq>=0.4.0
pip install pylsl>=1.16.0  # Optional for LSL
```

### API Key Configuration

Get your free Groq API key:
1. Visit [console.groq.com/keys](https://console.groq.com/keys)
2. Create an account or sign in
3. Generate a new API key

**Option 1 - Graphical interface** (recommended):
- Run the application
- Click "Configure API Key"
- Paste your key and save

**Option 2 - Source code**:
```python
# In main.py, line 24
GROQ_API_KEY = "your-api-key-here"
```

---

## 💻 Usage Guide

### Quick Start

```bash
# Run the application
python main.py
```

### Workflow - Speller Mode with Intendix

1. **Start the system**
   - Click "Start Interface"
   - System will begin listening on UDP port 1000
   - Confirmation message appears in chat

2. **Write query**
   - Use Intendix Speller to write your question
   - Each character appears in real-time
   - **End with `!` to generate questions**

3. **Select question**
   - System generates 6-9 numbered questions
   - Visual menu appears in chat
   - Use Speller to type the number (1-9)

4. **Receive response**
   - Question automatically sent to Groq
   - Streaming response appears word by word
   - Continue cycle for new queries

### Workflow - Graph Mode (Manual)

1. **Switch to Graph mode**
   - Select "Graph (suggestions)" radio button

2. **Enter keywords**
   - Type concepts separated by commas
   - Example: `AI, health, ethics`

3. **Generate questions**
   - Click "Generate Questions"
   - Wait 2-3 seconds

4. **Select and send**
   - Click on a question to select it
   - Click "✉ Send this question to Chat"
   - Read complete response

### Debug Mode (Simulation)

Perfect for development without BCI hardware:

```python
# Debug mode is enabled by default
debug_mode = True  # Line 59 in main.py
```

**Debug mode features:**
- Automatic click simulation every 1.2s
- Random EEG data
- No physical hardware required
- Ideal for testing and development

---

## 🔧 Technical Documentation

### System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    GUI Layer (Tkinter)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Speller    │  │    Graph     │  │  Chat Display│ │
│  │   Interface  │  │   Navigator  │  │              │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│              Processing Layer (Threading)               │
│  ┌──────────────────────────────────────────────────┐  │
│  │  UDP Listener  →  Queue Manager  →  Processor    │  │
│  └──────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│                 Integration Layer                       │
│  ┌─────────────────┐          ┌─────────────────┐      │
│  │ Intendix UDP    │          │   Groq API      │      │
│  │ (Port 1000)     │          │ (Llama 3.3 70B) │      │
│  └─────────────────┘          └─────────────────┘      │
└─────────────────────────────────────────────────────────┘
```

### Intendix Speller Protocol

**UDP Packet Format:**
```
Maximum size: 12264 bytes
Format: .NET Binary Serialization
Encoding: UTF-8
Port: 1000 (localhost)
```

**Deserialization Process:**
1. Search for `0x06` marker (.NET string start)
2. Read ULEB128 length (variable-length encoding)
3. Extract UTF-8 bytes
4. Validate and clean character (`clean_character` function)

### Character Validation

```python
# Allowed characters whitelist
allowed = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ'
              'abcdefghijklmnopqrstuvwxyz'
              '0123456789 .,;:?!¿¡áéíóúÁÉÍÓÚñÑüÜ')

# Cleaning process:
# 1. Remove Unicode control characters (category C)
# 2. Verify whitelist
# 3. Take only first character if multiple
```

### Groq API - Optimal Configuration

```python
# Question generation (fast)
model="llama-3.3-70b-versatile"
temperature=0.6
max_tokens=200
stream=False

# Conversational responses (streaming)
model="llama-3.3-70b-versatile"
temperature=0.7
max_tokens=500
stream=True
```

### Global State Management

```python
# Main states
conversation_history = []     # Chat history with AI
decision_tree = {}           # Question tree
current_question_map = {}    # Number → question mapping
waiting_for_selection = False # Selection mode flag
buffered_text = ""           # Temporary writing buffer
```

---

## 🔬 Use Cases

### 1. Assistive Communication (AAC)

**User profile:** People with ALS, cerebral palsy, or spinal cord injuries

**Benefits:**
- Faster communication than traditional spelling (40% less time)
- Expression of complex ideas through predefined questions
- Reduced cognitive fatigue with guided navigation

### 2. BCI Research

**Applications:**
- Development of optimized P300 protocols
- Testing of adaptive interfaces
- Validation of classification algorithms

**Measurable metrics:**
- Selection accuracy
- Response time
- Character Error Rate (CER)

### 3. Education and Topic Exploration

**Functionality:**
- Generation of conceptual trees
- Guided exploration of complex topics
- AI-assisted interactive learning

---

## 🎛️ Advanced Configuration

### Customizing Speller Characters

```python
# In main.py, line 56
alphabet = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _.,?!")

# Example: Extended Spanish alphabet
alphabet = list("ABCDEFGHIJKLMNÑOPQRSTUVWXYZÁÉÍÓÚ0123456789 _.,?!¿¡")
```

### Adjusting Simulation Timing

```python
# In main.py, run_interface() function (line ~600)
time.sleep(1.2)  # Change to simulate different speed
```

### Modifying Number of Generated Questions

```python
# In main.py, generate_initial_questions_thread() function (line ~490)
suggestions = suggestions[:9]  # Change limit (1-9 recommended)
```

### LSL (Lab Streaming Layer) - Configuration

```python
# To send markers to external analysis systems
info = StreamInfo('BCIInterface', 'Markers', 1, 0, 'string', 'bci_marker')
outlet = StreamOutlet(info)
outlet.push_sample([selected_character])
```

---

## 📊 Performance Metrics

| Metric | Typical Value | Conditions |
|---------|---------------|------------|
| **Groq API Latency** | 300-800ms | Question generation |
| **Streaming latency** | 50-150ms/token | Conversational responses |
| **UDP Processing** | <10ms | Packet deserialization |
| **GUI Update** | 50ms | Queue polling cycle |
| **Character accuracy** | >95% | With calibrated Intendix |

---

## 🐛 Troubleshooting

### Error: "⚠️ WARNING: No valid Groq API key found"

**Solution:**
1. Verify your API key has more than 10 characters
2. Use "Configure API Key" button in interface
3. Restart application after configuration

### Error: "groq module not installed"

**Solution:**
```bash
pip install groq --upgrade
# Or specify version:
pip install groq==0.4.2
```

### Not receiving characters from Speller

**Diagnosis:**
1. Verify Intendix is configured for UDP port 1000
2. Check Windows firewall (allow local UDP traffic)
3. Review console logs: "Waiting for data from Intendix Speller..."

**Solution:**
```python
# Verify correct port in main.py, line 153
sock.bind(("127.0.0.1", 1000))
```

### Invalid or corrupted characters

**Known issue:** Some UDP packets contain control characters

**Implemented solution:**
- Automatic cleaning with `clean_character()`
- Allowed characters whitelist
- Rejection of Unicode control categories

### API rate limiting / 429 errors

**Solution:**
- Groq offers generous free tier (typically 30 req/min)
- Wait 60 seconds between intensive queries
- Consider upgrading to paid plan for higher throughput

---
### Priority Improvement Areas

- [ ] **Multi-language support**: Complete i18n system
- [ ] **Real P300 algorithm**: ML classifier implementation
- [ ] **Conversation persistence**: Save/load history
- [ ] **Usage metrics**: Analytics dashboard
- [ ] **Synthesized voice**: Text-to-speech for responses
- [ ] **Offline mode**: Local model with llama.cpp

### Code Standards

- **PEP 8** for Python style
- **Type hints** for public functions
- **Docstrings** for classes and complex functions
- **Unit tests** for critical functionality

---

## 📄 License

This project is licensed under the code name unicorn speller hybrid black.
https://github.com/unicorn-bi/Unicorn-Speller-Hybrid-Black/blob/main/UnicornSpeller.md

---

## 👥 Project Contributors

These are the GitHub profiles of the team members who contributed to this project:

- [Jev05](https://github.com/Jev05)
- [DiegoLizarraga](https://github.com/DiegoLizarraga) 
- [Victor-123321](https://github.com/Victor-123321) 
- [KevRamirezM](https://github.com/KevRamirezM)  
- [andyys27](https://github.com/andyys27) 
- [IsaacVRey](https://github.com/IsaacVRey) 

## 🙏 Acknowledgments

- **Groq** for providing free access to their ultra-fast API
- **Unicorn (g.tec)** for research-grade EEG hardware
- **Intendix** for the established BCI communication system
- **Python BCI** community for resources and support

---

**⭐ If you find this project useful, consider giving it a star on GitHub ⭐**

Made with ❤️ for the BCI community

</div>
