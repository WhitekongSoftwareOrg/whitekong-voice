# 🎤 WhiteKong Voice

Aplicación de dictado por voz para macOS, similar a Wispr Flow. Transcribe tu voz a texto usando IA (Groq/Whisper o Google Gemini) y lo escribe automáticamente donde esté tu cursor.

![macOS](https://img.shields.io/badge/macOS-10.15+-blue)
![Python](https://img.shields.io/badge/Python-3.10+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ Características

- 🎙️ **Push-to-Talk**: Mantén `Ctrl + Option` para grabar, suelta para transcribir
- ⚡ **Dos proveedores de IA**:
  - **Groq (Whisper)**: Ultrarrápido, especializado en transcripción
  - **Google Gemini**: Multimodal, con corrección de puntuación
- 📱 **App de barra de menú**: Discreta, siempre accesible
- 🔄 **Cambio de proveedor al vuelo**: Sin reiniciar la app
- ⌨️ **Escritura automática**: El texto aparece donde esté tu cursor

## 🚀 Instalación Rápida

### 1. Clonar el repositorio

```bash
git clone https://github.com/whitekong/whitekong-voice.git
cd whitekong-voice
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Obtener API Keys

Necesitas al menos una API Key:

| Proveedor | URL | Descripción |
|-----------|-----|-------------|
| **Groq** (recomendado) | [console.groq.com/keys](https://console.groq.com/keys) | Gratis, muy rápido |
| **Google Gemini** | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | Gratis, buena calidad |

### 4. Lanzar la app

```bash
source venv/bin/activate
python dictado_app.py
```

O haz doble-click en `WhiteKong Voice.app`.

### 5. Configurar API Keys

1. Click en el icono 🎤 en la barra de menú
2. Selecciona **⚙️ Configurar API Keys**
3. Introduce tu(s) API Key(s)

## 📖 Uso

### Controles

| Acción | Cómo |
|--------|------|
| **Grabar** | Mantén `Ctrl + Option` |
| **Transcribir** | Suelta las teclas |
| **Cambiar proveedor** | Click en 🎤 → Selecciona proveedor |
| **Salir** | Click en 🎤 → ❌ Salir |

### Indicadores visuales

| Icono | Estado |
|-------|--------|
| 🎤 | Listo para grabar |
| 🔴 | Grabando |
| ⏳ | Procesando transcripción |

## 🔧 Permisos en macOS

La app necesita permisos de **Accesibilidad** para:
- Capturar teclas globalmente
- Escribir texto en otras aplicaciones

Cuando macOS lo solicite, ve a:
**Preferencias del Sistema → Privacidad y Seguridad → Accesibilidad**

Y habilita el terminal o la app.

## 📁 Estructura del Proyecto

```
whitekong-voice/
├── dictado_app.py          # App de barra de menú (principal)
├── dictado_global.py       # Script de terminal alternativo
├── requirements.txt        # Dependencias Python
├── WhiteKong Voice.app/    # App empaquetada para macOS
├── Dictado.command         # Lanzador alternativo
└── README.md
```

## 🛠️ Desarrollo

### Requisitos

- Python 3.10+
- macOS 10.15+

### Dependencias principales

```
pynput          # Captura de teclado
sounddevice     # Grabación de audio
scipy           # Procesamiento de audio
rumps           # App de barra de menú
groq            # API de Groq/Whisper
google-generativeai  # API de Google Gemini
```

### Ejecutar en modo desarrollo

```bash
source venv/bin/activate
python dictado_app.py
```

## ⚙️ Configuración

La configuración se guarda en `~/.dictado_config`:

```
provider=GROQ
groq_api_key=tu_api_key
google_api_key=tu_api_key
```

## 🐛 Solución de Problemas

### "No se detectan las teclas"
- Asegúrate de dar permisos de Accesibilidad al terminal/app

### "Error de transcripción"
- Verifica que tu API Key es correcta
- Comprueba tu conexión a internet

### "No aparece el icono en la barra de menú"
- Verifica que la app está corriendo (busca en el Dock)
- Reinicia la app

## 📄 Licencia

MIT License - © 2024 WhiteKong

## 🙏 Créditos

- Inspirado en [Wispr Flow](https://wisprflow.ai)
- Transcripción por [Groq](https://groq.com) y [Google Gemini](https://ai.google.dev)
