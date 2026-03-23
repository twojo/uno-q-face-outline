#!/bin/bash
set -e

pip install flask flask-socketio Pillow fal-client requests 2>/dev/null || true

exec python3 /home/runner/workspace/app.py
