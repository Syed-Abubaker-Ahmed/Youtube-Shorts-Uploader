# Youtube-Shorts-Uploader
Orchestrates Groq LLM (ideas &amp; scripts), ComfyUI (image generation), XTTS v2 (voiceover), and FFmpeg (video assembly) into a production-ready pipeline with SQLite state tracking, error recovery, and optional auto-upload scheduling. Built for continuous, hands-off short-form video creation at scale.
## Setup

### Prerequisites
- Python 3.8+
- FFmpeg installed and in PATH
- Services running:
  - **Groq API**: Cloud LLM (API key required)
  - **ComfyUI**: Running on `127.0.0.1:8188`
  - **XTTS v2**: Running on `127.0.0.1:8000`

### Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env

# 3. Edit .env and add your GROQ_API_KEY
nano .env
```

### Configuration

All API keys and settings go in the `.env` file. Edit it directly to add your credentials:

```bash
nano .env
```

**Required keys:**
- `GROQ_API_KEY` - Groq LLM for video ideas

**Optional keys (YouTube upload):**
- `YOUTUBE_CLIENT_ID` - For YouTube OAuth
- `YOUTUBE_CLIENT_SECRET` - For YouTube OAuth
- `YOUTUBE_REFRESH_TOKEN` - For YouTube authentication

**See [KEYS.md](KEYS.md) for complete API key setup guide.**

## Starting Required Services

These services **must be running before** starting the automation.

### Start ComfyUI

```bash
cd ~/ComfyUI
source venv/bin/activate
python3 main.py --listen 127.0.0.1 --port 8188

```

Verify:

```bash
curl http://127.0.0.1:8188/system_stats
```

Output images directory (must exist):

```
/home/creation/ComfyUI/output/
```

---

### Start XTTS v2

```bash
cd ~/xtts_api
source venv/bin/activate
uvicorn api:app --host 127.0.0.1 --port 8000
```

XTTS runs on:

```
http://127.0.0.1:8000
```

Output audio directory (must exist):

```
/home/creation/xtts_api/output/
```

---

### Running

```bash
# Production mode (continuous generation + uploads)
source venv/bin/activate 
python main.py

# Test mode (continuous generation, no uploads)
python main.py --test
```

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│           YOUTUBE AUTOMATION SYSTEM                         │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
    ┌─────────┐      ┌─────────────┐      ┌──────────┐
    │  Groq   │      │ ComfyUI     │      │XTTS v2   │
    │  LLM    │      │ Image Gen   │      │Audio Gen │
    └─────────┘      └─────────────┘      └──────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                    ┌───────▼────────┐
                    │  Orchestrator  │
                    │   Pipeline     │
                    └───────┬────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
    ┌─────────┐      ┌─────────────┐      ┌──────────┐
    │Database │      │   FFmpeg    │      │  Upload  │
    │SQLite   │      │  Video Asm  │      │Scheduler │
    └─────────┘      └─────────────┘      └──────────┘
```

### Data Flow

```
1. Idea Generation
   Groq → VideoIdea (3 types)
   
2. Image Generation
   ComfyUI reads: /home/creation/ComfyUI/output/
   
3. Audio Generation
   XTTS reads: /home/creation/xtts_api/output/
   
4. Video Assembly
   FFmpeg creates 1080x1920 MP4 with H.264 + AAC
   Output: ./video/
   
5. Upload Scheduling (Production Mode Only)
   Random delay: 15-35 minutes
   Status: pending → uploaded
```

### Database Schema

```
video_ideas
  id, video_type, positive_prompt, negative_prompt, 
  narration_script, caption, created_at

jobs
  job_id, idea_id, status, image_path, audio_path, 
  video_path, created_at, updated_at, error_message

upload_jobs
  upload_id, video_path, video_type, scheduled_time, 
  uploaded_at, status, error_message

compilation_batches
  batch_id, video_ids, created_at, status
```

### File Structure

```
YouTube Automation/
├── main.py                  # Entry point with test mode
├── config.py               # Configuration management
├── logging_config.py       # Logging setup
├── orchestrator.py         # Video generation pipeline
├── uploader.py             # Upload scheduler
│
├── services/               # AI Service integrations
│   ├── __init__.py
│   ├── groq_service.py    # Groq LLM integration
│   ├── comfyui_service.py # Image generation
│   ├── xtts_service.py    # Audio generation
│   └── ffmpeg_service.py  # Video assembly
│
├── models/                 # Data structures
│   ├── __init__.py
│   └── video_idea.py      # VideoIdea, Job, UploadJob
│
├── database/               # Data persistence
│   ├── __init__.py
│   └── db_manager.py      # SQLite CRUD
│
├── utils/                  # Utilities
│   ├── __init__.py
│   ├── file_utils.py      # Safe file operations
│   ├── path_utils.py      # Absolute path management
│   └── validators.py      # Input validation
│
├── video/                  # Output directory (auto-created)
├── automation.db           # Database (auto-created)
├── app.log                 # Logs (auto-created)
│
├── README.md              # This file
├── requirements.txt       # Dependencies
└── .env.example          # Configuration template
```

### Components

**Groq Service**: Generates 20-30 video ideas per batch (3 types)

**ComfyUI Service**: Stable Diffusion 1.5 images, reads `/home/creation/ComfyUI/output/`

**XTTS Service**: Text-to-speech audio, reads `/home/creation/xtts_api/output/`

**FFmpeg Service**: Assembles 1080x1920 MP4 videos (20-30s)

**Orchestrator**: Coordinates full pipeline with error handling

**Database**: SQLite persistence with state tracking and recovery

---

## Running

### Production Mode

```bash
python main.py
```

- Continuous generation + upload scheduling
- Random delays: 15-35 minutes per video
- Creates compilations from 10+ videos
- Loops indefinitely until interrupted

**Output:**
- Videos: `./video/*.mp4`
- Database: `./automation.db`
- Logs: `./app.log` (rotating, 10MB, 5 backups)

### Test Mode (No Uploads)

```bash
python main.py --test
```

- Same as production but **skips uploads**
- Videos still created in `./video/`
- Perfect for:
  - Verifying services running correctly
  - Testing video quality
  - Debugging without upload overhead
  - Validating complete pipeline

---

## Key Features

- ✅ Modular AI services (independent, swappable)
- ✅ Error handling & graceful failures
- ✅ State persistence (resume from failures)
- ✅ Absolute paths (no directory traversal)
- ✅ Read-only external (never modifies ComfyUI/XTTS)
- ✅ Production safe (signal handling, shutdown)
- ✅ Comprehensive logging (file + console)

---

## Troubleshooting

### ComfyUI Service Fails

```
Error: No image found in ComfyUI output after timeout
```

**Check:**
- ComfyUI running: `curl http://127.0.0.1:8188/system_stats`
- Output exists: `/home/creation/ComfyUI/output/`
- Logs: `tail -f app.log`

### XTTS Service Fails

```
Error: XTTS output file not found after timeout
```

**Check:**
- XTTS running: `curl http://127.0.0.1:8000/`
- Output exists: `/home/creation/xtts_api/output/`

### Groq API Error

```
Error: Invalid API key or rate limited
```

**Check:**
- `.env` has valid `GROQ_API_KEY`
- API permissions correct
- Check rate limits on Groq dashboard

### FFmpeg Errors

```
Error: FFmpeg command failed
```

**Check:**
- FFmpeg installed: `ffmpeg -version`
- In PATH: `which ffmpeg`

---

## Commands

```bash
# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
nano .env  # Add GROQ_API_KEY

# Test pipeline
python main.py --test

# Run production
python main.py

# Monitor logs
tail -f app.log

# Check database
sqlite3 automation.db
SELECT COUNT(*) FROM video_ideas WHERE used = 0;

# Stop (Ctrl+C)
```

---

**Status**: ✅ Production Ready | **Version**: 1.0 | **Python**: 3.8+ |
See product on https://www.youtube.com/@AutomationSparkys
