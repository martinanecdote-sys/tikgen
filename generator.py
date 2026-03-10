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
from groq import Groq

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

NICHES = {
    "foot": {
        "prompt": """Tu es un créateur TikTok viral francophone expert en contenu foot.
Génère un script de 65-75 secondes (environ 180 mots) sur une anecdote incroyable et méconnue du football.

Structure OBLIGATOIRE:
- Hook choc en 1 phrase percutante (ex: "Cristiano Ronaldo a failli ne jamais jouer au foot...")
- 4-5 faits surprenants enchaînés rapidement
- Conclusion avec question pour les commentaires (ex: "Tu savais ça ? Dis-le en commentaire !")

RÈGLES:
- Texte oral uniquement, direct et dynamique
- Pas de titre, pas de [pause], pas de didascalies, pas de numérotation
- Phrases courtes, rythme rapide
- Vouvoie JAMAIS, tutoie toujours""",
        "pexels_query": "football soccer stadium crowd"
    },
    "histoire": {
        "prompt": """Tu es un créateur TikTok viral francophone expert en histoire.
Génère un script de 65-75 secondes (environ 180 mots) sur un fait historique choquant ou totalement méconnu.

Structure OBLIGATOIRE:
- Hook choc: une phrase qui donne envie de tout écouter
- Contexte rapide en 2 phrases
- Le fait incroyable avec 3-4 détails saisissants
- Twist final qui retourne le cerveau
- Question pour les commentaires

RÈGLES:
- Texte oral uniquement, pas de titre, pas de didascalies
- Phrases courtes, rythme soutenu
- Tutoie toujours""",
        "pexels_query": "ancient rome castle medieval"
    },
    "quiz": {
        "prompt": """Tu es un créateur TikTok viral francophone.
Génère un script quiz de 65-75 secondes (environ 180 mots) avec 3 questions difficiles.

Structure OBLIGATOIRE:
- Hook: "90% des gens ratent au moins une de ces 3 questions..."
- Question 1 → "La réponse c'est... [révélation surprenante avec explication]"
- Question 2 → même format
- Question 3 → même format  
- Conclusion: "Combien t'en as eu ? Dis-le en commentaire !"

RÈGLES:
- Texte oral uniquement, direct
- Pas de titre, pas de numéros visuels, pas de didascalies
- Questions sur un seul thème cohérent (sport OU culture OU science)""",
        "pexels_query": "question thinking knowledge"
    },
    "melange": {
        "prompt": """Tu es un créateur TikTok viral francophone.
Choisis UN des thèmes suivants (celui qui te semble le plus viral en ce moment):
- Anecdote incroyable sur le sport
- Fait historique choquant et méconnu
- Quiz ultra-difficile

Génère un script de 65-75 secondes (environ 180 mots) très viral sur ce thème.
Structure: Hook choc → développement captivant (4-5 points) → conclusion avec appel aux commentaires.
Texte oral uniquement, pas de titre ni didascalies. Tutoie toujours.""",
        "pexels_query": "city urban timelapse"
    }
}

class VideoGenerator:

    def __init__(self):
        self.groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

    def check_config(self):
        errors = []
        if not GROQ_API_KEY:
            errors.append("Variable d'environnement GROQ_API_KEY manquante")
        if not PEXELS_API_KEY:
            errors.append("Variable d'environnement PEXELS_API_KEY manquante")
        return errors

    def generate_script(self, niche):
        if not self.groq_client:
            raise Exception("Clé API Groq manquante. Vérifie les variables d'environnement.")
        config = NICHES.get(niche, NICHES["foot"])
        response = self.groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": config["prompt"]}],
            max_tokens=650,
            temperature=0.9
        )
        script = response.choices[0].message.content.strip()
        # Clean up any residual markdown or brackets
        script = re.sub(r'\[.*?\]', '', script)
        script = re.sub(r'\*+', '', script)
        script = re.sub(r'\n{3,}', '\n\n', script)
        return script.strip()

    async def _generate_tts(self, text, audio_path, vtt_path):
        communicate = edge_tts.Communicate(
            text,
            voice="fr-FR-HenriNeural",
            rate="+8%",
            pitch="+0Hz"
        )
        submaker = edge_tts.SubMaker()

        with open(audio_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    submaker.create_sub(
                        (chunk["offset"], chunk["duration"]),
                        chunk["text"]
                    )

        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write(submaker.generate_subs(words_in_cue=3))

    def get_pexels_video(self, query, output_path):
        if not PEXELS_API_KEY:
            raise Exception("Clé API Pexels manquante.")

        headers = {"Authorization": PEXELS_API_KEY}

        # Try portrait first
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
            raise Exception(f"Aucune vidéo Pexels trouvée pour '{query}'")

        # Pick best quality file
        for video in videos[:5]:
            files = sorted(
                video.get("video_files", []),
                key=lambda x: x.get("width", 0),
                reverse=True
            )
            for f in files:
                link = f.get("link", "")
                if link and f.get("file_type", "").startswith("video"):
                    r = requests.get(link, stream=True, timeout=60)
                    r.raise_for_status()
                    with open(output_path, "wb") as out:
                        for chunk in r.iter_content(chunk_size=16384):
                            out.write(chunk)
                    return

        raise Exception("Impossible de télécharger la vidéo de fond Pexels")

    def get_audio_duration(self, audio_path):
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path],
            capture_output=True, text=True, check=True
        )
        return float(json.loads(result.stdout)["format"]["duration"])

    def style_subtitles(self, ass_path):
        """Apply TikTok-style bold white text with black outline"""
        with open(ass_path, "r", encoding="utf-8") as f:
            content = f.read()

        # TikTok style: big white bold text, thick black outline, bottom center
        tiktok_style = (
            "Style: Default,Arial Black,78,&H00FFFFFF,&H00FFFFFF,"
            "&H00000000,&H90000000,-1,0,0,0,100,100,1,0,1,5,2,2,20,20,110,1"
        )
        content = re.sub(r"^Style: Default.*$", tiktok_style, content, flags=re.MULTILINE)

        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(content)

    def create_video(self, niche, progress_callback=None):
        tmpdir = tempfile.mkdtemp(prefix="tiktok_")

        try:
            audio_path  = os.path.join(tmpdir, "audio.mp3")
            vtt_path    = os.path.join(tmpdir, "subs.vtt")
            ass_path    = os.path.join(tmpdir, "subs.ass")
            bg_path     = os.path.join(tmpdir, "background.mp4")
            output_path = os.path.join(tmpdir, "output.mp4")

            # ── 1. Script ──────────────────────────────────────
            if progress_callback: progress_callback("📝 Génération du script...")
            script = self.generate_script(niche)

            # ── 2. TTS + subtitles ─────────────────────────────
            if progress_callback: progress_callback("🎙️ Génération de la voix...")
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._generate_tts(script, audio_path, vtt_path))
            finally:
                loop.close()

            # ── 3. Background video ────────────────────────────
            if progress_callback: progress_callback("🎬 Téléchargement de la vidéo de fond...")
            config = NICHES.get(niche, NICHES["foot"])
            self.get_pexels_video(config["pexels_query"], bg_path)

            # ── 4. Audio duration ──────────────────────────────
            duration = self.get_audio_duration(audio_path)

            # ── 5. Subtitles: VTT → ASS → styled ──────────────
            if progress_callback: progress_callback("✏️ Mise en forme des sous-titres...")
            subprocess.run(
                ["ffmpeg", "-y", "-i", vtt_path, ass_path],
                check=True, capture_output=True
            )
            self.style_subtitles(ass_path)

            # ── 6. Assemble ────────────────────────────────────
            if progress_callback: progress_callback("🎞️ Assemblage de la vidéo finale...")

            # Escape the ASS path for ffmpeg filter (handle special chars)
            ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")

            vf = (
                "scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,"
                f"ass={ass_escaped}"
            )

            subprocess.run([
                "ffmpeg", "-y",
                "-stream_loop", "-1",
                "-i", bg_path,
                "-i", audio_path,
                "-t", str(duration + 0.5),
                "-vf", vf,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                "-shortest",
                output_path
            ], check=True, capture_output=True)

            # ── 7. Save to /tmp for serving ────────────────────
            final_path = f"/tmp/tiktok_{niche}_{int(time.time())}.mp4"
            shutil.copy(output_path, final_path)

            return final_path, script

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
