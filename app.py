"""
Face Tracker — Real-time Expression Analysis

Pure client-side face tracking with MediaPipe.
The Flask backend only serves the HTML page.
"""

import os
import sys
import logging

from flask import Flask, render_template

logger = logging.getLogger("facetracker")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
logger.addHandler(console_handler)

app = Flask(__name__, static_folder="static", template_folder="templates")


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    logger.info("Starting Face Tracker on port %d", port)
    app.run(host="0.0.0.0", port=port)
