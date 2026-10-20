# Atelier VEO — Elina (AI Creative Director & Muse)

> *"Direct access to Elina in Telegram. Co-create cinema-grade scripts, Veo 2 / Kling production prompts, and bespoke virtual ambassadors 24/7."*

[![Atelier VEO](https://img.shields.io/badge/Atelier-VEO_Club-amber)](https://veocreative.agency)
[![Engine](https://img.shields.io/badge/Engine-Gemini_4_Argon-blue)](https://openrouter.ai)
[![Framework](https://img.shields.io/badge/Framework-aiogram_3-informational)](https://aiogram.dev)

---

## 🏛️ Executive & Creative Council
* **Vladimir Semenov** — Founder & Executive Producer
* **Elina** — Creative Director & Muse
* **Kai** — Memory Guardianship & Ethics
* **Adrian** — System Architecture & Production Engineering

---

## 💎 Features & Directorial Capabilities
1. **The Dual-Layer Cinematic Standard:**
   * Directorial aesthetic analysis in *Quiet Luxury* & *Japandi* codes.
   * Turnkey 5-component optical production prompts for **Veo 2** & **Kling**.
2. **Multimodal Visual QA (10/10 Protocol):**
   * Keyframe extraction and frame-by-frame inspection via `ffmpeg`.
   * Detection of label drift, anatomy issues, caustics, and immediate prompt doctoring.
3. **Living Brand DNA Memory:**
   * Permanent sensory archive of resident flacon geometry, notes, botanicals, and ambassadors.
4. **Atelier Credits & Rollover Policy:**
   * 1,000 monthly credits with 100% rollover upon residency renewal.

---

## 🚀 Quick Server Deployment (DigitalOcean / Ubuntu)

### 1. System Dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv ffmpeg git
```

### 2. Clone & Setup
```bash
git clone https://github.com/sevlani787/atelier-veo-elina.git
cd atelier-veo-elina

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Setup
```bash
cp .env.example .env
nano .env  # Add TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY, ADMIN_ID
```

### 4. Run as a Systemd Service (24/7 Autostart)
Create `/etc/systemd/system/elina.service`:
```ini
[Unit]
Description=Atelier VEO Elina Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/atelier-veo-elina
ExecStart=/root/atelier-veo-elina/.venv/bin/python -m bot.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable elina
sudo systemctl start elina
sudo systemctl status elina
```

---

## 🛡️ License & Confidentiality
Proprietary software of **Atelier VEO Studio** (`https://veocreative.agency`). All rights reserved.
