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
    "illustration, painting, cartoon, anime, 3d render, sketch, drawing, "
    "nsfw, lowres, bad anatomy, bad hands, text, error, missing fingers, "
    "extra digit, fewer digits, cropped, worst quality, low quality, "
    "deformed, blurry, ugly, duplicate, morbid, mutilated, disfigured"
)

STYLE = "(No style)"

PROMPTS = [
    "A high-resolution photograph of the person as a fearless Viking warrior with braided beard and horned helmet on a snowy battlefield, cinematic lighting, 8k, shot on 35mm lens",
    "A high-resolution photograph of the person as a steampunk inventor wearing copper goggles and a leather vest surrounded by brass machinery, cinematic lighting, 8k, shot on 35mm lens",
    "A high-resolution photograph of the person as a Royal Guard in full ceremonial red uniform standing outside Buckingham Palace, cinematic lighting, 8k, shot on 35mm lens",
    "A high-resolution photograph of the person as a medieval knight in gleaming full plate armour holding a broadsword, cinematic lighting, 8k, shot on 35mm lens",
    "A high-resolution photograph of the person as an astronaut in a NASA space suit on the lunar surface with Earth in the sky, cinematic lighting, 8k, shot on 35mm lens",
    "A high-resolution photograph of the person as a pirate captain with a tricorn hat on the deck of a tall ship at golden hour, cinematic lighting, 8k, shot on 35mm lens",
    "A high-resolution photograph of the person as a wise wizard in dark flowing robes holding a glowing staff in an ancient library, cinematic lighting, 8k, shot on 35mm lens",
    "A high-resolution photograph of the person as a samurai warrior in ornate feudal Japanese armour with cherry blossoms falling, cinematic lighting, 8k, shot on 35mm lens",
    "A high-resolution photograph of the person as a deep-sea scuba diver in a wetsuit surrounded by tropical fish on a coral reef, cinematic lighting, 8k, shot on 35mm lens",
    "A high-resolution photograph of the person as a fighter pilot wearing an aviator helmet sitting in a jet cockpit, cinematic lighting, 8k, shot on 35mm lens",
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

    prompt = random.choice(PROMPTS)

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
            STYLE,                  # style template — always "(No style)" for photorealism
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
