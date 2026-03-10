import os
import uuid
import time
import threading
import glob
from flask import Flask, render_template, request, jsonify, send_file

from generator import VideoGenerator

app = Flask(__name__)

# In-memory job store
jobs = {}


def cleanup_old_files():
    """Delete temp video files older than 2 hours"""
    for f in glob.glob("/tmp/tiktok_*.mp4"):
        if time.time() - os.path.getmtime(f) > 7200:
            try:
                os.remove(f)
            except Exception:
                pass


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    gen = VideoGenerator()
    errors = gen.check_config()
    return jsonify({
        "status": "ok" if not errors else "config_error",
        "errors": errors
    })


@app.route("/generate", methods=["POST"])
def generate():
    cleanup_old_files()

    data = request.get_json() or {}
    niche = data.get("niche", "foot")

    if niche not in ["foot", "histoire", "quiz", "melange"]:
        return jsonify({"error": "Niche invalide"}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "running",
        "progress": "Démarrage...",
        "file": None,
        "script": None,
        "error": None,
        "created_at": time.time()
    }

    def run():
        try:
            gen = VideoGenerator()

            def update(msg):
                jobs[job_id]["progress"] = msg

            file_path, script = gen.create_video(niche, update)

            jobs[job_id]["status"] = "done"
            jobs[job_id]["file"] = file_path
            jobs[job_id]["script"] = script
            jobs[job_id]["progress"] = "✅ Vidéo prête !"

        except Exception as e:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = str(e)
            jobs[job_id]["progress"] = "❌ Erreur"

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"status": "not_found"})
    # Don't expose file path to client
    return jsonify({
        "status": job["status"],
        "progress": job["progress"],
        "script": job.get("script"),
        "error": job.get("error")
    })


@app.route("/download/<job_id>")
def download(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job introuvable"}), 404
    if job["status"] != "done" or not job["file"]:
        return jsonify({"error": "Vidéo pas encore prête"}), 400
    if not os.path.exists(job["file"]):
        return jsonify({"error": "Fichier introuvable"}), 404

    return send_file(
        job["file"],
        as_attachment=True,
        download_name="tiktok_video.mp4",
        mimetype="video/mp4"
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
