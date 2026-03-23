import os
import base64
import random
import tempfile
import requests
from flask import Flask, render_template, request, jsonify
from gradio_client import Client, handle_file

app = Flask(__name__, static_folder='static', template_folder='templates')

HF_API_TOKEN = os.environ.get("HF_TOKEN")

# InstantX/InstantID — zero-shot identity-preserving face generation
# API: /generate_image(face_image, pose_image, prompt, neg_prompt,
#                      style, steps, identity_strength, adapter_strength)
SPACE = "InstantX/InstantID"

NEGATIVE_PROMPT = (
    "nsfw, lowres, bad anatomy, bad hands, text, error, missing fingers, "
    "extra digit, fewer digits, cropped, worst quality, low quality, "
    "deformed, blurry, ugly, duplicate, morbid, mutilated"
)

# Each theme pairs a prompt with a matching InstantID style template.
# Available styles: (No style) | Watercolor | Film Noir | Neon |
#                   Jungle | Mars | Vibrant Color | Snow | Line art
THEMES = [
    {
        "prompt": "a fearless Viking warrior with braided beard and horned helmet, epic battle scene, dramatic sky",
        "style":  "(No style)",
    },
    {
        "prompt": "a steampunk cyborg inventor with copper gears, glowing goggles and mechanical arms",
        "style":  "(No style)",
    },
    {
        "prompt": "a Royal Guard in full ceremonial red uniform, standing outside a grand palace",
        "style":  "Film Noir",
    },
    {
        "prompt": "a medieval knight in gleaming full plate armour holding a sword, dramatic fantasy lighting",
        "style":  "(No style)",
    },
    {
        "prompt": "an astronaut in a space suit floating above Earth, stars and cosmos in the background",
        "style":  "Neon",
    },
    {
        "prompt": "a pirate captain with tricorn hat and eye patch on a tall ship at golden sunset",
        "style":  "Film Noir",
    },
    {
        "prompt": "a portrait in bold expressive swirling oil painting style, rich colourful brushstrokes",
        "style":  "Watercolor",
    },
    {
        "prompt": "a wise ancient wizard in flowing robes surrounded by magical glowing spell books",
        "style":  "(No style)",
    },
    {
        "prompt": "a samurai warrior in ornate feudal Japanese armour, cherry blossoms falling",
        "style":  "Line art",
    },
    {
        "prompt": "a sci-fi explorer in a sleek neon-lit cyberpunk city, futuristic glowing suit",
        "style":  "Neon",
    },
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/transform', methods=['POST'])
def transform():
    data      = request.json
    image_b64 = data.get('image', '').split(',')[-1]

    if not image_b64:
        return jsonify({"success": False, "error": "No image received."})

    theme  = random.choice(THEMES)
    prompt = theme["prompt"]
    style  = theme["style"]

    image_bytes = base64.b64decode(image_b64)
    tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
    try:
        tmp.write(image_bytes)
        tmp.flush()
        tmp.close()

        client = Client(SPACE)
        result = client.predict(
            handle_file(tmp.name),  # face image (identity source)
            None,                   # pose reference image (optional)
            prompt,                 # prompt
            NEGATIVE_PROMPT,        # negative prompt
            style,                  # style template
            30,                     # num inference steps  (1-100)
            0.8,                    # IdentityNet strength (0-1.5)  — face fidelity
            0.8,                    # Image adapter strength (0-1.5) — detail fidelity
            api_name="/generate_image",
        )

        print(f"InstantID result type: {type(result)}, value: {str(result)[:200]}")

        # InstantID returns a tuple: (filepath, metadata_dict)
        if isinstance(result, (tuple, list)):
            result = result[0]

        out_bytes = _read_result(result)
        if out_bytes is None:
            return jsonify({"success": False, "error": f"Unrecognised result format: {result}"})

        # Detect MIME type from the file path
        if isinstance(result, str) and result.endswith('.webp'):
            mime = "image/webp"
        elif isinstance(result, str) and result.endswith('.png'):
            mime = "image/png"
        else:
            mime = "image/jpeg"

        result_b64 = base64.b64encode(out_bytes).decode("utf-8")
        return jsonify({
            "success": True,
            "image":   f"data:{mime};base64,{result_b64}",
            "prompt":  prompt,
            "mode":    "img2img",
        })

    except Exception as e:
        print(f"InstantID error: {e}")
        return jsonify({"success": False, "error": str(e)})
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def _read_result(result):
    """Return raw bytes from whatever gradio_client hands back."""
    if isinstance(result, str):
        if os.path.exists(result):
            with open(result, 'rb') as f:
                return f.read()
        if result.startswith('http'):
            return requests.get(result, timeout=30).content
    if isinstance(result, dict):
        path = result.get('path') or result.get('name') or result.get('url', '')
        if path and os.path.exists(path):
            with open(path, 'rb') as f:
                return f.read()
        if path and path.startswith('http'):
            return requests.get(path, timeout=30).content
    return None


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
