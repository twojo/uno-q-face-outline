import os
import base64
import random
import tempfile
import requests
from flask import Flask, render_template, request, jsonify
from gradio_client import Client, handle_file

app = Flask(__name__, static_folder='static', template_folder='templates')

HF_API_TOKEN = os.environ.get("HF_TOKEN")

# Manjushri/SDXL-Turbo-Img2Img-CPU
# API: /predict(image, prompt, iterations 1-5, seed, strength 0.1-1.0)
SPACE = "Manjushri/SDXL-Turbo-Img2Img-CPU"

PROMPTS = [
    "A portrait of this person as a fearless Viking warrior with braided beard and horned helmet",
    "A portrait of this person as a steampunk cyborg with copper gears and glowing goggles",
    "A portrait of this person as a Royal Guard in full ceremonial uniform",
    "A portrait of this person in gleaming medieval full plate knight armour",
    "A portrait of this person as an astronaut floating near the moon",
    "A portrait of this person as a pirate captain at sunset on a tall ship",
    "A portrait of this person painted in Van Gogh's bold swirling oil style",
    "A portrait of this person as a wise wizard in flowing magical robes",
    "A portrait of this person as a sci-fi space explorer with neon suit",
    "A portrait of this person as a samurai warrior in feudal Japan",
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/transform', methods=['POST'])
def transform():
    data      = request.json
    image_b64 = data.get('image', '').split(',')[-1]
    prompt    = random.choice(PROMPTS)

    if not image_b64:
        return jsonify({"success": False, "error": "No image received."})

    # Decode image and write to a temp file for gradio_client
    image_bytes = base64.b64decode(image_b64)
    tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
    try:
        tmp.write(image_bytes)
        tmp.flush()
        tmp.close()

        client = Client(SPACE)
        result = client.predict(
            handle_file(tmp.name),      # Raw Image
            prompt,                     # Prompt (77 token max)
            3,                          # Number of Iterations (1-5)
            random.randint(0, 999999),  # Seed
            0.45,                       # Strength (0.1-1.0) — preserves face
            api_name="/predict",
        )

        print(f"Gradio result type: {type(result)}, value: {str(result)[:120]}")

        # result is a local file path to the output image
        if isinstance(result, str) and os.path.exists(result):
            with open(result, 'rb') as f:
                out_bytes = f.read()
        elif isinstance(result, dict):
            out_path = result.get('path') or result.get('name') or result.get('url', '')
            if os.path.exists(out_path):
                with open(out_path, 'rb') as f:
                    out_bytes = f.read()
            elif out_path.startswith('http'):
                out_bytes = requests.get(out_path, timeout=30).content
            else:
                return jsonify({"success": False, "error": f"Unexpected result format: {result}"})
        else:
            return jsonify({"success": False, "error": f"Unexpected result: {result}"})

        result_b64 = base64.b64encode(out_bytes).decode("utf-8")
        return jsonify({
            "success": True,
            "image":   f"data:image/jpeg;base64,{result_b64}",
            "prompt":  prompt,
            "mode":    "img2img",
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"success": False, "error": str(e)})
    finally:
        os.unlink(tmp.name)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
