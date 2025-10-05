
# 🧠 BCI Chat Interface with Groq (Tkinter & EEG)

**Proyecto del Hackathon – “DECUVE: Conecta tu cabeza con la IA”**

## 🚀 Descripción

**BCI Chat Interface with Groq** es una prueba de concepto para crear una interfaz de comunicación alternativa (BCI) utilizando la biblioteca **Tkinter** para la UI, simulación de señales cerebrales (o un dispositivo EEG como Unicorn Hybrid Black) y el modelo de lenguaje **Groq** para generar contenido.

El objetivo es simular un sistema de comunicación asistida donde el usuario puede interactuar con una IA avanzada:
1.  **Tecleando** letra por letra (Speller).
2.  **Seleccionando preguntas** y conceptos sugeridos por la IA (Graph).

La interacción simula la selección por **atención o permanencia** de 3 segundos, ideal para personas con movilidad reducida.

---

## ⚙️ Especificaciones de Software y Dependencias

| Componente | Uso Principal | Instalación (Python) |
| :--- | :--- | :--- |
| **Tkinter** | Interfaz Gráfica (GUI) | (Incluido en Python) |
| **Groq SDK** | Interacción con modelos de lenguaje (Llama 3.3) | `pip install groq` |
| **Pylsl** (Opcional) | Adquisición de datos de EEG/Marcadores (LSL) | `pip install pylsl` |
| **Threading** | Ejecución de tareas de IA y simulación en segundo plano. | (Librería estándar) |

### ⚠️ Modo de Funcionamiento (Debug vs. Real)

El código incluye un **modo Debug (simulación)** por defecto que:
1.  Simula la lectura de EEG con **datos aleatorios**.
2.  Simula la selección de botones (clics) de la interfaz cada **1.2 segundos**.

Para el uso con hardware real (como Unicorn Hybrid Black), se requiere la configuración de las librerías EEG y la implementación de una función `detect_p300` efectiva.

---

## 🧩 Flujo del Sistema

El programa opera en dos modos de entrada principales, con la generación de contenido a cargo de Groq:

### 1. Modo Speller (Teclado Virtual)
* Muestra un **grid de caracteres** (letras, números, puntuación).
* El usuario "selecciona" caracteres para escribir una palabra clave en el campo de texto.
* En modo Debug, un botón aleatorio es "seleccionado" automáticamente.

### 2. Modo Graph (Navegación por Preguntas Sugeridas)
* El usuario introduce **palabras clave**.
* El programa utiliza el modelo **Llama 3.3 de Groq** para generar una lista de **preguntas cortas** sobre los temas introducidos.
* El usuario selecciona una pregunta de la lista.
* La pregunta seleccionada se envía al chat de la IA para obtener una respuesta detallada.

### 3. Interacción con Groq API
* Todas las sugerencias de preguntas (`Generar Preguntas`) y las respuestas finales (`Enviar esta pregunta al Chat`) son procesadas por la API de Groq, optimizada para la velocidad.
* Se mantiene un **historial de conversación** para que la IA dé respuestas contextuales.

---

## 🔑 Configuración de la API

La API Key de Groq se puede configurar de tres maneras (la opción 1 es la predeterminada en el archivo `main.py`):
1.  **Directamente en el código** (Variable `GROQ_API_KEY`).
2.  Mediante un archivo `key.ini` (comentado por defecto).
3.  Mediante una variable de entorno.

También se puede configurar directamente desde el **botón "Configurar API Key"** en la interfaz.

---

## 💡 Posibles Aplicaciones

* **Accesibilidad y Comunicación Alternativa:** Permitir a personas con discapacidades motoras generar preguntas y comunicarse con una IA de manera más eficiente que la escritura letra por letra.
* **Investigación BCI:** Plataforma de prueba y desarrollo para la integración de señales cerebrales (P300 o SSVEP) en interfaces conversacionales.
* **Generación de Contenido Rápida:** Obtener un árbol de preguntas sobre un tema para explorar conceptos de manera guiada.

---


