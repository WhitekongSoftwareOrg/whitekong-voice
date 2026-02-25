#!/bin/bash
# WhiteKong Voice - Keep Alive Monitor

# Asegurar que estamos en el directorio correcto
cd /Users/smanez/codeWk/wisWK

while true; do
    echo "----------------------------------------" >> /tmp/whitekong_voice.log
    echo "[$(date)] 🚀 Iniciando WhiteKong Voice..." >> /tmp/whitekong_voice.log
    
    /Users/smanez/codeWk/wisWK/venv/bin/python /Users/smanez/codeWk/wisWK/dictado_app.py >> /tmp/whitekong_voice.log 2>&1
    
    EXIT_CODE=$?
    echo "[$(date)] ⚠️ App cerrada (Código: $EXIT_CODE). Reiniciando en 3 segundos..." >> /tmp/whitekong_voice.log
    sleep 3
done
