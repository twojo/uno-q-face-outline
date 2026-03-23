import os
import base64
import random
import time
import requests
import fal_client
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, static_folder='static', template_folder='templates')

app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB max request size

MAX_B64_SIZE = 2 * 1024 * 1024  # 2 MB max base64 image data
RATE_LIMIT_SECONDS = 5
_last_request_by_ip = {}

THEMES = {
    "Time Traveler": [
        "A close-up portrait of a person as an ancient Egyptian pharaoh wearing a golden nemes headdress and kohl eyeliner, inside a torch-lit pyramid chamber, photorealistic",
        "A close-up portrait of a person as a 1920s flapper at a speakeasy, sequined headband, art deco background, warm amber lighting, photorealistic",
        "A close-up portrait of a person as a Roman centurion in polished bronze armour with a red-plumed helmet, Colosseum behind them, photorealistic",
        "A close-up portrait of a person as a futuristic cyberpunk hacker with neon face tattoos, holographic HUD in front of their eyes, rain-soaked neon city, photorealistic",
    ],
    "Action Hero": [
        "A close-up portrait of a person as a fearless Viking warrior with war paint and a horned helmet on a misty battlefield, photorealistic",
        "A close-up portrait of a person as a samurai warrior in ornate black and gold armour, cherry blossom petals floating around, photorealistic",
        "A close-up portrait of a person as a space marine in heavy battle armour on an alien planet with two moons in the sky, photorealistic",
        "A close-up portrait of a person as a medieval knight in gleaming silver plate armour holding a flaming sword, epic storm clouds, photorealistic",
    ],
    "Fantasy Realm": [
        "A close-up portrait of a person as a powerful wizard with glowing blue eyes in a robe covered in arcane runes, ancient library background, photorealistic",
        "A close-up portrait of a person as an elf ranger with pointed ears and leaf-pattern cloak in an enchanted glowing forest, photorealistic",
        "A close-up portrait of a person as a dragon rider wearing scaled armour with a massive dragon visible behind them in flight, photorealistic",
        "A close-up portrait of a person as a vampire lord in a gothic castle, pale skin, crimson eyes, velvet cape, candlelight, photorealistic",
    ],
    "Explorer": [
        "A close-up portrait of a person as a NASA astronaut inside the International Space Station with Earth visible through the window, photorealistic",
        "A close-up portrait of a person as a deep-sea diver in a vintage brass diving helmet, underwater with bioluminescent jellyfish, photorealistic",
        "A close-up portrait of a person as an arctic explorer in a fur-lined parka on a frozen tundra with northern lights above, photorealistic",
        "A close-up portrait of a person as a jungle explorer with a weathered hat and binoculars in a dense tropical rainforest, photorealistic",
    ],
    "Pop Culture": [
        "A close-up portrait of a person as a retro disco king with a shiny jumpsuit, afro, and mirrored sunglasses on a light-up dance floor, photorealistic",
        "A close-up portrait of a person as a punk rocker with a tall mohawk, leather jacket covered in pins, on a concert stage, photorealistic",
        "A close-up portrait of a person as a classic Hollywood film noir detective in a trench coat and fedora, rainy alley with neon signs, photorealistic",
        "A close-up portrait of a person as a superhero in a gleaming suit with a flowing cape, standing on a rooftop at sunset overlooking a city, photorealistic",
    ],
    "Wild Card": [
        "A close-up portrait of a person as a mad scientist with wild hair and oversized goggles in a lab full of bubbling beakers and tesla coils, photorealistic",
        "A close-up portrait of a person as a pirate captain with a tricorn hat and golden tooth on the deck of a ghost ship in fog, photorealistic",
        "A close-up portrait of a person as a steampunk airship pilot wearing brass goggles and a leather aviator cap, clouds and gears behind them, photorealistic",
        "A close-up portrait of a person as a Western outlaw with a bandana and dusty hat in a saloon doorway at high noon, photorealistic",
    ],
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/themes', methods=['GET'])
def get_themes():
    return jsonify({"themes": list(THEMES.keys())})

@app.route('/transform', methods=['POST'])
def transform():
    ip = request.remote_addr or "unknown"
    now = time.time()
    last = _last_request_by_ip.get(ip, 0)
    if now - last < RATE_LIMIT_SECONDS:
        wait = int(RATE_LIMIT_SECONDS - (now - last)) + 1
        return jsonify({"success": False, "error": f"Please wait {wait}s before trying again."}), 429
    _last_request_by_ip[ip] = now

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid request."}), 400

    raw_image = data.get('image', '')
    if not isinstance(raw_image, str) or not raw_image:
        return jsonify({"success": False, "error": "No image provided."}), 400

    image_b64 = raw_image.split(',')[-1]
    if len(image_b64) > MAX_B64_SIZE:
        return jsonify({"success": False, "error": "Image too large. Use a smaller photo."}), 400

    if not image_b64:
        return jsonify({"success": False, "error": "No image data received."}), 400

    theme_name = data.get('theme')
    if theme_name and theme_name in THEMES:
        prompt = random.choice(THEMES[theme_name])
    else:
        theme_name = random.choice(list(THEMES.keys()))
        prompt = random.choice(THEMES[theme_name])

    face_data_uri = f"data:image/jpeg;base64,{image_b64}"

    try:
        print(f"[{theme_name}] Step 1: Generating themed image...")
        gen_result = fal_client.subscribe(
            "fal-ai/flux/schnell",
            arguments={
                "prompt": prompt,
                "image_size": "square",
                "num_images": 1,
                "seed": random.randint(0, 999999),
            },
        )

        gen_images = gen_result.get("images") or []
        if not gen_images:
            return jsonify({"success": False, "error": "Image generation failed."})

        base_image_url = gen_images[0].get("url", "")
        if not base_image_url:
            return jsonify({"success": False, "error": "Image generation failed."})

        print(f"Step 1 done. Step 2: Face swap...")
        swap_mode = "face-swap"
        final_url = ""
        try:
            swap_result = fal_client.subscribe(
                "fal-ai/face-swap",
                arguments={
                    "base_image_url": base_image_url,
                    "swap_image_url": face_data_uri,
                },
            )
            swap_image = swap_result.get("image") or {}
            if isinstance(swap_image, dict):
                final_url = swap_image.get("url", "")
            elif isinstance(swap_result.get("images"), list) and swap_result["images"]:
                final_url = swap_result["images"][0].get("url", "")
        except Exception as swap_err:
            print(f"Face swap failed (fallback): {swap_err}")
            swap_mode = "generated"

        if not final_url:
            final_url = base_image_url
            swap_mode = "generated"

        img_resp = requests.get(final_url, timeout=30)
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
            "image": f"data:{mime};base64,{result_b64}",
            "prompt": prompt,
            "theme": theme_name,
            "mode": swap_mode,
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"success": False, "error": "Transformation failed. Please try again."}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
