#!/bin/bash
set -e

mkdir -p /data

if [ -f Makefile ]; then
    echo "[Server] Building project with make..."
    make clean 2>/dev/null || true
    make
    if [ -f ./server ]; then
        echo "[Server] Starting C Quiz Server on port ${PORT:-5000}..."
        exec ./server
    else
        echo "[Server] Binary './server' not found after make."
        exec tail -f /dev/null
    fi
else
    echo "[Server] Makefile not found yet. Container ready and waiting for source code..."
    exec tail -f /dev/null
fi
