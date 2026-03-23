import os
import base64
import random
import requests
import fal_client
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, static_folder='static', template_folder='templates')

# fal_client reads FAL_KEY from the environment automatically
FAL_MODEL = "fal-ai/instant-id"

NEGATIVE_PROMPT = (
    "illustration, painting, cartoon, anime, 3d render, sketch, drawing, "
    "nsfw, lowres, bad anatomy, bad hands, text, error, missing fingers, "
    "extra digit, fewer digits, cropped, worst quality, low quality, "
    "deformed, blurry, ugly, duplicate, morbid, mutilated, disfigured"
)

PROMPTS = [
    "A cinematic, 8k resolution photograph of the person as a fearless Viking warrior with braided beard and horned helmet on a snowy battlefield, highly detailed, shot on 35mm",
    "A cinematic, 8k resolution photograph of the person as a steampunk inventor wearing copper goggles and a leather vest surrounded by brass machinery, highly detailed, shot on 35mm",
    "A cinematic, 8k resolution photograph of the person as a Royal Guard in full ceremonial red uniform standing outside Buckingham Palace, highly detailed, shot on 35mm",
    "A cinematic, 8k resolution photograph of the person as a medieval knight in gleaming full plate armour holding a broadsword, highly detailed, shot on 35mm",
    "A cinematic, 8k resolution photograph of the person as an astronaut in a NASA space suit on the lunar surface with Earth in the sky, highly detailed, shot on 35mm",
    "A cinematic, 8k resolution photograph of the person as a pirate captain with a tricorn hat on the deck of a tall ship at golden hour, highly detailed, shot on 35mm",
    "A cinematic, 8k resolution photograph of the person as a wise wizard in dark flowing robes holding a glowing staff in an ancient library, highly detailed, shot on 35mm",
    "A cinematic, 8k resolution photograph of the person as a samurai warrior in ornate feudal Japanese armour with cherry blossoms falling, highly detailed, shot on 35mm",
    "A cinematic, 8k resolution photograph of the person as a deep-sea scuba diver in a wetsuit surrounded by tropical fish on a coral reef, highly detailed, shot on 35mm",
    "A cinematic, 8k resolution photograph of the person as a fighter pilot wearing an aviator helmet sitting in a jet cockpit, highly detailed, shot on 35mm",
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
    face_data_uri = f"data:image/jpeg;base64,{image_b64}"

    try:
        result = fal_client.subscribe(
            FAL_MODEL,
            arguments={
                "prompt":                       prompt,
                "negative_prompt":              NEGATIVE_PROMPT,
                "face_image_url":               face_data_uri,
                "ip_adapter_scale":             0.8,
                "controlnet_conditioning_scale": 0.8,
                "num_inference_steps":           30,
                "guidance_scale":               5.0,
            },
        )

        print(f"fal result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")

        # fal returns {"images": [{"url": "https://..."}], ...}
        images = result.get("images") or result.get("image") or []
        if isinstance(images, dict):
            images = [images]

        if not images:
            return jsonify({"success": False, "error": f"No images in fal response: {list(result.keys())}"})

        image_url = images[0].get("url", "")
        if not image_url:
            return jsonify({"success": False, "error": "No image URL in fal response."})

        # Download the generated image and encode to base64
        img_resp = requests.get(image_url, timeout=30)
        result_b64 = base64.b64encode(img_resp.content).decode("utf-8")

        content_type = img_resp.headers.get("Content-Type", "image/jpeg")
        if "png" in content_type:
            mime = "image/png"
        elif "webp" in content_type:
            mime = "image/webp"
        else:
            mime = "image/jpeg"

        return jsonify({
            "success": True,
            "image":   f"data:{mime};base64,{result_b64}",
            "prompt":  prompt,
            "mode":    "img2img",
        })

    except Exception as e:
        print(f"fal error: {e}")
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
