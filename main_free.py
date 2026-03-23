"""
AI Mirror Booth — FREE Hugging Face edition.

Uses the Hugging Face Inference API (free tier) with instruct-pix2pix
for image-to-image face transformation.  No paid API keys required —
just a free Hugging Face token (HF_TOKEN).

Works on Replit (via the arduino/ shim) and on the Uno Q (real SDK).
Delete the arduino/ folder before flashing to the device.

Communication model
───────────────────
Browser → device : Socket.IO event  "transform"  { image: "data:image/jpeg;base64,..." }
Device  → browser: Socket.IO event  "result"     { success, image?, prompt?, theme?, error? }
Device  → browser: Socket.IO event  "status"     { message: str }
"""

import os
import sys
import base64
import random
import time
import io
import logging
from logging.handlers import RotatingFileHandler

from huggingface_hub import InferenceClient
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

HF_MODEL              = "timbrooks/instruct-pix2pix"
MAX_B64_SIZE          = 2 * 1024 * 1024
RATE_LIMIT_SECONDS    = 8
TARGET_BRIGHTNESS     = 128
TARGET_CONTRAST_FACTOR = 1.15
SHARPNESS_FACTOR      = 1.2
MAX_IMG_DIM           = 512

_last_request_by_sid: dict[str, float] = {}

# ── Hugging Face client ───────────────────────────────────────────────────────

hf_client: InferenceClient | None = None

# ── Image helpers ─────────────────────────────────────────────────────────────

def decode_b64_image(b64_data: str) -> Image.Image:
    raw = base64.b64decode(b64_data)
    return Image.open(io.BytesIO(raw)).convert("RGB")


def preprocess_face(img: Image.Image) -> Image.Image:
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
    return img


def resize_for_model(img: Image.Image) -> Image.Image:
    w, h = img.size
    if max(w, h) <= MAX_IMG_DIM:
        return img
    scale = MAX_IMG_DIM / max(w, h)
    new_w = int(w * scale) // 8 * 8
    new_h = int(h * scale) // 8 * 8
    return img.resize((new_w, new_h), Image.LANCZOS)


def pil_to_b64(img: Image.Image, fmt: str = "JPEG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=90)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

# ── Prompts (instruct-pix2pix style: imperative instructions) ─────────────────

THEMES = {
    "Time Traveler": [
        "Transform this person into an ancient Egyptian pharaoh wearing a golden headdress, in a torch-lit pyramid, cinematic lighting",
        "Make this person a 1920s flapper at a jazz speakeasy, sequined headband, art deco background, warm amber lighting",
        "Turn this person into a Roman centurion in polished bronze armour with a red-plumed helmet, the Colosseum behind at golden hour",
        "Transform this person into a cyberpunk hacker with neon-lit face, holographic visor, rain-soaked neon city background",
    ],
    "Action Hero": [
        "Turn this person into a Viking warrior with war paint and fur armour on a misty battlefield, dramatic stormy sky",
        "Make this person a samurai warrior in ornate black-and-gold armour, cherry blossom petals floating, morning mist",
        "Transform this person into a space marine in heavy battle armour on an alien planet with two moons in the sky",
        "Turn this person into a medieval knight in gleaming silver plate armour holding a flaming sword, storm clouds above",
    ],
    "Fantasy Realm": [
        "Transform this person into a wizard with glowing blue eyes wearing arcane robes, in an ancient candlelit library",
        "Make this person an elf ranger with pointed ears and a leaf-patterned cloak in a glowing enchanted forest",
        "Turn this person into a dragon rider in scaled armour with a massive dragon flying behind, sunset sky",
        "Transform this person into a vampire lord in a gothic castle, pale skin, crimson eyes, velvet cape, candlelight",
    ],
    "Explorer": [
        "Make this person a NASA astronaut inside the International Space Station with Earth visible through the window",
        "Turn this person into a deep-sea diver in a vintage brass diving helmet, surrounded by bioluminescent jellyfish",
        "Transform this person into an arctic explorer in a fur-lined parka on frozen tundra with northern lights above",
        "Make this person a jungle explorer with a weathered hat and binoculars in a dense tropical rainforest, dappled sunlight",
    ],
    "Pop Culture": [
        "Turn this person into a retro disco dancer in a shiny silver jumpsuit and mirrored sunglasses on a light-up dance floor",
        "Make this person a punk rocker with a tall neon mohawk and leather jacket covered in pins on a concert stage",
        "Transform this person into a 1940s film noir detective in a trench coat and fedora, rainy alley with neon signs",
        "Turn this person into a superhero in a gleaming metallic suit with a flowing cape on a rooftop at sunset",
    ],
    "Wild Card": [
        "Make this person a mad scientist with wild hair and oversized goggles in a lab with bubbling beakers and tesla coils",
        "Transform this person into a pirate captain with a tricorn hat and golden tooth on the deck of a ghost ship in fog",
        "Turn this person into a steampunk airship pilot with brass goggles and leather aviator cap, clouds below",
        "Make this person a Western outlaw with a bandana and dusty hat in a saloon doorway at high noon",
    ],
}

# ── Bricks app ────────────────────────────────────────────────────────────────

ui = WebUI()


def on_connect(sid: str):
    logger.info("Client connected: %s", sid)
    ui.send_message("status", {"message": "Connected — free Hugging Face edition"})

ui.on_connect(on_connect)


def on_transform(sid: str, data):
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
        img = decode_b64_image(image_b64)
        img = preprocess_face(img)
        img = resize_for_model(img)
    except Exception as pp_err:
        logger.warning("Pre-processing failed: %s", pp_err)
        try:
            img = decode_b64_image(image_b64)
            img = resize_for_model(img)
        except Exception:
            ui.send_message("result", {"success": False, "error": "Could not process image."})
            return

    theme_name = random.choice(list(THEMES.keys()))
    prompt = random.choice(THEMES[theme_name])

    logger.info("Transform: theme=%s sid=%s", theme_name, sid)
    logger.debug("Prompt: %s", prompt)

    ui.send_message("status", {"message": f"Transforming → {theme_name}… (may take 30-60s on free tier)"})

    try:
        t0 = time.time()

        input_buf = io.BytesIO()
        img.save(input_buf, format="JPEG", quality=90)
        input_buf.seek(0)

        logger.info("Calling Hugging Face %s…", HF_MODEL)

        result_image = hf_client.image_to_image(
            image=input_buf,
            prompt=prompt,
            model=HF_MODEL,
            num_inference_steps=25,
            image_guidance_scale=1.5,
            guidance_scale=7.5,
        )

        elapsed = time.time() - t0
        logger.info("HF inference completed in %.1fs", elapsed)

        if result_image is None:
            ui.send_message("result", {"success": False, "error": "Model returned no image."})
            return

        result_b64 = pil_to_b64(result_image, "JPEG")

        logger.info("Done: theme=%s elapsed=%.1fs", theme_name, elapsed)

        ui.send_message("result", {
            "success": True,
            "image":   f"data:image/jpeg;base64,{result_b64}",
            "prompt":  prompt,
            "theme":   theme_name,
        })

    except Exception as e:
        logger.exception("Transform failed: %s", e)
        err_msg = str(e)
        if "rate" in err_msg.lower() or "429" in err_msg:
            ui.send_message("result", {
                "success": False,
                "error": "Hugging Face free rate limit reached. Wait a minute and try again."
            })
        elif "503" in err_msg or "loading" in err_msg.lower():
            ui.send_message("result", {
                "success": False,
                "error": "Model is loading on HF servers. Try again in 30-60 seconds."
            })
        else:
            ui.send_message("result", {
                "success": False,
                "error": "Transformation failed. Please try again."
            })

ui.on_message("transform", on_transform)

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        logger.critical("HF_TOKEN not set — get a free token at https://huggingface.co/settings/tokens")
        sys.exit(1)

    hf_client = InferenceClient(token=hf_token)

    logger.info("Model        : %s (free tier)", HF_MODEL)
    logger.info("Settings     : steps=25  guidance=7.5  img_guidance=1.5")
    logger.info("Themes       : %s", ", ".join(THEMES.keys()))
    logger.info("Note         : Free tier has rate limits — ~5 requests/min")

    App.run()
