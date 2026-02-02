# API Keys & Credentials Configuration

All API keys and credentials are managed through the `.env` file. Never commit `.env` to version control.

## Setup

```bash
nano .env
```

Edit the `.env` file directly and add your credentials.

---

## Required Keys

### Groq API Key (REQUIRED)

**Generates video ideas using Groq's Mixtral 8x7B LLM**

1. Go to [console.groq.com](https://console.groq.com)
2. Create an account or sign in
3. Navigate to API Keys
4. Create a new API key
5. Copy and paste into `.env`:

```env
GROQ_API_KEY=gsk_your_actual_key_here
```

**Status**: Required for video generation
**Used in**: `services/groq_service.py`

---

## Optional Keys (YouTube Upload)

For production uploads to YouTube, configure these keys:

### YouTube API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable YouTube Data API v3
4. Create OAuth 2.0 credentials (Desktop app)
5. Download and extract credentials:

```env
YOUTUBE_CLIENT_ID=xxx...xxx.apps.googleusercontent.com
YOUTUBE_CLIENT_SECRET=GOCSP...your_secret
YOUTUBE_REFRESH_TOKEN=1//xxx...your_token
```

**Status**: Optional (test mode works without it)
**Used in**: `uploader.py` for YouTube uploads
**Note**: Test mode (`python main.py --test`) does NOT require YouTube keys

---

## Local Service Keys (Not Required)

These local services typically don't require authentication:

### ComfyUI

```env
COMFYUI_HOST=127.0.0.1
COMFYUI_PORT=8188
```

- No API key needed
- Must be running locally
- Used for: Image generation via Stable Diffusion 1.5

### XTTS v2

```env
XTTS_HOST=127.0.0.1
XTTS_PORT=8000
```

- No API key needed
- Must be running locally
- Used for: Text-to-speech audio generation

---

## Key Management in Code

All keys are loaded from `.env` through `config.py`:

```python
# config.py
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
```

**Services accessing config:**

- `services/groq_service.py` → `Config.GROQ_API_KEY`
- `uploader.py` → `Config.YOUTUBE_CLIENT_ID`, etc.

---

## Security Best Practices

✅ **DO:**
- Keep `.env` in `.gitignore` (already configured)
- Use environment variables for secrets
- Rotate keys periodically
- Use service accounts where possible
- Limit key permissions to minimum needed

❌ **DON'T:**
- Commit `.env` to git
- Share API keys in messages
- Log API keys (they're masked in output)
- Use same key for multiple environments

---

## Quick Commands

```bash
# Edit .env with your API keys
nano .env

# Install dependencies
pip install -r requirements.txt

# Test pipeline (no uploads)
python main.py --test

# Run production (with uploads)
python main.py
```

---

## .env File Reference

All settings in `.env`:

---

## Troubleshooting

### "GROQ_API_KEY not set"

```
Error: GROQ_API_KEY environment variable not set
```

**Fix:**
1. Create `.env` from `.env.example`
2. Add your Groq API key
3. Restart the system

### "Invalid API key"

```
Error: Invalid API key or rate limited
```

**Fix:**
1. Check key is copied correctly (no extra spaces)
2. Verify key is active on Groq dashboard
3. Check rate limits
4. Create new key if needed

### "YouTube API credentials not found"

```
 not configured - uploads will not work in production mode
```

**Fix (for test mode):** No action needed - test mode works fine
**Fix (for production):** Add YouTube keys to `.env`

---

## API Key Locations

**Groq**: https://console.groq.com/keys

**YouTube**: https://console.cloud.google.com/apis/credentials

---

**Status**: ✅ All APIs configured through `.env` file
