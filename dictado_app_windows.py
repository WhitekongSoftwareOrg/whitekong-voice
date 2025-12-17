#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                      WHITEKONG VOICE - WINDOWS GUI                            ║
║                     Transcripción de voz para Windows                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

Aplicación con interfaz gráfica y bandeja del sistema para dictado por voz.
Usa Ctrl+Alt para grabar y transcribir.
"""

import os
import sys
import tempfile
import time
import threading
import queue
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
from pathlib import Path
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN GLOBAl
# ══════════════════════════════════════════════════════════════════════════════

CONFIG_FILE = os.path.expanduser("~/.whitekong_voice_config")

# API Keys por defecto
DEFAULT_GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
DEFAULT_GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Configuración de audio
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"

# Cola para logs thread-safe
log_queue = queue.Queue()

def log_print(msg):
    """Envía mensajes a la cola de logs y a stdout."""
    print(msg)
    log_queue.put(str(msg))

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
                log_print(f"Error cargando config: {e}")
    
    def save(self):
        """Guarda la configuración en el archivo."""
        try:
            with open(CONFIG_FILE, 'w') as f:
                f.write(f"provider={self.provider}\n")
                f.write(f"google_api_key={self.google_api_key}\n")
                f.write(f"groq_api_key={self.groq_api_key}\n")
        except Exception as e:
            log_print(f"Error guardando config: {e}")


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
    
    prompt = "Transcribe el audio fielmente. Corrige puntuación. No añadas explicaciones. Solo devuelve el texto."
    
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
        log_print(f"Error de transcripción: {e}")
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



class CustomInputDialog(tk.Toplevel):
    def __init__(self, parent, title, prompt, initial_value=""):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x150")
        self.resizable(False, False)
        self.result = None
        
        # Center window
        x = parent.winfo_rootx() + 50
        y = parent.winfo_rooty() + 50
        self.geometry(f"+{x}+{y}")
        
        # UI
        self.configure(bg="#2d2d2d")
        
        tk.Label(self, text=prompt, bg="#2d2d2d", fg="white", font=("Segoe UI", 10)).pack(pady=10, padx=20, anchor="w")
        
        self.entry = tk.Entry(self, bg="#3d3d3d", fg="white", insertbackground="white", font=("Consolas", 10))
        self.entry.pack(fill="x", padx=20, pady=5)
        self.entry.insert(0, initial_value)
        self.entry.select_range(0, tk.END)
        self.entry.focus_set()
        
        btn_frame = tk.Frame(self, bg="#2d2d2d")
        btn_frame.pack(fill="x", pady=15, padx=20)
        
        tk.Button(btn_frame, text="Cancelar", command=self.cancel, bg="#444", fg="white", relief="flat", padx=10).pack(side="right", padx=5)
        tk.Button(btn_frame, text="Guardar", command=self.ok, bg="#4CAF50", fg="white", relief="flat", padx=10).pack(side="right", padx=5)
        
        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.cancel())
        
        # Modal
        self.transient(parent)
        self.grab_set()
        parent.wait_window(self)

    def ok(self):
        self.result = self.entry.get()
        self.destroy()

    def cancel(self):
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# INTERFAZ GRÁFICA (Tkinter)
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow:
    def __init__(self, root, app_controller):
        self.root = root
        self.app = app_controller
        self.root.title("WhiteKong Voice")
        self.root.geometry("500x400")
        
        # Interceptar el cierre para minimizar
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        # Estilos
        bg_color = "#1e1e1e"
        fg_color = "#ffffff"
        self.root.configure(bg=bg_color)
        
        # Header
        header_frame = tk.Frame(root, bg=bg_color)
        header_frame.pack(fill="x", padx=10, pady=10)
        
        title_label = tk.Label(header_frame, text="🎤 WhiteKong Voice", font=("Segoe UI", 16, "bold"), bg=bg_color, fg=fg_color)
        title_label.pack(side="left")
        
        this_version = tk.Label(header_frame, text="v1.1", font=("Segoe UI", 10), bg=bg_color, fg="#888888")
        this_version.pack(side="right", anchor="s")

        # Status
        self.status_label = tk.Label(root, text="🟢 Listo (Ctrl+Alt para grabar)", font=("Segoe UI", 11), bg=bg_color, fg="#4CAF50")
        self.status_label.pack(pady=5)
        
        # Controls
        controls_frame = tk.Frame(root, bg=bg_color)
        controls_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Button(controls_frame, text="⚙️ Groq Key", command=self.config_groq, bg="#333333", fg="white", relief="flat", padx=10).pack(side="left", padx=5)
        tk.Button(controls_frame, text="⚙️ Google Key", command=self.config_google, bg="#333333", fg="white", relief="flat", padx=10).pack(side="left", padx=5)
        tk.Button(controls_frame, text="Limpiar Log", command=self.clear_log, bg="#333333", fg="white", relief="flat", padx=10).pack(side="right", padx=5)

        # Console Log
        log_frame = tk.Frame(root, bg=bg_color)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, bg="#2d2d2d", fg="#cccccc", font=("Consolas", 9), state='disabled')
        self.log_text.pack(fill="both", expand=True)
        
        # Iniciar polling de logs
        self.check_log_queue()

    def hide_window(self):
        self.root.withdraw()
        if not self.app.tray_icon_visible:
            self.app.show_tray_notification("Minimizado", "La aplicación sigue ejecutándose en segundo plano.")

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def update_status(self, text, color):
        self.status_label.config(text=text, fg=color)

    def append_log(self, text):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def clear_log(self):
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')

    def check_log_queue(self):
        while not log_queue.empty():
            try:
                msg = log_queue.get_nowait()
                self.append_log(msg)
            except queue.Empty:
                pass
        self.root.after(100, self.check_log_queue)

    def config_groq(self):
        dialog = CustomInputDialog(self.root, "Configurar Groq API Key", "Introduce tu API Key de Groq:", self.app.config.groq_api_key)
        if dialog.result is not None:
            self.app.config.groq_api_key = dialog.result.strip()
            self.app.config.provider = "GROQ"
            self.app.config.save()
            log_print("API Key de Groq actualizada.")

    def config_google(self):
        dialog = CustomInputDialog(self.root, "Configurar Google API Key", "Introduce tu API Key de Google:", self.app.config.google_api_key)
        if dialog.result is not None:
            self.app.config.google_api_key = dialog.result.strip()
            self.app.config.provider = "GOOGLE"
            self.app.config.save()
            log_print("API Key de Google actualizada.")


# ══════════════════════════════════════════════════════════════════════════════
# CONTROLADOR PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class VoiceAppController:
    def __init__(self):
        self.config = Config()
        self.recording = False
        self.recorder = None
        self.keyboard_listener = None
        self.tray_icon = None
        self.gui = None
        self.tray_icon_visible = True
        
        # Teclas
        self.ctrl_pressed = False
        self.alt_pressed = False

    def set_gui(self, gui):
        self.gui = gui
        log_print(f"WhiteKong Voice iniciado. Proveedor actual: {self.config.provider}")
        log_print("Presiona Ctrl + Alt para grabar.")

    def start_recording(self):
        self.recording = True
        if self.gui:
            self.gui.update_status("🔴 Grabando...", "#f44336")
        self.recorder = AudioRecorder()
        self.recorder.start_recording()
        log_print("Iniciando grabación...")
        if self.tray_icon:
            self.tray_icon.icon = self.create_icon("red")

    def stop_recording(self):
        if not self.recording:
            return
        
        self.recording = False
        if self.gui:
            self.gui.update_status("⏳ Procesando...", "#ffc107")
        if self.tray_icon:
            self.tray_icon.icon = self.create_icon("yellow")
        log_print("Procesando audio...")
        
        def process():
            try:
                if self.recorder:
                    ruta_audio = self.recorder.stop_recording()
                    self.recorder = None
                    
                    if ruta_audio:
                        log_print("Audio capturado. Transcribiendo...")
                        texto = transcribir_audio(ruta_audio, self.config)
                        
                        if texto:
                            escribir_texto(texto)
                            log_print(f"✅ Transcripción: {texto}")
                        else:
                            log_print("⚠️ No se pudo transcribir o audio vacío.")
            except Exception as e:
                log_print(f"Error procesando: {e}")
            finally:
                if self.gui:
                    self.gui.root.after(0, lambda: self.gui.update_status("🟢 Listo", "#4CAF50"))
                if self.tray_icon:
                    self.tray_icon.icon = self.create_icon("green")
                log_print("Listo.")
        
        threading.Thread(target=process, daemon=True).start()

    def start_keyboard_listener(self):
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
            except Exception:
                pass
        
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
            except Exception:
                pass
        
        self.keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.keyboard_listener.start()

    # --- Tray Icon Support ---
    def create_icon(self, color: str):
        from PIL import Image, ImageDraw
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        colors = {"green": (76, 175, 80, 255), "red": (244, 67, 54, 255), "yellow": (255, 193, 7, 255)}
        fill_color = colors.get(color, colors["green"])
        draw.ellipse([4, 4, size-4, size-4], fill=fill_color)
        mic_color = (255, 255, 255, 255)
        draw.rounded_rectangle([24, 16, 40, 38], radius=6, fill=mic_color)
        draw.arc([20, 28, 44, 48], start=0, end=180, fill=mic_color, width=3)
        draw.line([32, 48, 32, 52], fill=mic_color, width=3)
        draw.line([26, 52, 38, 52], fill=mic_color, width=3)
        return image

    def setup_tray(self):
        import pystray
        
        def on_open_click(icon, item):
            if self.gui:
                self.gui.root.after(0, self.gui.show_window)

        def on_quit_click(icon, item):
            self.quit_app()

        menu = pystray.Menu(
            pystray.MenuItem("Abrir ventana", on_open_click, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", on_quit_click)
        )
        
        self.tray_icon = pystray.Icon("name", self.create_icon("green"), "WhiteKong Voice", menu)
        self.tray_icon.run() # This blocks the thread it runs in

    def show_tray_notification(self, title, msg):
        if self.tray_icon:
            # Pystray no tiene notificaciones nativas directas consistentes en todas las versiones,
            # pero intentamos notify si existe, sino pass
            try:
                self.tray_icon.notify(msg, title)
            except:
                pass

    def quit_app(self):
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        if self.gui:
            self.gui.root.quit()
        sys.exit(0)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Asegurar una sola instancia (básico)
    # ... (omitido para simplificar)

    app_controller = VoiceAppController()
    
    # Iniciar listener de teclado
    app_controller.start_keyboard_listener()

    # Iniciar Tray Icon en hilo separado
    threading.Thread(target=app_controller.setup_tray, daemon=True).start()

    # Iniciar GUI (Main Thread)
    root = tk.Tk()
    # Icono de ventana si es posible
    # root.iconbitmap("icon.ico") 
    
    gui = MainWindow(root, app_controller)
    app_controller.set_gui(gui)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app_controller.quit_app()
