# ─────────────────────────────────────────────────────────────
#  Smart Mirror AI Photo Booth — Backend
#  Prototype: Replit  |  Final target: Arduino Uno Q (QRB2210 Debian)
#
#  To run on the Uno Q's Debian partition:
#    pip install flask huggingface_hub Pillow
#    export HF_TOKEN="your_token_here"
#    python3 app.py
#
#  PORT defaults to 8000. Override with: export PORT=5000
# ─────────────────────────────────────────────────────────────

import os
import io
import base64
import random
from flask import Flask, render_template, request, jsonify
from huggingface_hub import InferenceClient
from PIL import Image

app = Flask(__name__)

# HF token is read from environment — never hardcoded.
# On Replit: set via the Secrets panel (HF_TOKEN).
# On Uno Q:  export HF_TOKEN="hf_..." before running.
hf_token = os.environ.get("HF_TOKEN")
client = InferenceClient(token=hf_token)

TRANSFORM_PROMPTS = [
    # ── Original set ──────────────────────────────────────────
    "turn this person into a scuba diver swimming in a vibrant coral reef",
    "turn this person into an astronaut floating in outer space with Earth in the background",
    "make this person look like a neon-lit cyberpunk character in a rainy futuristic city",
    "transform this person into a medieval knight wearing shining armor",
    "turn this person into a pirate captain standing on the deck of a tall ship",
    "make this person look like a wizard in flowing robes holding a glowing staff",
    "transform this person into a 1980s pop star with big hair and colorful stage outfit",
    "turn this person into a deep-sea explorer piloting a yellow submersible",
    "make this person look like a superhero in a dramatic cape and mask",
    "transform this person into a samurai warrior in traditional Japanese armor",
    "turn this person into an arctic explorer in a snowstorm with a husky sled",
    "make this person look like they stepped out of a Vincent van Gogh painting",
    "transform this person into a jungle adventurer with a safari hat in a rainforest",
    "turn this person into a retro-futuristic robot with chrome plating and glowing eyes",
    "make this person look like a Victorian-era inventor surrounded by clockwork gears",
    # ── New set ───────────────────────────────────────────────
    "make this person a steampunk cyborg with brass gears, copper tubing, and glowing goggles",
    "turn this person into a Royal Guard standing outside Buckingham Palace in London, "
    "wearing the iconic red tunic and black bearskin hat",
    "make the person look like they are snowboarding down a mountain with a bright ski jacket "
    "and goggles, snow flying around them",
    "turn this person into a 13 lb fluffy orange tabby cat sitting regally on a velvet cushion",
    "transform this person into a deep-jungle shaman covered in tribal paint and feathers",
    "make this person look like they are piloting a fighter jet at supersonic speed",
    "turn this person into a Renaissance painter in a Florence studio surrounded by canvases",
    "transform this person into a deep-sea diver in a vintage brass diving suit on the ocean floor",
    "make this person look like a 1920s jazz musician performing on a smoky Chicago stage",
    "turn this person into a Norse Viking warrior standing on the prow of a longship",
]

MODEL_ID = "timbrooks/instruct-pix2pix"

# Maximum long-edge size sent to the model.
# Smaller = faster inference, lower memory use on the Uno Q.
MAX_IMG_SIZE = 512


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/transform", methods=["POST"])
def transform():
    data = request.get_json(silent=True)
    if not data or "image" not in data:
        return jsonify({"success": False, "error": "No image provided"}), 400

    try:
        img_data = data["image"]
        # Strip data-URL header if present (e.g. "data:image/jpeg;base64,...")
        if img_data.startswith("data:"):
            img_data = img_data.split(",", 1)[1]

        img_bytes = base64.b64decode(img_data)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        # Resize to cap long edge — keeps inference fast on resource-limited hardware
        img.thumbnail((MAX_IMG_SIZE, MAX_IMG_SIZE))

        prompt = random.choice(TRANSFORM_PROMPTS)

        result = client.image_to_image(
            image=img,
            prompt=prompt,
            model=MODEL_ID,
        )

        out_buffer = io.BytesIO()
        result.save(out_buffer, format="JPEG", quality=90)
        out_b64 = base64.b64encode(out_buffer.getvalue()).decode("utf-8")

        return jsonify({
            "success": True,
            "image": f"data:image/jpeg;base64,{out_b64}",
            "prompt": prompt,
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    # PORT env var keeps the entry point environment-agnostic.
    # Replit assigns PORT automatically; on the Uno Q it defaults to 8000.
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
