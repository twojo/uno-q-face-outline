import os
import base64
import random
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, static_folder='static', template_folder='templates')

HF_API_TOKEN = os.environ.get("HF_TOKEN")
API_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"

PROMPTS = [
    "A fearless Viking warrior with braided beard and horned helmet, epic oil painting",
    "A steampunk cyborg with glowing copper gears and goggles, detailed digital art",
    "A Royal Guard outside Buckingham Palace in full ceremonial uniform, photorealistic",
    "A scuba diver swimming through a vibrant coral reef, underwater photography",
    "A medieval knight in gleaming full plate armour, dramatic fantasy illustration",
    "An astronaut floating on the surface of the moon, Earth glowing behind them",
    "A pirate captain on the deck of a tall ship at sunset, cinematic painting",
    "A portrait painted in the bold swirling style of Van Gogh, starry sky background",
    "A snowboarder launching off a mountain peak, action photography",
    "A wise wizard in flowing robes surrounded by magical floating books, fantasy art",
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/transform', methods=['POST'])
def transform():
    prompt = random.choice(PROMPTS)

    try:
        response = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {HF_API_TOKEN}"},
            json={"inputs": prompt},
            timeout=120,
        )

        print(f"HF status: {response.status_code}")
        if response.status_code != 200:
            print(f"HF error: {response.text[:300]}")

        if response.status_code == 200:
            result_b64 = base64.b64encode(response.content).decode("utf-8")
            return jsonify({
                "success": True,
                "image": f"data:image/jpeg;base64,{result_b64}",
                "prompt": prompt
            })
        else:
            return jsonify({"success": False, "error": f"HF {response.status_code}: {response.text[:200]}"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
