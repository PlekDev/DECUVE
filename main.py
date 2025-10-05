"""
BCI to ChatGPT Interface for Unicorn Hybrid Black
Conecta señales cerebrales con Chat GPT usando P300 y Motor Imagery
"""

import numpy as np
from scipy import signal
from scipy.signal import butter, filtfilt
import time
import threading
from collections import deque
import openai

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

class BCIConfig:
    """Configuración del sistema BCI"""
    
    # Configuración Unicorn Hybrid Black
    SAMPLING_RATE = 250  # Hz
    NUM_CHANNELS = 8
    CHANNEL_NAMES = ['Fz', 'C3', 'Cz', 'C4', 'Pz', 'PO7', 'Oz', 'PO8']
    
    # Configuración P300 (para selección de menú)
    P300_WINDOW = 0.8  # segundos después del estímulo
    P300_THRESHOLD = 5.0  # umbral de detección
    
    # Configuración Motor Imagery (para control SI/NO)
    MI_WINDOW = 3.0  # segundos de ventana
    MI_BANDS = {
        'mu': (8, 13),      # Ritmo mu (motor imagery)
        'beta': (13, 30)    # Ritmo beta
    }
    
    # Opciones del menú BCI
    MENU_OPTIONS = [
        "Hacer pregunta",
        "Continuar conversación",
        "Resumir respuesta",
        "Explicar más simple",
        "Dar ejemplo",
        "Finalizar"
    ]

# ============================================================================
# PROCESAMIENTO DE SEÑALES EEG
# ============================================================================

class EEGProcessor:
    """Procesa señales EEG del Unicorn Hybrid Black"""
    
    def __init__(self):
        self.fs = BCIConfig.SAMPLING_RATE
        self.buffer = deque(maxlen=int(self.fs * 5))  # 5 segundos
        
    def bandpass_filter(self, data, lowcut, highcut, order=4):
        """Filtro pasa-banda Butterworth"""
        nyq = 0.5 * self.fs
        low = lowcut / nyq
        high = highcut / nyq
        b, a = butter(order, [low, high], btype='band')
        return filtfilt(b, a, data)
    
    def detect_p300(self, eeg_epoch, channel_idx=4):
        """
        Detecta onda P300 en el canal Pz (índice 4)
        Retorna: True si se detecta P300, False si no
        """
        # Filtrar 0.5-10 Hz para P300
        filtered = self.bandpass_filter(eeg_epoch[channel_idx], 0.5, 10)
        
        # Buscar pico positivo entre 250-500ms
        window_start = int(0.25 * self.fs)
        window_end = int(0.5 * self.fs)
        
        if len(filtered) < window_end:
            return False
            
        p300_window = filtered[window_start:window_end]
        max_amplitude = np.max(p300_window)
        
        return max_amplitude > BCIConfig.P300_THRESHOLD
    
    def compute_band_power(self, eeg_data, channel, band):
        """Calcula la potencia en una banda de frecuencia específica"""
        filtered = self.bandpass_filter(eeg_data, band[0], band[1])
        return np.mean(filtered ** 2)
    
    def classify_motor_imagery(self, eeg_epoch):
        """
        Clasifica Motor Imagery en C3 (mano izquierda) vs C4 (mano derecha)
        Retorna: 'left', 'right', o 'none'
        """
        c3_idx = 1  # Canal C3
        c4_idx = 3  # Canal C4
        
        # Calcular potencia mu en C3 y C4
        mu_c3 = self.compute_band_power(eeg_epoch[c3_idx], c3_idx, BCIConfig.MI_BANDS['mu'])
        mu_c4 = self.compute_band_power(eeg_epoch[c4_idx], c4_idx, BCIConfig.MI_BANDS['mu'])
        
        # Desincronización relacionada con eventos (ERD)
        # Menor potencia mu = activación
        ratio = mu_c3 / mu_c4 if mu_c4 > 0 else 1
        
        if ratio < 0.7:  # C3 más activo = imagina mano izquierda
            return 'left'
        elif ratio > 1.3:  # C4 más activo = imagina mano derecha
            return 'right'
        else:
            return 'none'

# ============================================================================
# INTERFAZ BCI
# ============================================================================

class BCIInterface:
    """Interfaz entre el BCI y el usuario"""
    
    def __init__(self):
        self.processor = EEGProcessor()
        self.current_option = 0
        self.is_selecting = False
        self.flash_times = []
        
    def flash_option(self, option_idx):
        """Muestra una opción del menú (simula flash visual)"""
        print(f"\n>>> FLASH: {BCIConfig.MENU_OPTIONS[option_idx]} <<<")
        self.flash_times.append(time.time())
        
    def run_p300_selection(self, eeg_stream):
        """
        Ejecuta paradigma P300 para seleccionar opción del menú
        Retorna: índice de la opción seleccionada
        """
        print("\n=== MODO SELECCIÓN P300 ===")
        print("Enfócate en la opción que deseas seleccionar...")
        time.sleep(2)
        
        p300_scores = np.zeros(len(BCIConfig.MENU_OPTIONS))
        num_repetitions = 3
        
        for rep in range(num_repetitions):
            print(f"\nRepetición {rep + 1}/{num_repetitions}")
            
            # Presentar cada opción en orden aleatorio
            order = np.random.permutation(len(BCIConfig.MENU_OPTIONS))
            
            for idx in order:
                self.flash_option(idx)
                flash_time = time.time()
                time.sleep(0.15)  # ISI (Inter-Stimulus Interval)
                
                # Capturar época EEG después del flash
                epoch_samples = int(BCIConfig.P300_WINDOW * BCIConfig.SAMPLING_RATE)
                eeg_epoch = eeg_stream.get_epoch(epoch_samples)
                
                # Detectar P300
                if self.processor.detect_p300(eeg_epoch):
                    p300_scores[idx] += 1
                    print(f"  ✓ P300 detectado para opción {idx}")
                
                time.sleep(0.2)  # Pausa entre flashes
        
        # Seleccionar opción con mayor score
        selected = np.argmax(p300_scores)
        print(f"\n✓ SELECCIONADO: {BCIConfig.MENU_OPTIONS[selected]}")
        return selected
    
    def run_motor_imagery_confirmation(self, eeg_stream):
        """
        Usa Motor Imagery para confirmación SI/NO
        Imagina mano izquierda = NO, mano derecha = SI
        """
        print("\n=== CONFIRMACIÓN MOTOR IMAGERY ===")
        print("Imagina movimiento de:")
        print("  MANO DERECHA = SI")
        print("  MANO IZQUIERDA = NO")
        time.sleep(1)
        
        # Capturar ventana de motor imagery
        mi_samples = int(BCIConfig.MI_WINDOW * BCIConfig.SAMPLING_RATE)
        eeg_epoch = eeg_stream.get_epoch(mi_samples)
        
        classification = self.processor.classify_motor_imagery(eeg_epoch)
        
        if classification == 'right':
            print("✓ Confirmado: SI")
            return True
        elif classification == 'left':
            print("✓ Confirmado: NO")
            return False
        else:
            print("⚠ No detectado, reintentando...")
            return None

# ============================================================================
# SIMULADOR DE STREAM EEG (para pruebas sin hardware)
# ============================================================================

class MockEEGStream:
    """Simula stream de datos del Unicorn Hybrid Black"""
    
    def __init__(self):
        self.fs = BCIConfig.SAMPLING_RATE
        self.buffer = deque(maxlen=self.fs * 10)
        self.is_running = False
        self.thread = None
        
    def start(self):
        """Inicia el stream simulado"""
        self.is_running = True
        self.thread = threading.Thread(target=self._generate_data)
        self.thread.start()
        print("✓ Stream EEG iniciado (modo simulación)")
        
    def stop(self):
        """Detiene el stream"""
        self.is_running = False
        if self.thread:
            self.thread.join()
        
    def _generate_data(self):
        """Genera datos EEG sintéticos"""
        while self.is_running:
            # Generar muestra de 8 canales
            sample = np.random.randn(BCIConfig.NUM_CHANNELS) * 10
            self.buffer.append(sample)
            time.sleep(1.0 / self.fs)
    
    def get_epoch(self, num_samples):
        """Obtiene época de EEG"""
        if len(self.buffer) < num_samples:
            # Rellenar con ceros si no hay suficientes datos
            data = np.zeros((BCIConfig.NUM_CHANNELS, num_samples))
        else:
            recent_data = list(self.buffer)[-num_samples:]
            data = np.array(recent_data).T
        return data

# ============================================================================
# CONECTOR CON CHATGPT
# ============================================================================

class ChatGPTConnector:
    """Conecta el BCI con la API de ChatGPT"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.conversation_history = []
        
        if api_key:
            openai.api_key = api_key
    
    def send_prompt(self, prompt, context=None):
        """Envía prompt a ChatGPT"""
        if not self.api_key:
            # Modo demo sin API key
            return self._mock_response(prompt)
        
        try:
            messages = [{"role": "system", "content": "Eres un asistente controlado por BCI. Responde de forma concisa."}]
            
            if context:
                messages.append({"role": "user", "content": context})
            
            messages.append({"role": "user", "content": prompt})
            
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=messages,
                max_tokens=200
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _mock_response(self, prompt):
        """Respuesta simulada para modo demo"""
        return f"[DEMO] Respuesta a: '{prompt}'\nEsta es una simulación. Configura tu API key de OpenAI para respuestas reales."

# ============================================================================
# APLICACIÓN PRINCIPAL
# ============================================================================

class BrainChatGPT:
    """Aplicación principal: Cerebro -> ChatGPT"""
    
    def __init__(self, api_key=None):
        self.bci = BCIInterface()
        self.chatgpt = ChatGPTConnector(api_key)
        self.eeg_stream = MockEEGStream()  # Cambiar por UnicornPy en producción
        self.is_running = False
        
    def start(self):
        """Inicia la aplicación"""
        print("="*60)
        print("BRAIN-COMPUTER INTERFACE TO CHATGPT")
        print("Unicorn Hybrid Black + OpenAI")
        print("="*60)
        
        self.eeg_stream.start()
        self.is_running = True
        
        print("\n✓ Sistema listo. Iniciando interfaz BCI...")
        time.sleep(2)
        
        self.main_loop()
    
    def main_loop(self):
        """Loop principal de la aplicación"""
        
        while self.is_running:
            try:
                # 1. Seleccionar acción con P300
                action_idx = self.bci.run_p300_selection(self.eeg_stream)
                action = BCIConfig.MENU_OPTIONS[action_idx]
                
                if action == "Finalizar":
                    print("\n✓ Finalizando sesión...")
                    break
                
                # 2. Confirmar con Motor Imagery
                print(f"\n¿Ejecutar '{action}'?")
                confirmation = None
                while confirmation is None:
                    confirmation = self.bci.run_motor_imagery_confirmation(self.eeg_stream)
                
                if not confirmation:
                    print("✗ Acción cancelada\n")
                    continue
                
                # 3. Ejecutar acción
                self.execute_action(action)
                
            except KeyboardInterrupt:
                print("\n\n✓ Interrumpido por usuario")
                break
            except Exception as e:
                print(f"\n✗ Error: {e}")
                continue
        
        self.stop()
    
    def execute_action(self, action):
        """Ejecuta la acción seleccionada"""
        print(f"\n>>> Ejecutando: {action}")
        
        # Aquí podrías usar síntesis de voz para leer prompts predefinidos
        # o un teclado virtual controlado por BCI para escribir
        
        if action == "Hacer pregunta":
            prompt = "¿Cuál es la capital de Francia?"  # Pregunta de ejemplo
        elif action == "Continuar conversación":
            prompt = "Continúa con el tema anterior"
        elif action == "Resumir respuesta":
            prompt = "Resume la respuesta anterior en una frase"
        elif action == "Explicar más simple":
            prompt = "Explícalo como si tuviera 10 años"
        elif action == "Dar ejemplo":
            prompt = "Dame un ejemplo práctico"
        else:
            prompt = action
        
        print(f"\n📤 Enviando: {prompt}")
        response = self.chatgpt.send_prompt(prompt)
        print(f"\n📥 ChatGPT responde:\n{response}\n")
        
        # Aquí podrías usar text-to-speech para leer la respuesta
        time.sleep(2)
    
    def stop(self):
        """Detiene la aplicación"""
        self.is_running = False
        self.eeg_stream.stop()
        print("\n✓ Sistema detenido")

# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == "__main__":
    # Para usar con API real, proporciona tu key:
    # app = BrainChatGPT(api_key="tu-api-key-aqui")
    
    # Modo demo (sin API key):
    app = BrainChatGPT()
    
    try:
        app.start()
    except Exception as e:
        print(f"\n✗ Error fatal: {e}")
