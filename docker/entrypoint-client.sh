#!/bin/bash
set -e

echo "[Client] Starting Virtual Framebuffer (Xvfb)..."
Xvfb :0 -screen 0 1280x800x24 &
sleep 1

echo "[Client] Starting Window Manager (fluxbox)..."
DISPLAY=:0 fluxbox &

echo "[Client] Starting VNC Server (x11vnc)..."
x11vnc -display :0 -nopw -listen 0.0.0.0 -xkb -ncache 10 -ncache_cr -forever -shared &

echo "[Client] Starting noVNC Websocket Bridge (websockify)..."
NOVNC_DIR="/usr/share/novnc"
if [ ! -d "$NOVNC_DIR" ]; then
    NOVNC_DIR="/opt/novnc"
fi

if [ -f "$NOVNC_DIR/vnc.html" ] && [ ! -f "$NOVNC_DIR/index.html" ]; then
    ln -s "$NOVNC_DIR/vnc.html" "$NOVNC_DIR/index.html" 2>/dev/null || true
fi

websockify --web "$NOVNC_DIR" 6080 localhost:5900 &

echo "[Client] noVNC Web Interface is live at http://localhost:6080"

if [ -f gui/main.py ]; then
    echo "[Client] Launching PyQt5 GUI Client..."
    DISPLAY=:0 python3 -B gui/main.py
else
    echo "[Client] 'gui/main.py' not found yet. Container ready and waiting for source code..."
    tail -f /dev/null
fi
