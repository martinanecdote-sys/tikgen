import asyncio
import os
import time
import json
import re
import tempfile
import shutil
import requests
import subprocess
import edge_tts
import static_ffmpeg
from groq import Groq

static_ffmpeg.add_paths()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

NICHES = {
    "foot": {
        "prompt": "Tu es un createur TikTok viral francophone. Genere un script de 180 mots sur une anecdote incroyable du football. Hook choc -> 4-5 faits -> question commentaires. Texte oral uniquement, pas de crochets ni titres.",
        "pexels_query": "football soccer stadium"
    },
    "histoire": {
        "prompt": "Tu es un createur TikTok viral francophone. Genere un script de 180 mots sur un fait historique choquant. Hook -> contexte -> fait incroyable -> twist -> question commentaires. Texte oral uniquement.",
        "pexels_query": "ancient castle medieval"
    },
    "quiz": {
        "prompt": "Tu es un createur TikTok viral francophone. Genere un script quiz de 180 mots avec 3 questions difficiles. '90% des gens ratent...' -> Q1+reponse -> Q2+reponse -> Q3+reponse -> 'Combien t-en as eu?'. Texte oral uniquement.",
        "pexels_query": "brain thinking knowledge"
    },
    "melange": {
        "prompt": "Tu es un createur TikTok viral francophone. Genere un script viral de 180 mots sur le sujet le plus viral du moment. Hook choc -> 4-5 points -> appel commentaires. Texte oral uniquement.",
        "pexels_query": "city timelapse aerial"
    }
}


class VideoGenerator:

    def __init__(self):
        self.groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

    def check_config(self):
        errors = []
        if not GROQ_API_KEY:
            errors.append("GROQ_API_KEY manquante")
        if not PEXELS_API_KEY:
            errors.append("PEXELS_API_KEY manquante")
        return errors

    def generate_script(self, niche):
        if not self.groq_client:
            raise Exception("Cle API Groq manquante")
        config = NICHES.get(niche, NICHES["foot"])
        response = self.groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": config["prompt"]}],
            max_tokens=650,
            temperature=0.9
        )
        script = response.choices[0].message.content.strip()
        script = re.sub(r'\[.*?\]', '', script)
        script = re.sub(r'\*+', '', script)
        return script.strip()

    def generate_tts(self, text, audio_path, vtt_path):
        asyncio.run(self._tts_async(text, audio_path, vtt_path))

    async def _tts_async(self, text, audio_path, vtt_path):
        communicate = edge_tts.Communicate(text, voice="fr-FR-HenriNeural", rate="+8%")
        word_timings = []
        with open(audio_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    word_timings.append({
                        "word": chunk["text"],
                        "offset": chunk["offset"] / 10_000_000,
                        "duration": chunk["duration"] / 10_000_000
                    })
        self._build_vtt(word_timings, vtt_path)

    def _build_vtt(self, word_timings, vtt_path):
        def fmt(t):
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = t % 60
            return "{:02d}:{:02d}:{:06.3f}".format(h, m, s)

        lines = ["WEBVTT", ""]
        for i in range(0, len(word_timings), 3):
            group = word_timings[i:i+3]
            start = group[0]["offset"]
            end = group[-1]["offset"] + group[-1]["duration"]
            text = " ".join(w["word"] for w in group)
            lines.append("{} --> {}".format(fmt(start), fmt(end)))
            lines.append(text)
            lines.append("")

        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def get_pexels_video(self, query, output_path):
        headers = {"Authorization": PEXELS_API_KEY}
        videos = []
        for orientation in ["portrait", "landscape"]:
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params={"query": query, "per_page": 10, "orientation": orientation},
                timeout=15
            )
            videos = resp.json().get("videos", [])
            if videos:
                break
        if not videos:
            raise Exception("Aucune video Pexels trouvee")
        for video in videos[:5]:
            files = sorted(video.get("video_files", []), key=lambda x: x.get("width", 0), reverse=True)
            for vf in files:
                link = vf.get("link", "")
                if link and vf.get("file_type", "").startswith("video"):
                    r = requests.get(link, stream=True, timeout=60)
                    r.raise_for_status()
                    with open(output_path, "wb") as out:
                        for chunk in r.iter_content(chunk_size=16384):
                            out.write(chunk)
                    return
        raise Exception("Impossible de telecharger la video Pexels")

    def get_audio_duration(self, audio_path):
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path],
            capture_output=True, text=True, check=True
        )
        return float(json.loads(result.stdout)["format"]["duration"])

    def style_subtitles(self, ass_path):
        with open(ass_path, "r", encoding="utf-8") as f:
            content = f.read()
        style = "Style: Default,Arial Black,78,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,1,0,1,5,2,2,20,20,110,1"
        content = re.sub(r"^Style: Default.*$", style, content, flags=re.MULTILINE)
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(content)

    def create_video(self, niche, progress_callback=None):
        tmpdir = tempfile.mkdtemp(prefix="tiktok_")
        try:
            audio_path = os.path.join(tmpdir, "audio.mp3")
            vtt_path = os.path.join(tmpdir, "subs.vtt")
            ass_path = os.path.join(tmpdir, "subs.ass")
            bg_path = os.path.join(tmpdir, "bg.mp4")
            output_path = os.path.join(tmpdir, "out.mp4")

            if progress_callback: progress_callback("Generation du script...")
            script = self.generate_script(niche)

            if progress_callback: progress_callback("Generation de la voix...")
            self.generate_tts(script, audio_path, vtt_path)

            if progress_callback: progress_callback("Telechargement video de fond...")
            config = NICHES.get(niche, NICHES["foot"])
            self.get_pexels_video(config["pexels_query"], bg_path)

            duration = self.get_audio_duration(audio_path)

            if progress_callback: progress_callback("Sous-titres...")
            subprocess.run(["ffmpeg", "-y", "-i", vtt_path, ass_path], check=True, capture_output=True)
            self.style_subtitles(ass_path)

            if progress_callback: progress_callback("Assemblage final...")
            ass_esc = ass_path.replace("\\", "/").replace(":", "\\:")
            vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,ass={}".format(ass_esc)
            subprocess.run([
                "ffmpeg", "-y",
                "-stream_loop", "-1", "-i", bg_path,
                "-i", audio_path,
                "-t", str(duration + 0.5),
                "-vf", vf,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart", "-shortest",
                output_path
            ], check=True, capture_output=True)

            final_path = "/tmp/tiktok_{}_{}.mp4".format(niche, int(time.time()))
            shutil.copy(output_path, final_path)
            return final_path, script

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
