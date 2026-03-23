"""
AI Mirror Booth — Arduino Uno Q (QRB2210) entry point.

Uses the Arduino Bricks SDK (WebUI + App.run()).
On Replit the arduino/ shim folder replaces the real SDK so this file
runs unchanged for prototyping — delete arduino/ before flashing to the device.

Communication model
───────────────────
Browser → device : Socket.IO event  "transform"  { image: "data:image/jpeg;base64,..." }
Device  → browser: Socket.IO event  "result"     { success, image?, prompt?, theme?, seed?, error? }
Device  → browser: Socket.IO event  "status"     { message: str }   (progress updates)
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

from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App

# ── Logging ───────────────────────────────────────────────────────────────────

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

# ── Constants ─────────────────────────────────────────────────────────────────

FAL_MODEL             = "fal-ai/instantid"
MAX_B64_SIZE          = 2 * 1024 * 1024   # 2 MB
RATE_LIMIT_SECONDS    = 5
TARGET_BRIGHTNESS     = 128
TARGET_CONTRAST_FACTOR = 1.15
SHARPNESS_FACTOR      = 1.2

_last_request_by_sid: dict[str, float] = {}

# ── Image pre-processing ──────────────────────────────────────────────────────

def preprocess_face(b64_data: str) -> str:
    """Normalise brightness, contrast, and sharpness before sending to the model."""
    raw = base64.b64decode(b64_data)
    img = Image.open(io.BytesIO(raw)).convert("RGB")

    stat = ImageStat.Stat(img)
    perceived_brightness = sum(stat.mean[:3]) / 3.0
    logger.debug("Pre-process: size=%dx%d brightness=%.1f", img.width, img.height, perceived_brightness)

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

# ── Prompts ───────────────────────────────────────────────────────────────────

IDENTITY_PREFIX = (
    "(photorealistic portrait of the exact person in the reference image:1.4), "
    "highly detailed face, maintaining original facial features and structure, "
)

NEGATIVE_PROMPT = (
    "deformed face, different person, blurry, low quality, "
    "stylized illustration, cartoon, anime, 3d render, painting, sketch, "
    "disfigured, bad anatomy, extra limbs, mutated hands, watermark, text"
)

THEMES = {
    "Time Traveler": [
        IDENTITY_PREFIX + "dressed as an ancient Egyptian pharaoh wearing a golden nemes headdress, inside a torch-lit pyramid chamber, cinematic lighting, shot on 35mm film",
        IDENTITY_PREFIX + "as a 1920s flapper at a jazz-age speakeasy, sequined headband, art deco wallpaper behind, warm amber lighting, shot on 35mm film",
        IDENTITY_PREFIX + "as a Roman centurion in polished bronze armour with a red-plumed helmet, the Colosseum visible behind at golden hour, shot on 35mm film",
        IDENTITY_PREFIX + "as a cyberpunk hacker, neon light on face, holographic HUD reflections in pupils, rain-soaked neon city, shot on 35mm film",
    ],
    "Action Hero": [
        IDENTITY_PREFIX + "as a Viking warrior with war paint and fur-trimmed armour on a misty battlefield at dawn, dramatic stormy sky, shot on 35mm film",
        IDENTITY_PREFIX + "as a samurai warrior in ornate black-and-gold lacquered armour, cherry blossom petals drifting, soft morning mist, shot on 35mm film",
        IDENTITY_PREFIX + "as a space marine in heavy battle armour standing on an alien planet with two moons rising, dramatic cinematic lighting, shot on 35mm film",
        IDENTITY_PREFIX + "as a medieval knight in gleaming silver plate armour holding a flaming sword, lightning-lit storm clouds, shot on 35mm film",
    ],
    "Fantasy Realm": [
        IDENTITY_PREFIX + "as a powerful wizard with glowing arcane eyes, wearing rune-embroidered robes, ancient candlelit library, shot on 35mm film",
        IDENTITY_PREFIX + "as an elf ranger with pointed ears and a leaf-patterned forest cloak, standing in a bioluminescent enchanted forest, shot on 35mm film",
        IDENTITY_PREFIX + "as a dragon rider in scaled armour, a massive dragon soaring behind against a vivid sunset sky, shot on 35mm film",
        IDENTITY_PREFIX + "as a vampire lord in a gothic stone castle, pale skin, crimson eyes, velvet cape, flickering candlelight, shot on 35mm film",
    ],
    "Explorer": [
        IDENTITY_PREFIX + "as a NASA astronaut inside the International Space Station, Earth visible through the cupola window, shot on 35mm film",
        IDENTITY_PREFIX + "as a deep-sea diver in a vintage brass diving helmet, surrounded by bioluminescent jellyfish in deep ocean, shot on 35mm film",
        IDENTITY_PREFIX + "as an arctic explorer in a fur-lined parka on frozen tundra, aurora borealis blazing above, shot on 35mm film",
        IDENTITY_PREFIX + "as a jungle explorer wearing a weathered hat and carrying binoculars, dense tropical rainforest, dappled golden sunlight, shot on 35mm film",
    ],
    "Pop Culture": [
        IDENTITY_PREFIX + "as a retro disco dancer in a shiny silver jumpsuit and mirrored sunglasses on a glowing light-up dance floor, shot on 35mm film",
        IDENTITY_PREFIX + "as a punk rocker with a tall neon mohawk and a leather jacket covered in band pins, performing on a concert stage, shot on 35mm film",
        IDENTITY_PREFIX + "as a 1940s film noir detective in a trench coat and fedora, rain-soaked alley, neon signs reflecting on wet pavement, shot on 35mm film",
        IDENTITY_PREFIX + "as a superhero in a gleaming metallic suit with a flowing cape, standing on a rooftop at sunset above a vast city, shot on 35mm film",
    ],
    "Wild Card": [
        IDENTITY_PREFIX + "as a mad scientist with wild white hair and oversized goggles in a Victorian laboratory of bubbling beakers and crackling tesla coils, shot on 35mm film",
        IDENTITY_PREFIX + "as a pirate captain with a weathered tricorn hat and golden tooth, on the fog-shrouded deck of a ghost ship at night, shot on 35mm film",
        IDENTITY_PREFIX + "as a steampunk airship pilot wearing polished brass goggles and a leather aviator cap, clouds stretching below, shot on 35mm film",
        IDENTITY_PREFIX + "as a Western outlaw with a bandana and dusty hat framed in a saloon doorway at high noon, shot on 35mm film",
    ],
}

# ── Bricks app ────────────────────────────────────────────────────────────────

ui = WebUI()

@ui.on_connect
def on_connect(sid: str):
    logger.info("Client connected: %s", sid)
    ui.send_message("status", {"message": "Connected to AI Mirror Booth"})


@ui.on_message("transform")
def on_transform(sid: str, data):
    """Handle a transform request from the browser.

    Expected payload: { "image": "data:image/jpeg;base64,..." }
    """
    now = time.time()
    last = _last_request_by_sid.get(sid, 0)
    if now - last < RATE_LIMIT_SECONDS:
        wait = int(RATE_LIMIT_SECONDS - (now - last)) + 1
        logger.warning("Rate limit hit from sid=%s", sid)
        ui.send_message("result", {"success": False, "error": f"Please wait {wait}s before trying again."})
        return
    _last_request_by_sid[sid] = now

    if not isinstance(data, dict):
        ui.send_message("result", {"success": False, "error": "Invalid request."})
        return

    raw_image = data.get("image", "")
    if not isinstance(raw_image, str) or not raw_image:
        ui.send_message("result", {"success": False, "error": "No image provided."})
        return

    image_b64 = raw_image.split(",")[-1]
    if len(image_b64) > MAX_B64_SIZE:
        ui.send_message("result", {"success": False, "error": "Image too large (max 2 MB)."})
        return

    ui.send_message("status", {"message": "Preparing your image…"})

    try:
        image_b64 = preprocess_face(image_b64)
    except Exception as pp_err:
        logger.warning("Pre-processing failed, using raw image: %s", pp_err)

    theme_name = random.choice(list(THEMES.keys()))
    prompt = random.choice(THEMES[theme_name])
    seed = random.randint(0, 999999)
    face_data_uri = f"data:image/jpeg;base64,{image_b64}"

    logger.info("Transform: theme=%s seed=%d sid=%s", theme_name, seed, sid)
    logger.debug("Prompt: %s", prompt[:120])

    ui.send_message("status", {"message": f"Transforming you into: {theme_name}…"})

    try:
        t0 = time.time()
        logger.info("Calling InstantID (seed=%d)…", seed)

        result = fal_client.subscribe(
            FAL_MODEL,
            arguments={
                "face_image_url":              face_data_uri,
                "prompt":                      prompt,
                "negative_prompt":             NEGATIVE_PROMPT,
                "ip_adapter_scale":            0.8,
                "controlnet_conditioning_scale": 0.8,
                "num_inference_steps":         30,
                "guidance_scale":              7.5,
                "seed":                        seed,
                "enhance_face_region":         True,
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
            ui.send_message("result", {"success": False, "error": "Model returned no image."})
            return

        ui.send_message("status", {"message": "Finishing up…"})
        logger.info("Downloading result image…")

        img_resp = requests.get(image_url, timeout=30)
        result_b64 = base64.b64encode(img_resp.content).decode("utf-8")

        ct = img_resp.headers.get("Content-Type", "image/jpeg")
        mime = "image/png" if "png" in ct else ("image/webp" if "webp" in ct else "image/jpeg")

        short_prompt = prompt.replace(IDENTITY_PREFIX, "").strip()
        logger.info("Done: theme=%s seed=%d elapsed=%.1fs", theme_name, seed, time.time() - t0)

        ui.send_message("result", {
            "success": True,
            "image":   f"data:{mime};base64,{result_b64}",
            "prompt":  short_prompt,
            "theme":   theme_name,
            "seed":    seed,
        })

    except Exception as e:
        logger.exception("Transform failed: %s", e)
        ui.send_message("result", {"success": False, "error": "Transformation failed. Please try again."})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    fal_key = os.environ.get("FAL_KEY")
    if not fal_key:
        logger.critical("FAL_KEY not set — export FAL_KEY and retry.")
        sys.exit(1)

    logger.info("Model        : %s", FAL_MODEL)
    logger.info("Settings     : ip_adapter=0.8  controlnet=0.8  steps=30  guidance=7.5  enhance_face=True")
    logger.info("Themes       : %s", ", ".join(THEMES.keys()))

    App.run()
