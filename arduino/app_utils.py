# Replit compatibility shim for arduino.app_utils.App
#
# App.run() is the single entry point that starts the entire Bricks runtime.
# On the Uno Q the real App.run() also starts the mDNS daemon, the QR-code
# provisioning server, and any registered peripherals (camera, GPIO, etc.).
# Here it simply starts the Flask-SocketIO server registered by WebUI().

import os


class App:
    @staticmethod
    def run():
        from arduino.app_bricks.web_ui import _ui_instance
        if _ui_instance is None:
            raise RuntimeError(
                "App.run() called before a WebUI() instance was created."
            )
        port = int(os.environ.get("PORT", 8000))
        _ui_instance._run(port=port)
