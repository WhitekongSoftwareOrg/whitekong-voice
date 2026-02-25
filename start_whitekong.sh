#!/bin/bash
# WhiteKong Voice - Script de inicio
# Este script lanza el monitor de WhiteKong Voice en segundo plano

# Matar instancias anteriores del monitor o la app
pkill -f keep_alive.sh
pkill -f dictado_app.py

cd /Users/smanez/codeWk/wisWK

# Lanzar el monitor en segundo plano (ignorando HUP para que persista)
nohup /Users/smanez/codeWk/wisWK/keep_alive.sh > /dev/null 2>&1 &
PID=$!

echo "✅ WhiteKong Voice iniciado en modo persistente (Monitor PID: $PID)"
echo "   La app se reiniciará automáticamente si falla."
