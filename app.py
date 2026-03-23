import os
import base64
import random
import requests
import fal_client
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, static_folder='static', template_folder='templates')

# fal_client reads FAL_KEY from the environment automatically
FAL_MODEL = "fal-ai/nano-banana-2"

PROMPTS = [
    "A cinematic 8k photograph of a fearless Viking warrior with braided beard and horned helmet standing on a snowy battlefield, dramatic sky, shot on 35mm lens, highly detailed",
    "A cinematic 8k photograph of a steampunk inventor wearing copper goggles and a leather vest in a workshop full of brass machinery and glowing gauges, shot on 35mm lens, highly detailed",
    "A cinematic 8k photograph of a Royal Guard in full ceremonial red uniform standing at attention outside Buckingham Palace, golden hour lighting, shot on 35mm lens, highly detailed",
    "A cinematic 8k photograph of a medieval knight in gleaming full plate armour holding a broadsword on a misty castle battlement, dramatic lighting, shot on 35mm lens, highly detailed",
    "A cinematic 8k photograph of an astronaut in a NASA space suit standing on the lunar surface with Earth glowing in the black sky behind them, shot on 35mm lens, highly detailed",
    "A cinematic 8k photograph of a pirate captain with a tricorn hat and weathered coat on the deck of a tall ship at golden sunset, ocean spray, shot on 35mm lens, highly detailed",
    "A cinematic 8k photograph of a wise wizard in dark flowing robes holding a glowing staff in a vast ancient library filled with floating candles, shot on 35mm lens, highly detailed",
    "A cinematic 8k photograph of a samurai warrior in ornate feudal Japanese armour standing in a garden of falling cherry blossoms, soft morning light, shot on 35mm lens, highly detailed",
    "A cinematic 8k photograph of a deep-sea scuba diver in a wetsuit swimming through a vibrant coral reef surrounded by tropical fish, underwater lighting, shot on 35mm lens, highly detailed",
    "A cinematic 8k photograph of a fighter pilot wearing an aviator helmet sitting in the cockpit of a jet with clouds streaking past, dramatic lighting, shot on 35mm lens, highly detailed",
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/transform', methods=['POST'])
def transform():
    prompt = random.choice(PROMPTS)

    try:
        result = fal_client.subscribe(
            FAL_MODEL,
            arguments={
                "prompt":        prompt,
                "num_images":    1,
                "aspect_ratio":  "1:1",
                "resolution":    "1K",
                "output_format": "jpeg",
                "seed":          random.randint(0, 999999),
            },
        )

        print(f"fal result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")

        images = result.get("images") or []
        if isinstance(images, dict):
            images = [images]

        if not images:
            return jsonify({"success": False, "error": f"No images in fal response: {result}"})

        image_url = images[0].get("url", "")
        if not image_url:
            return jsonify({"success": False, "error": "No image URL in fal response."})

        img_resp  = requests.get(image_url, timeout=30)
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
            "mode":    "text2img",
        })

    except Exception as e:
        print(f"fal error: {e}")
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
