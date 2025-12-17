#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         DICTADO GLOBAL - WISPR FLOW CLONE                     ║
║                     Transcripción de voz agnóstica de proveedor               ║
╚══════════════════════════════════════════════════════════════════════════════╝

Autor: Arquitecto de Software Senior
Descripción: Script de dictado push-to-talk que transcribe audio usando
             Google Gemini o Groq, y escribe el texto donde esté el cursor.

Uso: python dictado_global.py
     Mantén pulsada Ctrl+Option para grabar, suelta para transcribir.
     Presiona ESC para salir.

Instalación de dependencias:
    pip install pynput sounddevice scipy google-generativeai groq numpy

Notas:
    - En macOS, necesitas dar permisos de Accesibilidad al terminal
      (Preferencias del Sistema → Privacidad y Seguridad → Accesibilidad)
"""

import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional
import threading

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN - MODIFICA ESTAS VARIABLES
# ══════════════════════════════════════════════════════════════════════════════

# Proveedor de IA: "GOOGLE" o "GROQ"
AI_PROVIDER: str = "GROQ"

# ══════════════════════════════════════════════════════════════════════════════
# API KEYS
# ══════════════════════════════════════════════════════════════════════════════

GOOGLE_API_KEY: str = os.environ.get("GOOGLE_API_KEY", "")
GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE AUDIO
# ══════════════════════════════════════════════════════════════════════════════

SAMPLE_RATE: int = 16000  # Hz - Óptimo para transcripción de voz
CHANNELS: int = 1         # Mono
DTYPE: str = "int16"      # Formato de audio

# ══════════════════════════════════════════════════════════════════════════════
# IMPORTS Y VALIDACIÓN DE DEPENDENCIAS
# ══════════════════════════════════════════════════════════════════════════════

def check_dependencies() -> bool:
    """Verifica que todas las dependencias estén instaladas."""
    missing = []
    
    try:
        import pynput
    except ImportError:
        missing.append("pynput")
    
    try:
        import sounddevice
    except ImportError:
        missing.append("sounddevice")
    
    try:
        import scipy
    except ImportError:
        missing.append("scipy")
    
    try:
        import numpy
    except ImportError:
        missing.append("numpy")
    
    if AI_PROVIDER == "GOOGLE":
        try:
            import google.generativeai
        except ImportError:
            missing.append("google-generativeai")
    
    if AI_PROVIDER == "GROQ":
        try:
            import groq
        except ImportError:
            missing.append("groq")
    
    if missing:
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║  ERROR: Faltan dependencias                                      ║")
        print("╚══════════════════════════════════════════════════════════════════╝")
        print(f"\nInstala las dependencias faltantes con:")
        print(f"  pip install {' '.join(missing)}")
        return False
    
    return True


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO DE GRABACIÓN DE AUDIO
# ══════════════════════════════════════════════════════════════════════════════

class AudioRecorder:
    """Gestiona la grabación de audio del micrófono."""
    
    def __init__(self, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS):
        import sounddevice as sd
        import numpy as np
        
        self.sample_rate = sample_rate
        self.channels = channels
        self.recording = False
        self.audio_data = []
        self.stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()
        self.sd = sd
        self.np = np
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback que se ejecuta para cada bloque de audio."""
        if status:
            print(f"⚠️  Estado del stream: {status}")
        
        with self._lock:
            if self.recording:
                self.audio_data.append(indata.copy())
    
    def start_recording(self):
        """Inicia la grabación de audio."""
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
        print("🎙️  Grabando... (mantén pulsadas las teclas)")
    
    def stop_recording(self) -> Optional[str]:
        """
        Detiene la grabación y guarda el audio en un archivo temporal.
        
        Returns:
            Ruta al archivo .wav temporal, o None si no hay audio.
        """
        with self._lock:
            self.recording = False
        
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        with self._lock:
            if not self.audio_data:
                print("⚠️  No se capturó audio.")
                return None
            
            # Concatenar todos los bloques de audio
            audio_array = self.np.concatenate(self.audio_data, axis=0)
        
        # Guardar en archivo temporal
        return self._save_to_wav(audio_array)
    
    def _save_to_wav(self, audio_array) -> str:
        """Guarda el array de audio en un archivo WAV temporal."""
        from scipy.io import wavfile
        
        # Crear archivo temporal
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
            prefix="dictado_"
        )
        temp_path = temp_file.name
        temp_file.close()
        
        # Escribir el archivo WAV
        wavfile.write(temp_path, self.sample_rate, audio_array)
        
        duration = len(audio_array) / self.sample_rate
        print(f"✅ Audio guardado: {duration:.1f}s")
        
        return temp_path


def grabar_audio() -> Optional[str]:
    """
    Función de conveniencia para grabar audio push-to-talk.
    
    Returns:
        Ruta al archivo .wav temporal con el audio grabado, o None si falla.
    """
    recorder = AudioRecorder()
    recorder.start_recording()
    return recorder


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO DE TRANSCRIPCIÓN
# ══════════════════════════════════════════════════════════════════════════════

def transcribir_con_google(ruta_archivo: str) -> Optional[str]:
    """
    Transcribe audio usando Google Gemini.
    
    Args:
        ruta_archivo: Ruta al archivo de audio .wav
        
    Returns:
        Texto transcrito o None si falla.
    """
    import google.generativeai as genai
    
    # Configurar la API
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # Cargar el archivo de audio
    print("📤 Enviando a Google Gemini...")
    
    # Subir el archivo de audio
    audio_file = genai.upload_file(ruta_archivo)
    
    # Configurar el modelo
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    # Prompt del sistema
    prompt = """Transcribe el audio fielmente. 
Corrige puntuación. 
No añadas explicaciones. 
Solo devuelve el texto."""
    
    # Generar la transcripción
    response = model.generate_content([prompt, audio_file])
    
    # Limpiar el archivo subido
    try:
        audio_file.delete()
    except Exception:
        pass  # Ignorar errores de limpieza
    
    return response.text.strip() if response.text else None


def transcribir_con_groq(ruta_archivo: str) -> Optional[str]:
    """
    Transcribe audio usando Groq (Whisper).
    
    Args:
        ruta_archivo: Ruta al archivo de audio .wav
        
    Returns:
        Texto transcrito o None si falla.
    """
    from groq import Groq
    
    # Crear cliente
    client = Groq(api_key=GROQ_API_KEY)
    
    print("📤 Enviando a Groq (Whisper)...")
    
    # Abrir el archivo de audio
    with open(ruta_archivo, "rb") as audio_file:
        # Usar el endpoint de transcripción de audio
        transcription = client.audio.transcriptions.create(
            file=(Path(ruta_archivo).name, audio_file.read()),
            model="whisper-large-v3",
            language="es",  # Español
            response_format="text"
        )
    
    return transcription.strip() if transcription else None


def transcribir_audio(ruta_archivo: str) -> Optional[str]:
    """
    Transcribe un archivo de audio usando el proveedor configurado.
    
    Esta función actúa como un dispatcher que selecciona el proveedor
    de IA según la configuración global AI_PROVIDER.
    
    Args:
        ruta_archivo: Ruta al archivo de audio .wav
        
    Returns:
        Texto transcrito o None si falla.
    """
    try:
        if AI_PROVIDER.upper() == "GOOGLE":
            return transcribir_con_google(ruta_archivo)
        elif AI_PROVIDER.upper() == "GROQ":
            return transcribir_con_groq(ruta_archivo)
        else:
            print(f"❌ Proveedor desconocido: {AI_PROVIDER}")
            print("   Usa 'GOOGLE' o 'GROQ'")
            return None
            
    except Exception as e:
        print(f"❌ Error de transcripción: {type(e).__name__}")
        print(f"   {str(e)}")
        return None
    finally:
        # Limpiar el archivo temporal
        try:
            if ruta_archivo and os.path.exists(ruta_archivo):
                os.unlink(ruta_archivo)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO DE ESCRITURA DE TEXTO
# ══════════════════════════════════════════════════════════════════════════════

def escribir_texto(texto: str):
    """
    Escribe texto simulando pulsaciones de teclado usando pynput.
    
    Args:
        texto: El texto a escribir
    """
    from pynput.keyboard import Controller
    
    if not texto:
        return
    
    print(f"⌨️  Escribiendo: {texto[:50]}{'...' if len(texto) > 50 else ''}")
    
    # Pequeña pausa antes de escribir para evitar interferencias
    time.sleep(0.2)
    
    keyboard = Controller()
    keyboard.type(texto)
    
    print("✅ Texto escrito correctamente")


# ══════════════════════════════════════════════════════════════════════════════
# BUCLE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def mostrar_banner():
    """Muestra el banner de inicio."""
    banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ██████╗ ██╗ ██████╗████████╗ █████╗ ██████╗  ██████╗                       ║
║   ██╔══██╗██║██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██╔═══██╗                      ║
║   ██║  ██║██║██║        ██║   ███████║██║  ██║██║   ██║                      ║
║   ██║  ██║██║██║        ██║   ██╔══██║██║  ██║██║   ██║                      ║
║   ██████╔╝██║╚██████╗   ██║   ██║  ██║██████╔╝╚██████╔╝                      ║
║   ╚═════╝ ╚═╝ ╚═════╝   ╚═╝   ╚═╝  ╚═╝╚═════╝  ╚═════╝                       ║
║                                                                              ║
║                    🎤 GLOBAL VOICE DICTATION 🎤                              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    print(banner)


def mostrar_configuracion():
    """Muestra la configuración actual."""
    print("┌──────────────────────────────────────────────────────────────────┐")
    print(f"│  🤖 Proveedor: {AI_PROVIDER.upper():50} │")
    print(f"│  ⌨️  Tecla:     {'CTRL + OPTION':50} │")
    print("├──────────────────────────────────────────────────────────────────┤")
    print("│  📋 Instrucciones:                                               │")
    print("│     • Mantén CTRL + OPTION pulsadas para grabar                  │")
    print("│     • Suelta para transcribir                                    │")
    print("│     • El texto se escribirá donde esté el cursor                 │")
    print("│     • Presiona CTRL + C para salir                               │")
    print("└──────────────────────────────────────────────────────────────────┘")
    print()


def verificar_api_keys() -> bool:
    """Verifica que las API keys estén configuradas."""
    if AI_PROVIDER.upper() == "GOOGLE":
        if not GOOGLE_API_KEY or "TU_API_KEY" in GOOGLE_API_KEY:
            print("❌ Error: GOOGLE_API_KEY no está configurada")
            return False
    
    if AI_PROVIDER.upper() == "GROQ":
        if not GROQ_API_KEY or "TU_API_KEY" in GROQ_API_KEY:
            print("❌ Error: GROQ_API_KEY no está configurada")
            return False
    
    return True


def main():
    """Punto de entrada principal del script."""
    from pynput import keyboard
    from pynput.keyboard import Key
    
    mostrar_banner()
    
    # Verificar dependencias
    if not check_dependencies():
        sys.exit(1)
    
    # Verificar API keys
    if not verificar_api_keys():
        sys.exit(1)
    
    mostrar_configuracion()
    
    print("🟢 Sistema listo. Esperando entrada de voz...")
    print()
    
    # Estado
    estado = {
        'ctrl_pressed': False,
        'alt_pressed': False,
        'grabando': False,
        'recorder': None
    }
    
    def check_hotkey_pressed():
        """Verifica si ambas teclas del hotkey están presionadas."""
        return estado['ctrl_pressed'] and estado['alt_pressed']
    
    def iniciar_grabacion():
        """Inicia la grabación de audio."""
        if estado['grabando']:
            return
        
        estado['grabando'] = True
        estado['recorder'] = AudioRecorder()
        estado['recorder'].start_recording()
    
    def detener_y_transcribir():
        """Detiene la grabación y transcribe."""
        if not estado['grabando']:
            return
        
        estado['grabando'] = False
        recorder = estado['recorder']
        estado['recorder'] = None
        
        if recorder:
            ruta_audio = recorder.stop_recording()
            
            if ruta_audio:
                texto = transcribir_audio(ruta_audio)
                
                if texto:
                    escribir_texto(texto)
                else:
                    print("⚠️  No se pudo transcribir el audio")
            
            print()
            print("🟢 Listo para la siguiente grabación...")
            print()
    
    def on_press(key):
        """Callback cuando se presiona una tecla."""
        try:
            # Detectar Ctrl
            if key == Key.ctrl or key == Key.ctrl_l or key == Key.ctrl_r:
                estado['ctrl_pressed'] = True
            # Detectar Alt/Option
            elif key == Key.alt or key == Key.alt_l or key == Key.alt_r:
                estado['alt_pressed'] = True
            
            # Si ambas están presionadas, iniciar grabación
            if check_hotkey_pressed() and not estado['grabando']:
                iniciar_grabacion()
                
        except Exception as e:
            print(f"Error en on_press: {e}")
    
    def on_release(key):
        """Callback cuando se suelta una tecla."""
        try:
            # Si se suelta Ctrl o Alt mientras grabamos, detener
            if key == Key.ctrl or key == Key.ctrl_l or key == Key.ctrl_r:
                estado['ctrl_pressed'] = False
                if estado['grabando']:
                    detener_y_transcribir()
            elif key == Key.alt or key == Key.alt_l or key == Key.alt_r:
                estado['alt_pressed'] = False
                if estado['grabando']:
                    detener_y_transcribir()
                    
        except Exception as e:
            print(f"Error en on_release: {e}")
    
    # Iniciar el listener
    print("(Presiona CTRL + C para salir)")
    print()
    
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            print("\n\n👋 ¡Hasta luego!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrumpido por el usuario. ¡Hasta luego!")
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
