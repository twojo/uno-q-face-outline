import os
import base64
import random
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, static_folder='static', template_folder='templates')

HF_API_TOKEN  = os.environ.get("HF_TOKEN")
FAL_API_KEY   = os.environ.get("FAL_KEY")

# fal.ai endpoint for instruct-pix2pix (img2img, preserves face structure)
FAL_URL  = "https://fal.run/fal-ai/fast-instruct-pix2pix"
# Fallback: FLUX text-to-image when no FAL_KEY is set
FLUX_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"

PROMPTS = [
    "A portrait of this exact person as a fearless Viking warrior with braided beard, keeping their original face and features",
    "A portrait of this exact person as a steampunk cyborg with copper gears and goggles, keeping their facial structure",
    "A portrait of this exact person in full Royal Guard ceremonial uniform, keeping their face",
    "A portrait of this exact person in medieval full plate knight armour, keeping their original features",
    "A portrait of this exact person as an astronaut floating near the moon, keeping their face",
    "A portrait of this exact person as a pirate captain at sunset, keeping their facial features",
    "A portrait of this exact person painted in Van Gogh's bold swirling style, keeping their likeness",
    "A portrait of this exact person as a wise wizard in flowing robes, keeping their original face",
    "A portrait of this exact person as a sci-fi space explorer, keeping their facial structure",
    "A portrait of this exact person in a dramatic fantasy oil painting style, keeping their face",
]

@app.route('/')
def index():
    return render_template('index.html', has_fal=bool(FAL_API_KEY))

@app.route('/transform', methods=['POST'])
def transform():
    data      = request.json
    image_b64 = data.get('image', '').split(',')[-1]
    prompt    = random.choice(PROMPTS)

    # ── img2img via fal.ai (face-preserving) ──────────────────────────
    if FAL_API_KEY and image_b64:
        try:
            payload = {
                "image_url": f"data:image/jpeg;base64,{image_b64}",
                "prompt":    prompt,
                "strength":  0.45,
                "num_inference_steps": 30,
                "guidance_scale": 7.5,
                "image_guidance_scale": 1.5,
            }
            resp = requests.post(
                FAL_URL,
                headers={
                    "Authorization": f"Key {FAL_API_KEY}",
                    "Content-Type":  "application/json",
                },
                json=payload,
                timeout=120,
            )

            print(f"fal status: {resp.status_code}")
            print(f"fal response: {resp.text[:300]}")

            if resp.status_code == 200:
                result = resp.json()
                # fal.ai returns {images: [{url: "..."}]}
                image_url = result.get("images", [{}])[0].get("url", "")
                if image_url.startswith("data:"):
                    return jsonify({"success": True, "image": image_url, "prompt": prompt, "mode": "img2img"})
                # If it's a remote URL, fetch and re-encode
                img_resp = requests.get(image_url, timeout=30)
                result_b64 = base64.b64encode(img_resp.content).decode("utf-8")
                return jsonify({
                    "success": True,
                    "image":   f"data:image/jpeg;base64,{result_b64}",
                    "prompt":  prompt,
                    "mode":    "img2img",
                })
            else:
                return jsonify({"success": False, "error": f"fal.ai {resp.status_code}: {resp.text[:200]}"})

        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    # ── Fallback: FLUX text-to-image ───────────────────────────────────
    try:
        # Strip "keeping their original face" from FLUX prompts (doesn't apply)
        flux_prompt = prompt.split(",")[0].replace("A portrait of this exact person as ", "")
        resp = requests.post(
            FLUX_URL,
            headers={"Authorization": f"Bearer {HF_API_TOKEN}"},
            json={"inputs": flux_prompt},
            timeout=120,
        )

        print(f"FLUX status: {resp.status_code}")

        if resp.status_code == 200:
            result_b64 = base64.b64encode(resp.content).decode("utf-8")
            return jsonify({
                "success": True,
                "image":   f"data:image/jpeg;base64,{result_b64}",
                "prompt":  flux_prompt,
                "mode":    "text2img",
            })
        else:
            return jsonify({"success": False, "error": f"FLUX {resp.status_code}: {resp.text[:200]}"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
