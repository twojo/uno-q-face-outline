"""
AI Mirror Booth — Final Showstopper Edition
Target: Arduino Uno Q (QRB2210)
Logic: Identity-Preserved Face Mapping via Fal.ai InstantID

DEPLOYMENT TARGETS
──────────────────
  1. REPLIT
     Entry point : app.py        ← Flask HTTP version for Replit hosting
     Shim folder : arduino/      ← keep this; provides Bricks SDK compatibility

  2. ARDUINO UNO Q (QRB2210) ← YOU ARE HERE
     Entry point : main.py       ← Bricks SDK version (WebSocket via Socket.IO)
     Shim folder : DELETE arduino/ before flashing (real SDK is pre-installed)
     Run command : python main.py
     Env vars    : FAL_KEY (set in device env or .env file)

  3. FREE ALTERNATIVE (no paid API)
     Entry point : main_free.py  ← Uses Hugging Face instruct-pix2pix (free tier)
     Env vars    : HF_TOKEN (free Hugging Face token)

SWITCHING TO UNO Q — STEP BY STEP
──────────────────────────────────
  1. Copy this entire project to the Uno Q filesystem
  2. Delete the arduino/ shim folder:  rm -rf arduino/
     (The real Bricks SDK is pre-installed on the Uno Q at the system level)
  3. Set FAL_KEY in the device environment or a .env file
  4. Run:  python main.py
  5. The real SDK handles: TLS, mDNS, QR-code pairing, iframe video streaming
"""

import os
import sys
import base64
import random
import time
import requests
import fal_client
from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App

# --- IDENTITY LOCK SETTINGS ---
FAL_MODEL = "fal-ai/instantid"

# We weight the identity at 1.4 to force the model to respect your bone structure
IDENTITY_PREFIX = (
    "(photorealistic portrait of the exact person in the reference image:1.4), "
    "highly detailed face, maintaining original facial features and structure, "
)

NEGATIVE_PROMPT = (
    "deformed face, generic features, different person, blurry, low quality, "
    "illustration, cartoon, anime, painting, sketch, 3d render, "
    "disfigured, bad anatomy, extra limbs, mutated hands, watermark, text"
)

# --- THEMED PROMPT POOLS ---
THEMES = {
    "Time Traveler": [
        IDENTITY_PREFIX + "dressed as an ancient Egyptian pharaoh wearing a golden nemes headdress, inside a torch-lit pyramid chamber, cinematic lighting, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a 1920s flapper at a jazz-age speakeasy, sequined headband, art deco wallpaper behind, warm amber lighting, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a Roman centurion in polished bronze armour with a red-plumed helmet, the Colosseum visible behind at golden hour, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a cyberpunk hacker, neon light on face, holographic HUD reflections in pupils, rain-soaked neon city, shot on 35mm, photorealistic",
    ],
    "Action Hero": [
        IDENTITY_PREFIX + "as a Viking warrior with war paint and fur-trimmed armour on a misty battlefield at dawn, dramatic stormy sky, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a samurai warrior in ornate black and gold armour, cherry blossom petals floating, soft morning light, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a space marine in heavy battle armour on an alien planet with two moons, cinematic lighting, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a medieval knight in gleaming silver plate armour holding a flaming sword, lightning-lit storm clouds, shot on 35mm, photorealistic",
    ],
    "Fantasy Realm": [
        IDENTITY_PREFIX + "as a powerful wizard with glowing arcane eyes, wearing rune-embroidered robes, ancient candlelit library, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as an elf ranger with pointed ears and a leaf-patterned forest cloak, standing in a bioluminescent enchanted forest, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a dragon rider in scaled armour, a massive dragon soaring behind against a vivid sunset sky, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a vampire lord in a gothic stone castle, pale skin, crimson eyes, velvet cape, flickering candlelight, shot on 35mm, photorealistic",
    ],
    "Explorer": [
        IDENTITY_PREFIX + "as a NASA astronaut inside the ISS, Earth visible through the cupola window, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a deep-sea diver in a vintage brass diving helmet, underwater with bioluminescent jellyfish, cinematic lighting, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as an arctic explorer in a fur-lined parka on frozen tundra, aurora borealis blazing above, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a jungle explorer wearing a weathered hat and binoculars, dense tropical rainforest, dappled golden sunlight, shot on 35mm, photorealistic",
    ],
    "Pop Culture": [
        IDENTITY_PREFIX + "as a retro disco dancer in a shiny silver jumpsuit and mirrored sunglasses on a glowing light-up dance floor, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a punk rocker with a tall neon mohawk and a leather jacket covered in band pins, performing on a concert stage, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a classic film noir detective in trench coat and fedora, rainy alley with neon signs reflecting on wet pavement, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a superhero in a gleaming metallic suit with a flowing cape, standing on a rooftop at sunset above a vast city, shot on 35mm, photorealistic",
    ],
    "Wild Card": [
        IDENTITY_PREFIX + "as a mad scientist with wild white hair and oversized goggles in a Victorian laboratory of bubbling beakers and crackling tesla coils, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a pirate captain with a weathered tricorn hat and golden tooth, on the fog-shrouded deck of a ghost ship at night, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a steampunk airship pilot wearing polished brass goggles and a leather aviator cap, clouds stretching below, shot on 35mm, photorealistic",
        IDENTITY_PREFIX + "as a Western outlaw with a bandana and dusty hat framed in a saloon doorway at high noon, shot on 35mm, photorealistic",
    ],
}

# --- BRICKS APP ---
ui = WebUI()

@ui.on_connect
def on_connect(sid):
    ui.send_message("status", {"message": "Connected to AI Mirror Booth"})


_rate_limit = {}
RATE_LIMIT_SECONDS = 5

@ui.on_message("transform")
def on_transform(sid, data):
    now = time.time()
    last = _rate_limit.get(sid, 0)
    if now - last < RATE_LIMIT_SECONDS:
        ui.send_message("result", {"success": False, "error": "Please wait a few seconds between requests."})
        return
    _rate_limit[sid] = now

    if len(_rate_limit) > 1000:
        cutoff = now - 60
        _rate_limit.clear()

    ui.send_message("status", {"message": "Extrapolating facial data..."})

    raw_image = data.get("image", "") if isinstance(data, dict) else ""
    if not raw_image:
        ui.send_message("result", {"success": False, "error": "No image provided."})
        return

    image_b64 = raw_image.split(",")[-1]
    theme_name = random.choice(list(THEMES.keys()))
    prompt = random.choice(THEMES[theme_name])
    seed = random.randint(0, 999999)

    ui.send_message("status", {"message": f"Transforming you into: {theme_name}..."})

    try:
        t0 = time.time()

        # Pinging Fal.ai with the Identity-Lock parameters
        result = fal_client.subscribe(
            FAL_MODEL,
            arguments={
                "face_image_url": f"data:image/jpeg;base64,{image_b64}",
                "prompt": prompt,
                "negative_prompt": NEGATIVE_PROMPT,
                "ip_adapter_scale": 0.85,             # High fidelity to YOUR face
                "controlnet_conditioning_scale": 0.8,  # Respect the POSE
                "guidance_scale": 5.0,                 # Lower = better blending
                "enhance_face_region": True,           # Sharp eyes/mouth
                "seed": seed,
            },
        )

        elapsed = time.time() - t0

        # Extract image URL from response (handles both response shapes)
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
            ui.send_message("result", {"success": False, "error": "Model returned no image."})
            return

        ui.send_message("status", {"message": "Finishing up..."})

        img_resp = requests.get(image_url, timeout=30)
        result_b64 = base64.b64encode(img_resp.content).decode("utf-8")

        ct = img_resp.headers.get("Content-Type", "image/jpeg")
        mime = "image/png" if "png" in ct else ("image/webp" if "webp" in ct else "image/jpeg")

        short_prompt = prompt.replace(IDENTITY_PREFIX, "").strip()

        ui.send_message("result", {
            "success": True,
            "image": f"data:{mime};base64,{result_b64}",
            "prompt": short_prompt,
            "theme": theme_name,
            "seed": seed,
        })

    except Exception as e:
        err_str = str(e).lower()
        if "cannot find any face" in err_str or "no face" in err_str:
            msg = "No face detected in the photo. Make sure your face is clearly visible and try again."
        else:
            msg = "Transformation failed. Please try again."
        ui.send_message("result", {"success": False, "error": msg})


# --- ENTRY POINT ---
# Ensure you set FAL_KEY in the Uno Q environment!
if __name__ == "__main__":
    if not os.environ.get("FAL_KEY"):
        print("[CRITICAL] FAL_KEY not set. Export FAL_KEY and retry.")
        sys.exit(1)
    App.run()
