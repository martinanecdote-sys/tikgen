# 🎬 TikGen — Générateur de vidéos TikTok automatique

Génère des vidéos TikTok virales (script + voix + sous-titres + vidéo) en 1 clic depuis ton iPhone.

---

## 🚀 Déploiement en 15 minutes (100% gratuit)

### Étape 1 — Clé API Groq (gratuit)
1. Va sur **https://console.groq.com**
2. Crée un compte (gratuit)
3. Menu gauche → **API Keys** → **Create API Key**
4. Copie la clé (commence par `gsk_...`)

---

### Étape 2 — Clé API Pexels (gratuit)
1. Va sur **https://www.pexels.com/api/**
2. Clique **Get Started** → crée un compte gratuit
3. Va dans ton profil → **API** → copie ta clé

---

### Étape 3 — Déployer sur Render (gratuit)
1. Va sur **https://render.com** → crée un compte gratuit
2. Clique **New +** → **Web Service**
3. Choisis **Deploy an existing image or repo**
   - Si tu as GitHub : pousse ce dossier sur GitHub et connecte-le
   - Sinon : utilise l'option **Upload files** (ZIP du dossier)
4. Configure :
   - **Name** : tikgen (ou ce que tu veux)
   - **Region** : Frankfurt (EU)
   - **Build Command** : `apt-get update && apt-get install -y ffmpeg && pip install -r requirements.txt`
   - **Start Command** : `gunicorn app:app --workers 2 --timeout 300 --bind 0.0.0.0:$PORT`
   - **Plan** : Free
5. Dans **Environment Variables**, ajoute :
   - `GROQ_API_KEY` → ta clé Groq
   - `PEXELS_API_KEY` → ta clé Pexels
6. Clique **Create Web Service**

⏳ Le déploiement prend ~3-5 minutes.

---

### Étape 4 — Utiliser depuis l'iPhone
1. Render te donne une URL type `https://tikgen-xxxx.onrender.com`
2. Ouvre-la dans Safari
3. (Optionnel) Ajoute à l'écran d'accueil : partage → "Sur l'écran d'accueil"
4. Choisis ton sujet → **Générer la vidéo** → attends ~2 min → télécharge !
5. Poste sur TikTok

---

## ⚠️ Notes importantes

- **Temps de génération** : ~1-3 minutes par vidéo (normal)
- **Premier démarrage** : l'app se "réveille" en 30 sec après inactivité (tier gratuit Render)
- **Vidéo de fond** : fournie par Pexels (libre de droits ✅)
- **Voix** : Microsoft Edge TTS (gratuit, naturelle)
- **Script** : Llama 3.3 via Groq (gratuit, rapide)

---

## 💡 Conseils pour monétiser

- Poste **1-2 vidéos/jour** minimum
- Les 3 premières semaines : teste quels sujets fonctionnent le mieux
- Hook dans les 2 premières secondes = crucial
- Objectif : 10 000 abonnés + 100k vues/30j pour le Creator Rewards Program

---

## 📁 Structure du projet

```
tiktok-generator/
├── app.py              ← Serveur Flask
├── generator.py        ← Pipeline vidéo (script → voix → vidéo)
├── templates/
│   └── index.html      ← Interface mobile
├── requirements.txt
└── render.yaml         ← Config déploiement Render
```
