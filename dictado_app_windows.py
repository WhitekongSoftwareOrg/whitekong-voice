#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                      WHITEKONG VOICE - WINDOWS SYSTEM TRAY                    ║
║                     Transcripción de voz para Windows                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

Aplicación de bandeja del sistema para dictado por voz en Windows.
Usa Ctrl+Alt para grabar y transcribir.
"""

import os
import sys
import tempfile
import time
import threading
from pathlib import Path
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════

CONFIG_FILE = os.path.expanduser("~/.whitekong_voice_config")

# API Keys por defecto (vacías - el usuario debe configurarlas)
DEFAULT_GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
DEFAULT_GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Configuración de audio
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"


# ══════════════════════════════════════════════════════════════════════════════
# CLASE DE CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════

class Config:
    """Gestiona la configuración de la aplicación."""
    
    def __init__(self):
        self.provider = "GROQ"
        self.google_api_key = DEFAULT_GOOGLE_API_KEY
        self.groq_api_key = DEFAULT_GROQ_API_KEY
        self.load()
    
    def load(self):
        """Carga la configuración del archivo."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line:
                            key, value = line.split('=', 1)
                            if key == 'provider':
                                self.provider = value
                            elif key == 'google_api_key':
                                self.google_api_key = value
                            elif key == 'groq_api_key':
                                self.groq_api_key = value
            except Exception as e:
                print(f"Error cargando config: {e}")
    
    def save(self):
        """Guarda la configuración en el archivo."""
        try:
            with open(CONFIG_FILE, 'w') as f:
                f.write(f"provider={self.provider}\n")
                f.write(f"google_api_key={self.google_api_key}\n")
                f.write(f"groq_api_key={self.groq_api_key}\n")
        except Exception as e:
            print(f"Error guardando config: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# GRABADOR DE AUDIO
# ══════════════════════════════════════════════════════════════════════════════

class AudioRecorder:
    """Gestiona la grabación de audio del micrófono."""
    
    def __init__(self):
        import sounddevice as sd
        import numpy as np
        
        self.sample_rate = SAMPLE_RATE
        self.channels = CHANNELS
        self.recording = False
        self.audio_data = []
        self.stream = None
        self._lock = threading.Lock()
        self.sd = sd
        self.np = np
    
    def _audio_callback(self, indata, frames, time_info, status):
        with self._lock:
            if self.recording:
                self.audio_data.append(indata.copy())
    
    def start_recording(self):
        with self._lock:
            self.audio_data = []
            self.recording = True
        
        self.stream = self.sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=DTYPE,
            callback=self._audio_callback,
            blocksize=1024
        )
        self.stream.start()
    
    def stop_recording(self) -> Optional[str]:
        with self._lock:
            self.recording = False
        
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        with self._lock:
            if not self.audio_data:
                return None
            audio_array = self.np.concatenate(self.audio_data, axis=0)
        
        return self._save_to_wav(audio_array)
    
    def _save_to_wav(self, audio_array) -> str:
        from scipy.io import wavfile
        
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
            prefix="whitekong_voice_"
        )
        temp_path = temp_file.name
        temp_file.close()
        
        wavfile.write(temp_path, self.sample_rate, audio_array)
        return temp_path


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE TRANSCRIPCIÓN
# ══════════════════════════════════════════════════════════════════════════════

def transcribir_con_google(ruta_archivo: str, api_key: str) -> Optional[str]:
    """Transcribe audio usando Google Gemini."""
    import google.generativeai as genai
    
    genai.configure(api_key=api_key)
    audio_file = genai.upload_file(ruta_archivo)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    prompt = """Transcribe el audio fielmente. 
Corrige puntuación. 
No añadas explicaciones. 
Solo devuelve el texto."""
    
    response = model.generate_content([prompt, audio_file])
    
    try:
        audio_file.delete()
    except:
        pass
    
    return response.text.strip() if response.text else None


def transcribir_con_groq(ruta_archivo: str, api_key: str) -> Optional[str]:
    """Transcribe audio usando Groq (Whisper)."""
    from groq import Groq
    
    client = Groq(api_key=api_key)
    
    with open(ruta_archivo, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=(Path(ruta_archivo).name, audio_file.read()),
            model="whisper-large-v3",
            language="es",
            response_format="text"
        )
    
    return transcription.strip() if transcription else None


def transcribir_audio(ruta_archivo: str, config: Config) -> Optional[str]:
    """Transcribe un archivo de audio usando el proveedor configurado."""
    try:
        if config.provider == "GOOGLE":
            return transcribir_con_google(ruta_archivo, config.google_api_key)
        else:
            return transcribir_con_groq(ruta_archivo, config.groq_api_key)
    except Exception as e:
        print(f"Error de transcripción: {e}")
        return None
    finally:
        try:
            if ruta_archivo and os.path.exists(ruta_archivo):
                os.unlink(ruta_archivo)
        except:
            pass


def escribir_texto(texto: str):
    """Escribe texto simulando pulsaciones de teclado."""
    from pynput.keyboard import Controller
    
    if not texto:
        return
    
    time.sleep(0.2)
    keyboard = Controller()
    keyboard.type(texto)


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGOS DE WINDOWS
# ══════════════════════════════════════════════════════════════════════════════

def show_input_dialog(title: str, prompt: str, default_value: str = "") -> Optional[str]:
    """Muestra un diálogo de entrada usando tkinter."""
    import tkinter as tk
    from tkinter import simpledialog
    
    root = tk.Tk()
    root.withdraw()  # Ocultar ventana principal
    root.attributes('-topmost', True)  # Mantener en primer plano
    
    result = simpledialog.askstring(title, prompt, initialvalue=default_value, parent=root)
    root.destroy()
    
    return result


def show_notification(title: str, message: str):
    """Muestra una notificación del sistema en Windows."""
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=3, threaded=True)
    except ImportError:
        # Fallback: usar tkinter
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(title, message)
        root.destroy()
    except Exception:
        print(f"{title}: {message}")


# ══════════════════════════════════════════════════════════════════════════════
# APLICACIÓN DE BANDEJA DEL SISTEMA
# ══════════════════════════════════════════════════════════════════════════════

class WhiteKongVoiceApp:
    """Aplicación de bandeja del sistema para dictado por voz."""
    
    def __init__(self):
        import pystray
        from PIL import Image, ImageDraw
        
        self.pystray = pystray
        self.config = Config()
        self.recording = False
        self.recorder = None
        self.keyboard_listener = None
        self.icon = None
        
        # Estado de teclas
        self.ctrl_pressed = False
        self.alt_pressed = False
        
        # Crear icono
        self.icon_normal = self.create_icon("green")
        self.icon_recording = self.create_icon("red")
        self.icon_processing = self.create_icon("yellow")
        
        # Crear menú
        self.create_tray_icon()
    
    def create_icon(self, color: str) -> 'Image':
        """Crea un icono de micrófono simple."""
        from PIL import Image, ImageDraw
        
        # Crear imagen 64x64
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Colores
        colors = {
            "green": (76, 175, 80, 255),
            "red": (244, 67, 54, 255),
            "yellow": (255, 193, 7, 255)
        }
        fill_color = colors.get(color, colors["green"])
        
        # Dibujar círculo de fondo
        draw.ellipse([4, 4, size-4, size-4], fill=fill_color)
        
        # Dibujar micrófono simple (rectángulo + base)
        mic_color = (255, 255, 255, 255)
        # Cuerpo del micrófono
        draw.rounded_rectangle([24, 16, 40, 38], radius=6, fill=mic_color)
        # Base
        draw.arc([20, 28, 44, 48], start=0, end=180, fill=mic_color, width=3)
        # Línea vertical
        draw.line([32, 48, 32, 52], fill=mic_color, width=3)
        # Base horizontal
        draw.line([26, 52, 38, 52], fill=mic_color, width=3)
        
        return image
    
    def create_tray_icon(self):
        """Crea el icono de la bandeja del sistema."""
        menu = self.pystray.Menu(
            self.pystray.MenuItem(
                "✅ Activo - Ctrl+Alt para grabar",
                None,
                enabled=False
            ),
            self.pystray.Menu.SEPARATOR,
            self.pystray.MenuItem(
                "🔊 Proveedor de IA",
                self.pystray.Menu(
                    self.pystray.MenuItem(
                        "⚡ Groq (Whisper) - Rápido",
                        self.select_groq,
                        checked=lambda item: self.config.provider == "GROQ"
                    ),
                    self.pystray.MenuItem(
                        "🧠 Google Gemini",
                        self.select_google,
                        checked=lambda item: self.config.provider == "GOOGLE"
                    )
                )
            ),
            self.pystray.Menu.SEPARATOR,
            self.pystray.MenuItem(
                "⚙️ Configurar API Keys",
                self.pystray.Menu(
                    self.pystray.MenuItem(
                        "Configurar Groq API Key...",
                        self.config_groq_key
                    ),
                    self.pystray.MenuItem(
                        "Configurar Google API Key...",
                        self.config_google_key
                    )
                )
            ),
            self.pystray.Menu.SEPARATOR,
            self.pystray.MenuItem("❌ Salir", self.quit_app)
        )
        
        self.icon = self.pystray.Icon(
            "WhiteKong Voice",
            self.icon_normal,
            "WhiteKong Voice - Ctrl+Alt para grabar",
            menu
        )
    
    def select_groq(self, icon, item):
        """Selecciona Groq como proveedor."""
        self.config.provider = "GROQ"
        self.config.save()
        show_notification("WhiteKong Voice", "Ahora usando Groq (Whisper) ⚡")
    
    def select_google(self, icon, item):
        """Selecciona Google como proveedor."""
        self.config.provider = "GOOGLE"
        self.config.save()
        show_notification("WhiteKong Voice", "Ahora usando Google Gemini 🧠")
    
    def config_groq_key(self, icon, item):
        """Configura la API Key de Groq."""
        result = show_input_dialog(
            "Configurar Groq API Key",
            "Introduce tu API Key de Groq:",
            self.config.groq_api_key
        )
        if result:
            self.config.groq_api_key = result.strip()
            self.config.save()
            show_notification("WhiteKong Voice", "Groq API Key actualizada ✅")
    
    def config_google_key(self, icon, item):
        """Configura la API Key de Google."""
        result = show_input_dialog(
            "Configurar Google API Key",
            "Introduce tu API Key de Google:",
            self.config.google_api_key
        )
        if result:
            self.config.google_api_key = result.strip()
            self.config.save()
            show_notification("WhiteKong Voice", "Google API Key actualizada ✅")
    
    def start_keyboard_listener(self):
        """Inicia el listener de teclado."""
        from pynput import keyboard
        from pynput.keyboard import Key
        
        def on_press(key):
            try:
                if key == Key.ctrl_l or key == Key.ctrl_r:
                    self.ctrl_pressed = True
                elif key == Key.alt_l or key == Key.alt_r:
                    self.alt_pressed = True
                
                if self.ctrl_pressed and self.alt_pressed and not self.recording:
                    self.start_recording()
            except Exception as e:
                print(f"Error on_press: {e}")
        
        def on_release(key):
            try:
                if key == Key.ctrl_l or key == Key.ctrl_r:
                    self.ctrl_pressed = False
                    if self.recording:
                        self.stop_recording()
                elif key == Key.alt_l or key == Key.alt_r:
                    self.alt_pressed = False
                    if self.recording:
                        self.stop_recording()
            except Exception as e:
                print(f"Error on_release: {e}")
        
        self.keyboard_listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release
        )
        self.keyboard_listener.start()
    
    def start_recording(self):
        """Inicia la grabación."""
        self.recording = True
        if self.icon:
            self.icon.icon = self.icon_recording
        self.recorder = AudioRecorder()
        self.recorder.start_recording()
        print("🔴 Grabando...")
    
    def stop_recording(self):
        """Detiene la grabación y transcribe."""
        if not self.recording:
            return
        
        self.recording = False
        if self.icon:
            self.icon.icon = self.icon_processing
        print("⏳ Procesando...")
        
        def process():
            try:
                if self.recorder:
                    ruta_audio = self.recorder.stop_recording()
                    self.recorder = None
                    
                    if ruta_audio:
                        texto = transcribir_audio(ruta_audio, self.config)
                        
                        if texto:
                            escribir_texto(texto)
                            print(f"✅ Transcrito: {texto[:50]}...")
                        else:
                            show_notification("WhiteKong Voice", "No se pudo transcribir el audio")
            except Exception as e:
                print(f"Error procesando: {e}")
                show_notification("WhiteKong Voice", f"Error: {str(e)}")
            finally:
                if self.icon:
                    self.icon.icon = self.icon_normal
                print("🟢 Listo")
        
        threading.Thread(target=process, daemon=True).start()
    
    def quit_app(self, icon, item):
        """Cierra la aplicación."""
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.icon:
            self.icon.stop()
    
    def run(self):
        """Ejecuta la aplicación."""
        print("🎤 WhiteKong Voice - Windows")
        print("   Usa Ctrl + Alt para grabar")
        print("   Click derecho en el icono de la bandeja para opciones")
        print()
        
        # Iniciar listener de teclado
        self.start_keyboard_listener()
        
        # Ejecutar el icono de la bandeja
        self.icon.run()


# ══════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        app = WhiteKongVoiceApp()
        app.run()
    except KeyboardInterrupt:
        print("\n👋 ¡Hasta luego!")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
