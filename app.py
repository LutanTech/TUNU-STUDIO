import os
import io
import math
from datetime import datetime
from flask import Flask, request, send_file, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from PIL import Image, ImageDraw

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WAVE_PATH = os.path.join(BASE_DIR, "wave.png")

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'covers.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class GeneratedCover(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(150), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    image_data = db.Column(db.LargeBinary, nullable=False)


with app.app_context():
    db.create_all()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        uploaded_file = request.files.get("image")
        if not uploaded_file or uploaded_file.filename == '':
            return "No image uploaded", 400

        try:
            bg_img = Image.open(uploaded_file.stream).convert("RGBA")
        except Exception:
            return "Invalid image", 400

        W, H = bg_img.size
        canvas = bg_img.copy()

        if os.path.exists(WAVE_PATH):
            wave_img = Image.open(WAVE_PATH).convert("RGBA")
            wave_h = int((wave_img.height / wave_img.width) * W)
            wave_img = wave_img.resize((W, wave_h), Image.Resampling.LANCZOS)
            canvas.paste(wave_img, (0, H - wave_h), wave_img)
        else:
            wave_h = int(H * 0.30)
            draw = ImageDraw.Draw(canvas)
            wave_points = [(0, H)]
            base_y = H - wave_h * 0.70
            amplitude = wave_h * 0.30

            for x in range(0, W + 1, 5):
                y = base_y - amplitude * math.sin((x / W) * math.pi * 1.1)
                wave_points.append((x, int(y)))
            wave_points.append((W, H))
            draw.polygon(wave_points, fill=(112, 0, 168, 255))

        output = io.BytesIO()
        canvas.save(output, format="PNG")
        png_data = output.getvalue()
        output.seek(0)

        try:
            new_cover = GeneratedCover(
                filename=f"wave_{uploaded_file.filename}",
                image_data=png_data
            )
            db.session.add(new_cover)
            db.session.commit()
        except Exception as e:
            print("Database save error:", e)

        return send_file(
            output, 
            mimetype="image/png",
            as_attachment=False,
            conditional=False
        )

    return render_template("index.html")


@app.route("/admin")
def admin():
    covers = GeneratedCover.query.order_by(GeneratedCover.timestamp.desc()).all()
    return render_template("admin.html", covers=covers)


@app.route("/cover/view/<int:cover_id>")
def view_cover(cover_id):
    cover = GeneratedCover.query.get_or_404(cover_id)
    return send_file(io.BytesIO(cover.image_data), mimetype="image/png")


@app.route("/cover/delete/<int:cover_id>", methods=["POST"])
def delete_cover(cover_id):
    cover = GeneratedCover.query.get_or_404(cover_id)
    db.session.delete(cover)
    db.session.commit()
    return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)