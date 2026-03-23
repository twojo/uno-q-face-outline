import os
from flask import Flask, render_template, request, jsonify
from huggingface_hub import HfApi
from PIL import Image
import io
import base64

app = Flask(__name__)

hf_token = os.environ.get("HF_TOKEN")
hf_api = HfApi(token=hf_token)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search-models", methods=["GET"])
def search_models():
    query = request.args.get("query", "")
    limit = int(request.args.get("limit", 10))
    try:
        models = list(hf_api.list_models(search=query, limit=limit))
        model_list = [
            {
                "id": model.id,
                "downloads": getattr(model, "downloads", 0) or 0,
                "likes": getattr(model, "likes", 0) or 0,
                "pipeline_tag": getattr(model, "pipeline_tag", None),
            }
            for model in models
        ]
        return jsonify({"success": True, "models": model_list})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/image-info", methods=["POST"])
def image_info():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "No file selected"}), 400

    try:
        img_bytes = file.read()
        img = Image.open(io.BytesIO(img_bytes))

        thumbnail = img.copy()
        thumbnail.thumbnail((300, 300))

        thumb_buffer = io.BytesIO()
        fmt = img.format or "PNG"
        thumbnail.save(thumb_buffer, format=fmt)
        thumb_b64 = base64.b64encode(thumb_buffer.getvalue()).decode("utf-8")

        return jsonify({
            "success": True,
            "info": {
                "filename": file.filename,
                "format": img.format,
                "mode": img.mode,
                "width": img.width,
                "height": img.height,
                "size_kb": round(len(img_bytes) / 1024, 2),
            },
            "thumbnail": f"data:image/{(fmt).lower()};base64,{thumb_b64}",
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/create-image", methods=["POST"])
def create_image():
    data = request.get_json() or {}
    width = int(data.get("width", 200))
    height = int(data.get("height", 200))
    color = data.get("color", "blue")

    color_map = {
        "red": (220, 50, 50),
        "green": (50, 200, 80),
        "blue": (50, 100, 220),
        "yellow": (240, 200, 50),
        "purple": (150, 50, 200),
        "orange": (240, 130, 40),
        "white": (255, 255, 255),
        "black": (20, 20, 20),
    }
    rgb = color_map.get(color.lower(), (50, 100, 220))

    img = Image.new("RGB", (width, height), color=rgb)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return jsonify({
        "success": True,
        "image": f"data:image/png;base64,{img_b64}",
        "info": {"width": width, "height": height, "color": color},
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
