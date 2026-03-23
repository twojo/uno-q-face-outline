import os
import base64
import random
import requests
import fal_client
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, static_folder='static', template_folder='templates')

# fal_client reads FAL_KEY from the environment automatically

PROMPTS = [
    "A portrait photo of a fearless Viking warrior with braided beard and horned helmet on a snowy battlefield, dramatic lighting, photorealistic",
    "A portrait photo of a steampunk inventor wearing copper goggles and a leather vest in a workshop of brass machinery, photorealistic",
    "A portrait photo of a Royal Guard in full ceremonial red uniform standing outside Buckingham Palace, photorealistic",
    "A portrait photo of a medieval knight in gleaming full plate armour holding a broadsword, dramatic lighting, photorealistic",
    "A portrait photo of an astronaut in a NASA space suit on the lunar surface with Earth in the sky, photorealistic",
    "A portrait photo of a pirate captain with a tricorn hat on the deck of a tall ship at golden sunset, photorealistic",
    "A portrait photo of a wizard in dark flowing robes holding a glowing staff in an ancient library, photorealistic",
    "A portrait photo of a samurai warrior in ornate feudal Japanese armour with cherry blossoms falling, photorealistic",
    "A portrait photo of a deep-sea scuba diver in a wetsuit surrounded by tropical fish on a coral reef, photorealistic",
    "A portrait photo of a fighter pilot wearing an aviator helmet sitting in the cockpit of a jet, photorealistic",
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

    prompt        = random.choice(PROMPTS)
    face_data_uri = f"data:image/jpeg;base64,{image_b64}"

    try:
        # Step 1: Generate a themed character with FLUX Schnell (~$0.003)
        print(f"Step 1: Generating themed image...")
        gen_result = fal_client.subscribe(
            "fal-ai/flux/schnell",
            arguments={
                "prompt":     prompt,
                "image_size": "square",
                "num_images": 1,
                "seed":       random.randint(0, 999999),
            },
        )

        gen_images = gen_result.get("images") or []
        if not gen_images:
            return jsonify({"success": False, "error": "Image generation failed (no images returned)."})

        base_image_url = gen_images[0].get("url", "")
        if not base_image_url:
            return jsonify({"success": False, "error": "Image generation failed (no URL)."})

        print(f"Step 1 done: {base_image_url[:80]}...")

        # Step 2: Face-swap user's face onto the character (~$0.01)
        swap_mode = "face-swap"
        final_url = ""
        try:
            print(f"Step 2: Swapping face...")
            swap_result = fal_client.subscribe(
                "fal-ai/face-swap",
                arguments={
                    "base_image_url": base_image_url,
                    "swap_image_url": face_data_uri,
                },
            )

            print(f"Step 2 result keys: {list(swap_result.keys()) if isinstance(swap_result, dict) else type(swap_result)}")

            swap_image = swap_result.get("image") or {}
            if isinstance(swap_image, dict):
                final_url = swap_image.get("url", "")
            elif isinstance(swap_result.get("images"), list) and swap_result["images"]:
                final_url = swap_result["images"][0].get("url", "")

        except Exception as swap_err:
            print(f"Face swap failed (falling back to generated image): {swap_err}")
            swap_mode = "text2img"

        if not final_url:
            print("No face-swap URL; using generated image as fallback.")
            final_url  = base_image_url
            swap_mode  = "text2img"

        img_resp   = requests.get(final_url, timeout=30)
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
            "mode":    swap_mode,
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
