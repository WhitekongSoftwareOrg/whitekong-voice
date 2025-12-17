#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           WHITEKONG VOICE - MENU BAR APP                      ║
║                     Transcripción de voz para macOS                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

Aplicación de barra de menú para dictado por voz.
Usa Ctrl+Option para grabar y transcribir.
"""

import os
import sys
import tempfile
import time
import threading
import queue
from pathlib import Path
from typing import Optional
from datetime import datetime
from collections import deque

import rumps

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════

CONFIG_FILE = os.path.expanduser("~/.dictado_config")

# API Keys por defecto (vacías - el usuario debe configurarlas)
DEFAULT_GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
DEFAULT_GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Configuración de audio
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"

# Logs
LOG_MAX_ENTRIES = 100
log_buffer = deque(maxlen=LOG_MAX_ENTRIES)

def log(message: str):
    """Añade un mensaje al buffer de logs."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {message}"
    log_buffer.append(entry)
    print(entry)  # También imprimir en consola


# ══════════════════════════════════════════════════════════════════════════════
# CLASE DE CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════

class Config:
    """Gestiona la configuración de la aplicación."""
    
    def __init__(self):
        self.provider = "GROQ"  # Default: GROQ es más rápido
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
            prefix="dictado_"
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
# APLICACIÓN DE BARRA DE MENÚ
# ══════════════════════════════════════════════════════════════════════════════

class WhiteKongVoiceApp(rumps.App):
    """Aplicación de barra de menú para dictado por voz."""
    
    def __init__(self):
        super().__init__(
            "🎤",
            title="🎤",
            quit_button=None  # Personalizaremos el botón de salir
        )
        
        self.config = Config()
        self.active = True
        self.recording = False
        self.recorder = None
        self.keyboard_listener = None
        
        # Estado de teclas
        self.ctrl_pressed = False
        self.alt_pressed = False
        
        # Construir menú
        self.build_menu()
        
        # Cola para actualizaciones de UI thread-safe
        self.ui_queue = queue.Queue()
        
        # Timer para procesar la cola de UI (cada 0.1s)
        self.ui_timer = rumps.Timer(self.process_ui_queue, 0.1)
        self.ui_timer.start()
        
        # Iniciar listener de teclado
        self.start_keyboard_listener()
    
    def process_ui_queue(self, _):
        """Procesa las actualizaciones de UI en el hilo principal."""
        try:
            while not self.ui_queue.empty():
                action, args = self.ui_queue.get_nowait()
                
                if action == 'title':
                    self.title = args
                elif action == 'notification':
                    title, subtitle, message = args
                    rumps.notification(title, subtitle, message)
        except queue.Empty:
            pass
    
    def build_menu(self):
        """Construye el menú de la aplicación."""
        # Estado
        self.status_item = rumps.MenuItem("✅ Activo - Ctrl+Option para grabar")
        
        # Selector de proveedor
        self.provider_groq = rumps.MenuItem(
            "⚡ Groq (Whisper) - Rápido",
            callback=self.select_groq
        )
        self.provider_google = rumps.MenuItem(
            "🧠 Google Gemini",
            callback=self.select_google
        )
        
        # Marcar el proveedor actual
        self.update_provider_marks()
        
        # Menú de configuración de API Keys
        self.config_menu = rumps.MenuItem("⚙️ Configurar API Keys")
        self.config_menu.add(rumps.MenuItem("Configurar Groq API Key...", callback=self.config_groq_key))
        self.config_menu.add(rumps.MenuItem("Configurar Google API Key...", callback=self.config_google_key))
        
        # Botón ver logs
        logs_button = rumps.MenuItem("📋 Ver logs", callback=self.show_logs)
        
        # Botón de salir
        quit_button = rumps.MenuItem("❌ Salir", callback=self.quit_app)
        
        # Construir menú completo
        self.menu = [
            self.status_item,
            None,  # Separador
            rumps.MenuItem("🔊 Proveedor de IA:"),
            self.provider_groq,
            self.provider_google,
            None,  # Separador
            self.config_menu,
            logs_button,
            None,  # Separador
            quit_button
        ]
    
    def update_provider_marks(self):
        """Actualiza las marcas de verificación en el menú."""
        if self.config.provider == "GROQ":
            self.provider_groq.state = 1  # Checked
            self.provider_google.state = 0
        else:
            self.provider_groq.state = 0
            self.provider_google.state = 1  # Checked
    
    def select_groq(self, sender):
        """Selecciona Groq como proveedor."""
        self.config.provider = "GROQ"
        self.config.save()
        self.update_provider_marks()
        rumps.notification(
            title="WhiteKong Voice",
            subtitle="Proveedor cambiado",
            message="Ahora usando Groq (Whisper) ⚡"
        )
    
    def select_google(self, sender):
        """Selecciona Google como proveedor."""
        self.config.provider = "GOOGLE"
        self.config.save()
        self.update_provider_marks()
        rumps.notification(
            title="WhiteKong Voice",
            subtitle="Proveedor cambiado",
            message="Ahora usando Google Gemini 🧠"
        )
    
    def config_groq_key(self, sender):
        """Configura la API Key de Groq."""
        response = rumps.Window(
            title="Configurar Groq API Key",
            message="Introduce tu API Key de Groq:",
            default_text=self.config.groq_api_key if self.config.groq_api_key else "",
            ok="Guardar",
            cancel="Cancelar",
            dimensions=(400, 24)
        ).run()
        
        if response.clicked:
            self.config.groq_api_key = response.text.strip()
            self.config.save()
            rumps.notification("WhiteKong Voice", "API Key guardada", "Groq API Key actualizada ✅")
    
    def config_google_key(self, sender):
        """Configura la API Key de Google."""
        response = rumps.Window(
            title="Configurar Google API Key",
            message="Introduce tu API Key de Google:",
            default_text=self.config.google_api_key if self.config.google_api_key else "",
            ok="Guardar",
            cancel="Cancelar",
            dimensions=(400, 24)
        ).run()
        
        if response.clicked:
            self.config.google_api_key = response.text.strip()
            self.config.save()
            rumps.notification("WhiteKong Voice", "API Key guardada", "Google API Key actualizada ✅")
    
    def show_logs(self, sender):
        """Muestra los logs en un archivo de texto."""
        import subprocess
        
        log_file = "/tmp/whitekong_voice_logs.txt"
        
        if not log_buffer:
            logs_text = "No hay logs disponibles."
        else:
            logs_text = "📋 LOGS DE WHITEKONG VOICE\n"
            logs_text += "=" * 50 + "\n\n"
            logs_text += "\n".join(log_buffer)
        
        with open(log_file, 'w') as f:
            f.write(logs_text)
        
        subprocess.run(["open", log_file])
    
    def start_keyboard_listener(self):
        """Inicia el listener de teclado en un hilo separado."""
        from pynput import keyboard
        from pynput.keyboard import Key
        
        def on_press(key):
            try:
                if key == Key.ctrl or key == Key.ctrl_l or key == Key.ctrl_r:
                    self.ctrl_pressed = True
                elif key == Key.alt or key == Key.alt_l or key == Key.alt_r:
                    self.alt_pressed = True
                
                if self.ctrl_pressed and self.alt_pressed and not self.recording and self.active:
                    self.start_recording()
            except Exception as e:
                print(f"Error on_press: {e}")
        
        def on_release(key):
            try:
                if key == Key.ctrl or key == Key.ctrl_l or key == Key.ctrl_r:
                    self.ctrl_pressed = False
                    if self.recording:
                        self.stop_recording()
                elif key == Key.alt or key == Key.alt_l or key == Key.alt_r:
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
        log("🔴 Iniciando grabación...")
        self.recording = True
        self.ui_queue.put(('title', "🔴"))  # Update UI thread-safe
        self.recorder = AudioRecorder()
        self.recorder.start_recording()
    
    def stop_recording(self):
        """Detiene la grabación y transcribe."""
        if not self.recording:
            return
        
        log("⏳ Deteniendo grabación, procesando...")
        self.recording = False
        self.ui_queue.put(('title', "⏳"))  # Update UI thread-safe
        
        # Procesar en hilo separado para no bloquear la UI
        def process():
            try:
                if self.recorder:
                    ruta_audio = self.recorder.stop_recording()
                    self.recorder = None
                    
                    if ruta_audio:
                        log(f"📁 Audio guardado: {ruta_audio}")
                        log(f"🤖 Transcribiendo con {self.config.provider}...")
                        texto = transcribir_audio(ruta_audio, self.config)
                        
                        if texto:
                            log(f"✅ Transcrito: {texto[:50]}...")
                            escribir_texto(texto)
                        else:
                            log("❌ Error: No se pudo transcribir")
                            self.ui_queue.put(('notification', (
                                "WhiteKong Voice",
                                "Error",
                                "No se pudo transcribir el audio"
                            )))
                    else:
                        log("⚠️ No se grabó audio")
            except Exception as e:
                log(f"❌ Error procesando: {e}")
                self.ui_queue.put(('notification', ("WhiteKong Voice", "Error", str(e))))
            finally:
                self.ui_queue.put(('title', "🎤"))  # Restaurar icono thread-safe
        
        threading.Thread(target=process, daemon=True).start()
    
    def quit_app(self, sender):
        """Cierra la aplicación."""
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        rumps.quit_application()


# ══════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════════════════

def hide_dock_icon():
    """Oculta el icono del Dock en macOS (app se comporta como 'agent')."""
    try:
        import objc
        from Foundation import NSBundle
        info = NSBundle.mainBundle().infoDictionary()
        info["LSBackgroundOnly"] = "1"
    except Exception:
        pass  # Silenciosamente ignorar si falla


if __name__ == "__main__":
    # Ocultar icono del Dock
    hide_dock_icon()
    
    print("🎤 WhiteKong Voice - Iniciando aplicación de barra de menú...")
    print("   Usa Ctrl + Option para grabar")
    print("   Click en el icono 🎤 de la barra de menú para opciones")
    print()
    
    try:
        app = WhiteKongVoiceApp()
        app.run()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

