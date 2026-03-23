import os
import base64
import random
import requests
from io import BytesIO
from PIL import Image
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, static_folder='static', template_folder='templates')

HF_API_TOKEN = os.environ.get("HF_TOKEN")
API_URL = "https://router.huggingface.co/hf-inference/models/timbrooks/instruct-pix2pix"

PROMPTS = [
    "Turn this person into a scuba diver swimming in a coral reef",
    "Make this person look like a steampunk cyborg",
    "Turn this person into a Royal Guard outside Buckingham Palace",
    "Make the subject look like a 13 lb fluffy cat",
    "Make this person look like they are snowboarding down a mountain",
    "Turn this person into a Viking warrior",
    "Make this person look like a Van Gogh painting",
    "Turn this person into a medieval knight in shining armour",
    "Make this person look like an astronaut on the moon",
    "Turn this person into a pirate captain on the high seas",
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/transform', methods=['POST'])
def transform():
    data = request.json
    image_b64 = data['image'].split(',')[1]
    prompt = random.choice(PROMPTS)

    try:
        # New HF router expects raw binary image in the body, prompt as query param
        image_bytes = base64.b64decode(image_b64)
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {HF_API_TOKEN}",
                "Content-Type": "image/jpeg",
            },
            params={"prompt": prompt},
            data=image_bytes,
            timeout=120,
        )

        if response.status_code == 200:
            result_b64 = base64.b64encode(response.content).decode("utf-8")
            return jsonify({
                "success": True,
                "image": f"data:image/jpeg;base64,{result_b64}",
                "prompt": prompt
            })
        else:
            return jsonify({"success": False, "error": f"API Error {response.status_code}: {response.text}"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
