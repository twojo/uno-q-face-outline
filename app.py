import os
import io
import base64
import random
from flask import Flask, render_template, request, jsonify
from huggingface_hub import InferenceClient
from PIL import Image

app = Flask(__name__)

hf_token = os.environ.get("HF_TOKEN")
client = InferenceClient(token=hf_token)

TRANSFORM_PROMPTS = [
    "turn this person into a scuba diver swimming in a vibrant coral reef",
    "turn this person into an astronaut floating in outer space with Earth in the background",
    "make this person look like a neon-lit cyberpunk character in a rainy futuristic city",
    "transform this person into a medieval knight wearing shining armor",
    "turn this person into a pirate captain standing on the deck of a tall ship",
    "make this person look like a wizard in flowing robes holding a glowing staff",
    "transform this person into a 1980s pop star with big hair and colorful stage outfit",
    "turn this person into a deep-sea explorer piloting a submersible",
    "make this person look like a superhero in a dramatic cape and mask",
    "transform this person into a samurai warrior in traditional Japanese armor",
    "turn this person into an arctic explorer in a snowstorm with a husky sled",
    "make this person look like they stepped out of a Vincent van Gogh painting",
    "transform this person into a jungle adventurer with a safari hat in a rainforest",
    "turn this person into a retro-futuristic robot with chrome plating and glowing eyes",
    "make this person look like a Victorian-era inventor surrounded by clockwork gears",
]

MODEL_ID = "timbrooks/instruct-pix2pix"


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
        if img_data.startswith("data:"):
            img_data = img_data.split(",", 1)[1]

        img_bytes = base64.b64decode(img_data)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        img.thumbnail((512, 512))

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
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
