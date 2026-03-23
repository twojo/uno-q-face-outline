# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  REPLIT SHIM — DELETE THIS ENTIRE arduino/ FOLDER BEFORE UNO Q DEPLOY  ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
# Replit compatibility shim for arduino.app_bricks.web_ui.WebUI
#
# Mirrors the official Bricks API exactly:
#   ui = WebUI()
#   ui.on_connect(callback)          callback(sid)
#   ui.on_message(event, callback)   callback(sid, data)
#   ui.send_message(event, data)
#
# On the Uno Q the real WebUI class (from the pre-installed arduino package)
# handles TLS, mDNS advertising, the QR-code pairing flow, and iframe
# video streaming.  This shim replaces all of that with Flask + Flask-SocketIO
# so the same main.py runs unchanged on Replit for prototyping.
#
# Threading note: Flask-SocketIO with async_mode="threading" gives every
# incoming Socket.IO event its own OS thread, so long-running handlers
# (e.g. a 30-90 s fal.ai inference call) never block the event loop.

import os
import threading
from flask import Flask, render_template, request as flask_request
from flask_socketio import SocketIO

# Module-level singleton so App.run() can find the instance.
_ui_instance = None

# Thread-local storage that lets send_message() route to the correct
# client when called from inside an on_connect / on_message handler.
_ctx = threading.local()


class WebUI:
    def __init__(self, use_tls=False):
        # use_tls is accepted for API compatibility but is a no-op on Replit.
        # On the Uno Q the real SDK sets up TLS transparently.
        global _ui_instance
        _ui_instance = self

        # Resolve paths relative to the workspace root, not this shim file.
        # web_ui.py lives at arduino/app_bricks/web_ui.py so we go up 3 levels.
        _root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        self._flask_app = Flask(
            __name__,
            static_folder=os.path.join(_root, "static"),
            template_folder=os.path.join(_root, "templates"),
        )
        self._sio = SocketIO(
            self._flask_app,
            cors_allowed_origins="*",
            async_mode="threading",
            logger=False,
            engineio_logger=False,
        )

        @self._flask_app.route("/")
        def index():
            return render_template("index.html")

        # Internal connect handler — delegates to the user's callback.
        @self._sio.on("connect")
        def _on_connect(auth=None):
            _ctx.sid = flask_request.sid
            try:
                if self._connect_cb:
                    self._connect_cb(flask_request.sid)
            finally:
                _ctx.sid = None

        self._connect_cb = None

    def on_connect(self, callback):
        """Register a callback invoked whenever a browser connects.

        Supports both direct call and decorator usage:
            ui.on_connect(my_func)   # direct
            @ui.on_connect           # decorator
        Signature: callback(sid: str) -> None
        """
        self._connect_cb = callback
        return callback

    def on_message(self, event_or_callback, callback=None):
        """Register a callback for a named Socket.IO event from the frontend.

        Supports both direct call and decorator usage:
            ui.on_message("transform", my_func)  # direct
            @ui.on_message("transform")           # decorator
        Signature: callback(sid: str, data: any) -> None
        """
        if callback is not None:
            self._register_message_handler(event_or_callback, callback)
        else:
            def decorator(fn):
                self._register_message_handler(event_or_callback, fn)
                return fn
            return decorator

    def _register_message_handler(self, event, callback):
        @self._sio.on(event)
        def _handler(data=None):
            sid = flask_request.sid
            _ctx.sid = sid
            try:
                callback(sid, data)
            finally:
                _ctx.sid = None

    def send_message(self, event: str, data):
        """Emit a Socket.IO event to the connected browser.

        When called from inside an on_connect / on_message handler the
        message is targeted at that specific client.  Otherwise it
        broadcasts to all connected clients (correct for a single-user
        photo booth).
        """
        sid = getattr(_ctx, "sid", None)
        if sid is not None:
            self._sio.emit(event, data, to=sid)
        else:
            self._sio.emit(event, data)

    def _run(self, port: int = 8000):
        """Start the Flask-SocketIO development server (called by App.run()).

        Reads the PORT env var when set (Replit artifact system injects this)
        so the shim can be wired as a proper artifact service without hardcoding
        a port that conflicts with other workflows.
        """
        port = int(os.environ.get("PORT", port))
        self._sio.run(
            self._flask_app,
            host="0.0.0.0",
            port=port,
            debug=False,
            allow_unsafe_werkzeug=True,
        )
