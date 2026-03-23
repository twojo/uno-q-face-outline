# Smart Mirror — Arduino Bricks edition
#
# Architecture is identical on Replit and on the Uno Q:
#
#   Phone browser                     Python backend (this file)
#   ─────────────                     ──────────────────────────
#   getUserMedia → <video>
#   tap Capture
#   canvas.toDataURL ──socket.emit("capture")──► handle_capture()
#                                                 HuggingFace inference
#   showResult() ◄──socket.emit("result") ─────
#
# On Replit  : the "arduino/" folder is a Flask-SocketIO shim.
# On Uno Q   : delete the "arduino/" folder; the real SDK takes over.
# THIS FILE never changes between environments.
#
# Dependencies (pip install on both Replit and Uno Q):
#   flask-socketio  huggingface_hub  Pillow
#
# SPDX-FileCopyrightText: Copyright (C) 2025 Smart Mirror Project
# SPDX-License-Identifier: MPL-2.0

import base64
import io
import logging
import os
import random
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

from PIL import Image
from huggingface_hub import InferenceClient

# On the Uno Q these imports resolve to the official Bricks SDK.
# On Replit they resolve to the arduino/ compatibility shim.
from arduino.app_utils import App
from arduino.app_bricks.web_ui import WebUI

# ── Logging ───────────────────────────────────────────────────────────────────
# RotatingFileHandler caps the log at 5 MB and keeps 3 rotations —
# critical for embedded storage (SD / eMMC) on the Uno Q.

LOG_FILE = os.environ.get("LOG_FILE", "smart_mirror.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3),
    ],
)
logger = logging.getLogger(__name__)

# ── Captures directory ────────────────────────────────────────────────────────
CAPTURES_DIR = os.environ.get("CAPTURES_DIR", "./captures")
os.makedirs(CAPTURES_DIR, exist_ok=True)
logger.info("Captures directory: %s", os.path.abspath(CAPTURES_DIR))

# ── HuggingFace client ────────────────────────────────────────────────────────
HF_TOKEN = os.environ.get("HF_TOKEN")
if not HF_TOKEN:
    logger.warning("HF_TOKEN not set — API calls will use the public rate-limited tier")
MODEL_ID = "timbrooks/instruct-pix2pix"
client = InferenceClient(token=HF_TOKEN)

# ── Transform prompts ─────────────────────────────────────────────────────────
TRANSFORM_PROMPTS = [
    # Adventure / Exploration
    "turn this person into a scuba diver swimming in a vibrant coral reef",
    "turn this person into an astronaut floating in outer space with Earth in the background",
    "turn this person into a deep-sea explorer piloting a yellow submersible",
    "turn this person into an arctic explorer in a snowstorm with a husky sled",
    "transform this person into a jungle adventurer with a safari hat in a rainforest",
    "make the person look like they are snowboarding down a mountain with bright goggles",
    "make this person look like they are piloting a fighter jet at supersonic speed",
    # Fantasy / Historical
    "transform this person into a medieval knight wearing shining armour",
    "turn this person into a pirate captain standing on the deck of a tall ship",
    "make this person look like a wizard in flowing robes holding a glowing staff",
    "transform this person into a samurai warrior in traditional Japanese armour",
    "turn this person into a Norse Viking warrior standing on the prow of a longship",
    "transform this person into a Renaissance painter in a Florence studio",
    "make this person look like a Victorian-era inventor surrounded by clockwork gears",
    "make this person look like a 1920s jazz musician on a smoky Chicago stage",
    # Sci-Fi / Cyberpunk
    "make this person look like a neon-lit cyberpunk character in a rainy futuristic city",
    "turn this person into a retro-futuristic robot with chrome plating and glowing eyes",
    "make this person a steampunk cyborg with brass gears and glowing goggles",
    "transform this person into a deep-sea diver in a vintage brass diving suit",
    # Pop Culture / Art Styles
    "transform this person into a 1980s pop star with big hair and a colourful stage outfit",
    "make this person look like a superhero in a dramatic cape and mask",
    "make this person look like they stepped out of a Vincent van Gogh painting",
    "transform this person into a deep-jungle shaman covered in tribal paint and feathers",
    # London themed
    "turn this person into a Royal Guard outside Buckingham Palace in a red tunic and bearskin hat",
    # Animal
    "turn this person into a 13 lb fluffy orange tabby cat sitting regally on a velvet cushion",
]

# ── Bricks wiring ─────────────────────────────────────────────────────────────

ui = WebUI()
# use_tls=True is accepted by the real SDK to enable HTTPS on the Uno Q.
# Leave it False here for Replit prototyping.


def on_client_connect(sid: str):
    """Called by the Bricks framework when a browser tab connects."""
    logger.info("Browser connected — sid=%s", sid)
    ui.send_message("welcome", {
        "status": "ready",
        "prompts": len(TRANSFORM_PROMPTS),
    })


ui.on_connect(on_client_connect)


def handle_capture(sid: str, data: dict):
    """
    Receive a base-64 JPEG frame from the browser, run AI image-to-image
    inference, save both images to disk, and emit the result back.

    Socket.IO events used:
      ← "capture"        { image: "<data-url>" }   (from browser)
      → "processing"     { prompt: "..." }          (prompt chosen)
      → "result"         { image: "<data-url>", prompt: "..." }
      → "transform_error" { message: "..." }
    """
    t_start = time.perf_counter()
    prompt = random.choice(TRANSFORM_PROMPTS)
    logger.info("capture — sid=%s  prompt=%r", sid, prompt)

    # Notify the frontend which prompt was chosen before the slow inference.
    ui.send_message("processing", {"prompt": prompt})

    try:
        # ── Decode incoming image ─────────────────────────────────────────
        img_data: str = (data or {}).get("image", "")
        if img_data.startswith("data:"):
            img_data = img_data.split(",", 1)[1]
        img_bytes = base64.b64decode(img_data)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        logger.info("Decoded: %dx%d px", *img.size)

        # ── Resize to model limit (preserves aspect ratio) ────────────────
        img.thumbnail((512, 512))

        # ── Save original capture ─────────────────────────────────────────
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        original_path = os.path.join(CAPTURES_DIR, f"original_{ts}.jpg")
        img.save(original_path, format="JPEG", quality=90)

        # ── HuggingFace inference ─────────────────────────────────────────
        t_inf = time.perf_counter()
        result_img = client.image_to_image(image=img, prompt=prompt, model=MODEL_ID)
        logger.info("Inference: %.2fs", time.perf_counter() - t_inf)

        # ── Save AI result ────────────────────────────────────────────────
        ai_path = os.path.join(CAPTURES_DIR, f"ai_{ts}.jpg")
        result_img.save(ai_path, format="JPEG", quality=90)

        # ── Encode and send back ──────────────────────────────────────────
        buf = io.BytesIO()
        result_img.save(buf, format="JPEG", quality=90)
        out_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        logger.info("Total round-trip: %.2fs", time.perf_counter() - t_start)

        ui.send_message("result", {
            "image": f"data:image/jpeg;base64,{out_b64}",
            "prompt": prompt,
        })

    except Exception as exc:
        logger.error("Transform failed: %s", exc, exc_info=True)
        ui.send_message("transform_error", {"message": str(exc)})


ui.on_message("capture", handle_capture)

# ── Start ─────────────────────────────────────────────────────────────────────
logger.info("Starting Smart Mirror (Bricks edition)")
App.run()
