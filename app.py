# ═══════════════════════════════════════════════════════════════════
#  Smart Mirror AI Photo Booth — Flask Backend
#  Prototype: Replit  |  Final target: Arduino Uno Q (QRB2210 Debian)
#
#  Deployment on Uno Q Debian partition:
#    pip install flask huggingface_hub Pillow
#    export HF_TOKEN="hf_..."      # your Hugging Face token
#    python3 app.py                # serves on 0.0.0.0:8000
#
#  Log file  → smart_mirror.log   (rotates at 5 MB, keeps 3 backups)
#  Captures  → captures/          (original + AI image, timestamped)
# ═══════════════════════════════════════════════════════════════════

import os
import io
import base64
import random
import time
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template, request, jsonify
from huggingface_hub import InferenceClient
from PIL import Image


# ── Logging setup ────────────────────────────────────────────────────
# RotatingFileHandler caps the log at MAX_BYTES and keeps BACKUP_COUNT
# old files — critical for embedded storage (SD cards, eMMC).
LOG_FILE    = "smart_mirror.log"
MAX_BYTES   = 5 * 1024 * 1024   # 5 MB per log file
BACKUP_COUNT = 3                 # smart_mirror.log.1, .2, .3

log_formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT)
file_handler.setFormatter(log_formatter)

# Also emit to stdout — useful when tailing over SSH on the Uno Q
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)

logger = logging.getLogger("smart_mirror")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)


# ── Captures directory ───────────────────────────────────────────────
# All original and AI-generated images are saved here with timestamps.
# On the Uno Q, point CAPTURES_DIR to a path on the Debian partition.
CAPTURES_DIR = os.environ.get("CAPTURES_DIR", "captures")
os.makedirs(CAPTURES_DIR, exist_ok=True)
logger.info("Captures directory: %s", os.path.abspath(CAPTURES_DIR))


# ── HuggingFace client ───────────────────────────────────────────────
# HF_TOKEN is read from the environment — never hardcoded.
# Replit: set via the Secrets panel.
# Uno Q:  export HF_TOKEN="hf_..." before running.
hf_token = os.environ.get("HF_TOKEN")
if not hf_token:
    logger.warning("HF_TOKEN is not set — API calls will use the public (rate-limited) tier")
client = InferenceClient(token=hf_token)


# ── Model ────────────────────────────────────────────────────────────
MODEL_ID    = "timbrooks/instruct-pix2pix"
MAX_IMG_SIZE = 512   # pixels (long edge) — keeps inference fast on QRB2210


# ── Prompt list ──────────────────────────────────────────────────────
# Add or remove prompts freely. One is chosen at random per capture.
TRANSFORM_PROMPTS = [
    # Adventure / Exploration
    "turn this person into a scuba diver swimming in a vibrant coral reef",
    "turn this person into an astronaut floating in outer space with Earth in the background",
    "turn this person into a deep-sea explorer piloting a yellow submersible",
    "turn this person into an arctic explorer in a snowstorm with a husky sled",
    "transform this person into a jungle adventurer with a safari hat in a rainforest",
    "make the person look like they are snowboarding down a mountain with a bright ski jacket "
    "and goggles, snow flying around them",
    "make this person look like they are piloting a fighter jet at supersonic speed",
    # Fantasy / Historical
    "transform this person into a medieval knight wearing shining armour",
    "turn this person into a pirate captain standing on the deck of a tall ship",
    "make this person look like a wizard in flowing robes holding a glowing staff",
    "transform this person into a samurai warrior in traditional Japanese armour",
    "turn this person into a Norse Viking warrior standing on the prow of a longship",
    "transform this person into a Renaissance painter in a Florence studio surrounded by canvases",
    "make this person look like a Victorian-era inventor surrounded by clockwork gears",
    "make this person look like a 1920s jazz musician performing on a smoky Chicago stage",
    # Sci-Fi / Cyberpunk
    "make this person look like a neon-lit cyberpunk character in a rainy futuristic city",
    "turn this person into a retro-futuristic robot with chrome plating and glowing eyes",
    "make this person a steampunk cyborg with brass gears, copper tubing, and glowing goggles",
    "transform this person into a deep-sea diver in a vintage brass diving suit on the ocean floor",
    # Pop Culture / Fun
    "transform this person into a 1980s pop star with big hair and a colourful stage outfit",
    "make this person look like a superhero in a dramatic cape and mask",
    "make this person look like they stepped out of a Vincent van Gogh painting",
    "transform this person into a deep-jungle shaman covered in tribal paint and feathers",
    # London / Specific
    "turn this person into a Royal Guard standing outside Buckingham Palace in London, "
    "wearing the iconic red tunic and black bearskin hat",
    # Animal
    "turn this person into a 13 lb fluffy orange tabby cat sitting regally on a velvet cushion",
]


# ── Flask app ────────────────────────────────────────────────────────
# static_folder='static'  → Flask serves /static/* from ./static/
# template_folder='templates' is the default but stated explicitly for clarity.
app = Flask(__name__, static_folder="static", template_folder="templates")


# ── Routes ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the Smart Mirror UI."""
    logger.info("GET / — serving index.html")
    return render_template("index.html")


@app.route("/transform", methods=["POST"])
def transform():
    """
    Accepts a base64-encoded JPEG, runs image-to-image inference,
    saves both images to disk, and returns the result as base64 JSON.

    Expected JSON body:
        { "image": "<data-url or raw base64>" }

    Response JSON:
        { "success": true, "image": "<data-url>", "prompt": "<string>" }
    or
        { "success": false, "error": "<message>" }
    """
    request_start = time.perf_counter()
    logger.info("POST /transform — request received from %s", request.remote_addr)

    # ── 1. Parse request ──────────────────────────────────────────────
    data = request.get_json(silent=True)
    if not data or "image" not in data:
        logger.warning("POST /transform — rejected: missing 'image' field")
        return jsonify({"success": False, "error": "No image provided"}), 400

    try:
        # ── 2. Decode incoming base64 image ───────────────────────────
        img_data = data["image"]
        if img_data.startswith("data:"):
            # Strip  "data:image/jpeg;base64,"  header
            img_data = img_data.split(",", 1)[1]

        img_bytes = base64.b64decode(img_data)
        original_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        logger.info(
            "Decoded original image — size: %dx%d px, raw bytes: %d",
            original_img.width, original_img.height, len(img_bytes),
        )

        # ── 3. Resize before sending to model ─────────────────────────
        # thumbnail() preserves aspect ratio and only shrinks (never upscales).
        original_img.thumbnail((MAX_IMG_SIZE, MAX_IMG_SIZE))
        logger.info(
            "Resized for inference — %dx%d px",
            original_img.width, original_img.height,
        )

        # ── 4. Pick a random prompt ───────────────────────────────────
        prompt = random.choice(TRANSFORM_PROMPTS)
        logger.info("Selected prompt: %s", prompt)

        # ── 5. Save original capture to disk ──────────────────────────
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        original_path = os.path.join(CAPTURES_DIR, f"original_{timestamp}.jpg")
        original_img.save(original_path, format="JPEG", quality=90)
        logger.info("Saved original → %s", original_path)

        # ── 6. Run inference ──────────────────────────────────────────
        inference_start = time.perf_counter()
        result_img = client.image_to_image(
            image=original_img,
            prompt=prompt,
            model=MODEL_ID,
        )
        inference_elapsed = time.perf_counter() - inference_start
        logger.info("Inference complete — %.2f s", inference_elapsed)

        # ── 7. Save AI result to disk ─────────────────────────────────
        ai_path = os.path.join(CAPTURES_DIR, f"ai_{timestamp}.jpg")
        result_img.save(ai_path, format="JPEG", quality=90)
        logger.info("Saved AI result → %s", ai_path)

        # ── 8. Encode result for frontend ─────────────────────────────
        out_buffer = io.BytesIO()
        result_img.save(out_buffer, format="JPEG", quality=90)
        out_b64 = base64.b64encode(out_buffer.getvalue()).decode("utf-8")

        total_elapsed = time.perf_counter() - request_start
        logger.info(
            "POST /transform — success | inference: %.2fs | total: %.2fs",
            inference_elapsed, total_elapsed,
        )

        return jsonify({
            "success": True,
            "image":  f"data:image/jpeg;base64,{out_b64}",
            "prompt": prompt,
        })

    except Exception as exc:
        total_elapsed = time.perf_counter() - request_start
        logger.error(
            "POST /transform — ERROR after %.2fs: %s",
            total_elapsed, exc, exc_info=True,
        )
        return jsonify({"success": False, "error": str(exc)}), 500


# ── Entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    logger.info("Starting Smart Mirror server on 0.0.0.0:%d", port)
    # debug=False is required for production / headless Uno Q deployment.
    # Set debug=True locally only if you need the Werkzeug reloader.
    app.run(host="0.0.0.0", port=port, debug=False)
