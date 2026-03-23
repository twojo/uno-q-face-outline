"""
AI Mirror Booth — fal.ai InstantID Backend
Designed for Arduino Uno Q (QRB2210) deployment.
Single-step identity-preserving face transformation via InstantID.
"""

import os
import sys
import base64
import random
import time
import io
import logging
from logging.handlers import RotatingFileHandler

import requests
import fal_client
from PIL import Image, ImageEnhance, ImageStat
from flask import Flask, render_template, request, jsonify

# ── Logging ──────────────────────────────────────────────────────────────────

LOG_FILE = "mirror_debug.log"

logger = logging.getLogger("mirror")
logger.setLevel(logging.DEBUG)

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
logger.addHandler(console_handler)

# ── App Setup ────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

FAL_MODEL = "fal-ai/instantid"
MAX_B64_SIZE = 2 * 1024 * 1024
RATE_LIMIT_SECONDS = 5
_last_request_by_ip = {}

TARGET_BRIGHTNESS = 128
TARGET_CONTRAST_FACTOR = 1.15
SHARPNESS_FACTOR = 1.2


def preprocess_face(b64_data: str) -> str:
    raw = base64.b64decode(b64_data)
    img = Image.open(io.BytesIO(raw)).convert("RGB")

    stat = ImageStat.Stat(img)
    perceived_brightness = sum(stat.mean[:3]) / 3.0
    logger.debug("Pre-process: size=%dx%d, brightness=%.1f", img.width, img.height, perceived_brightness)

    if perceived_brightness < 90:
        factor = min(TARGET_BRIGHTNESS / max(perceived_brightness, 1), 1.6)
        img = ImageEnhance.Brightness(img).enhance(factor)
        logger.debug("Brightness boosted x%.2f", factor)
    elif perceived_brightness > 180:
        factor = max(TARGET_BRIGHTNESS / perceived_brightness, 0.7)
        img = ImageEnhance.Brightness(img).enhance(factor)
        logger.debug("Brightness reduced x%.2f", factor)

    img = ImageEnhance.Contrast(img).enhance(TARGET_CONTRAST_FACTOR)
    img = ImageEnhance.Sharpness(img).enhance(SHARPNESS_FACTOR)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ── Prompts ──────────────────────────────────────────────────────────────────

IDENTITY_PREFIX = (
    "High-fidelity portrait of the exact person in the reference image, "
    "preserving all facial features and skin details, "
)

NEGATIVE_PROMPT = (
    "deformed face, generic features, different person, blurry, low quality, "
    "stylized illustration, cartoon, anime, 3d render, painting, sketch, "
    "disfigured, bad anatomy, extra limbs, mutated hands"
)

THEMES = {
    "Time Traveler": [
        IDENTITY_PREFIX + "dressed as an ancient Egyptian pharaoh with golden nemes headdress, inside a torch-lit pyramid chamber, cinematic lighting, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a 1920s flapper at a speakeasy, sequined headband, art deco background, warm amber lighting, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a Roman centurion in polished bronze armour with red-plumed helmet, Colosseum behind, golden hour, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a cyberpunk hacker with neon-lit face, holographic HUD, rain-soaked neon city, cinematic lighting, shot on 35mm, photorealistic",
    ],
    "Action Hero": [
        IDENTITY_PREFIX + "as a Viking warrior with war paint and fur-trimmed armour on a misty battlefield, dramatic sky, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a samurai warrior in ornate black and gold armour, cherry blossom petals floating, soft morning light, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a space marine in heavy battle armour on an alien planet with two moons, cinematic lighting, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a medieval knight in gleaming silver plate armour holding a flaming sword, epic storm clouds, shot on 35mm, photorealistic",
    ],
    "Fantasy Realm": [
        IDENTITY_PREFIX + "as a wizard with glowing blue eyes wearing arcane-runed robes in an ancient candlelit library, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as an elf ranger with pointed ears and leaf-pattern cloak in a bioluminescent enchanted forest, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a dragon rider wearing scaled armour with a massive dragon in flight behind, sunset sky, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a vampire lord in a gothic castle, pale skin, crimson eyes, velvet cape, candlelight atmosphere, shot on 35mm, photorealistic",
    ],
    "Explorer": [
        IDENTITY_PREFIX + "as a NASA astronaut inside the International Space Station with Earth visible through the cupola window, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a deep-sea diver in a vintage brass diving helmet, underwater with bioluminescent jellyfish, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as an arctic explorer in a fur-lined parka on frozen tundra with northern lights above, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a jungle explorer with a weathered hat and binoculars in dense tropical rainforest, dappled sunlight, shot on 35mm, photorealistic",
    ],
    "Pop Culture": [
        IDENTITY_PREFIX + "as a retro disco dancer with a shiny jumpsuit and mirrored sunglasses on a light-up dance floor, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a punk rocker with a tall mohawk and leather jacket covered in pins on a concert stage, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a classic film noir detective in trench coat and fedora, rainy alley with neon signs, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a superhero in a gleaming suit with flowing cape on a rooftop at sunset overlooking a city, shot on 35mm, photorealistic",
    ],
    "Wild Card": [
        IDENTITY_PREFIX + "as a mad scientist with wild hair and oversized goggles in a lab of bubbling beakers and tesla coils, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a pirate captain with tricorn hat and golden tooth on the deck of a ghost ship in fog, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a steampunk airship pilot wearing brass goggles and leather aviator cap, clouds below, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a Western outlaw with bandana and dusty hat in a saloon doorway at high noon, shot on 35mm, photorealistic",
    ],
}

# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    logger.info("Serving index page")
    return render_template("index.html")


@app.route("/transform", methods=["POST"])
def transform():
    ip = request.remote_addr or "unknown"
    now = time.time()
    last = _last_request_by_ip.get(ip, 0)
    if now - last < RATE_LIMIT_SECONDS:
        wait = int(RATE_LIMIT_SECONDS - (now - last)) + 1
        logger.warning("Rate limit hit from %s", ip)
        return jsonify({"success": False, "error": f"Please wait {wait}s before trying again."}), 429
    _last_request_by_ip[ip] = now

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid request."}), 400

    raw_image = data.get("image", "")
    if not isinstance(raw_image, str) or not raw_image:
        return jsonify({"success": False, "error": "No image provided."}), 400

    image_b64 = raw_image.split(",")[-1]
    if len(image_b64) > MAX_B64_SIZE:
        return jsonify({"success": False, "error": "Image too large."}), 400

    try:
        image_b64 = preprocess_face(image_b64)
    except Exception as pp_err:
        logger.warning("Pre-processing failed, using raw: %s", pp_err)

    theme_name = random.choice(list(THEMES.keys()))
    prompt = random.choice(THEMES[theme_name])

    seed = random.randint(0, 999999)
    face_data_uri = f"data:image/jpeg;base64,{image_b64}"

    logger.info("Transform: theme=%s, seed=%d, ip=%s", theme_name, seed, ip)
    logger.debug("Prompt: %s", prompt[:120])

    try:
        t0 = time.time()
        logger.info("Calling InstantID (seed=%d)...", seed)

        result = fal_client.subscribe(
            FAL_MODEL,
            arguments={
                "face_image_url": face_data_uri,
                "prompt": prompt,
                "negative_prompt": NEGATIVE_PROMPT,
                "ip_adapter_scale": 0.95,
                "controlnet_conditioning_scale": 0.90,
                "num_inference_steps": 20,
                "guidance_scale": 4.0,
                "seed": seed,
            },
        )

        elapsed = time.time() - t0
        logger.info("InstantID completed in %.1fs", elapsed)

        images = result.get("images") or []
        if isinstance(images, dict):
            images = [images]

        image_url = ""
        if images and isinstance(images[0], dict):
            image_url = images[0].get("url", "")
        if not image_url:
            obj = result.get("image")
            if isinstance(obj, dict):
                image_url = obj.get("url", "")
        if not image_url:
            logger.error("No image URL in response: %s", list(result.keys()))
            return jsonify({"success": False, "error": "Model returned no image."}), 500

        logger.info("Downloading result...")
        img_resp = requests.get(image_url, timeout=30)
        result_b64 = base64.b64encode(img_resp.content).decode("utf-8")

        ct = img_resp.headers.get("Content-Type", "image/jpeg")
        mime = "image/png" if "png" in ct else ("image/webp" if "webp" in ct else "image/jpeg")

        short_prompt = prompt.replace(IDENTITY_PREFIX, "").strip()
        logger.info("Done: theme=%s, seed=%d, elapsed=%.1fs", theme_name, seed, time.time() - t0)

        return jsonify({
            "success": True,
            "image": f"data:{mime};base64,{result_b64}",
            "prompt": short_prompt,
            "theme": theme_name,
            "seed": seed,
        })

    except Exception as e:
        logger.exception("Transform failed: %s", e)
        return jsonify({"success": False, "error": "Transformation failed. Please try again."}), 500


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    fal_key = os.environ.get("FAL_KEY")
    if not fal_key:
        logger.critical("FAL_KEY not set. Export FAL_KEY and retry.")
        sys.exit(1)

    logger.info("FAL_KEY loaded (length=%d)", len(fal_key))
    logger.info("Model: %s", FAL_MODEL)
    logger.info("Settings: ip_adapter=0.95, controlnet=0.90, steps=20, guidance=4.0")

    port = int(os.environ.get("PORT", 8000))
    logger.info("Starting AI Mirror Booth on port %d", port)
    app.run(host="0.0.0.0", port=port)
