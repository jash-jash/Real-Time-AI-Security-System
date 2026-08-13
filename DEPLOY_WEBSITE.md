# Website-Only Deploy (always online)

This mode keeps the **dashboard website** online even if your laptop is off.
Live camera/AI still needs your PC (or an IP camera on a bigger server).

## Fastest path: Render (free)

### 1) Push is already on GitHub
Repo: https://github.com/k-v-jaswanth/Real-Time-AI-Security-System

### 2) Create Render account
1. Go to https://render.com and sign up (GitHub login)
2. Click **New +** → **Web Service**
3. Connect GitHub and select `Real-Time-AI-Security-System`
4. Use these settings:

| Field | Value |
|--|--|
| Name | `real-time-security` |
| Runtime | Python |
| Build Command | `pip install -r requirements-web.txt` |
| Start Command | `gunicorn -b 0.0.0.0:$PORT app:app` |
| Instance | Free |

### 3) Environment variables
In Render → Environment, add:

```text
WEB_ONLY=true
SECURITY_EMAIL=realtimesecuritysystem@gmail.com
SECURITY_EMAIL_PASSWORD=your-app-password
SECURITY_ALERT_RECIPIENT=your-email@gmail.com
SECURITY_ALERT_RECIPIENT_2=optional-second@gmail.com
```

### 4) Deploy
Click **Create Web Service**. Wait 2–5 minutes.

Your live site will look like:

`https://real-time-security.onrender.com`

That URL stays online even when your laptop sleeps/shuts down.

## What works online
- Dashboard UI
- Navigation / branding
- Events list (cloud instance)
- Recipient settings UI

## What still needs your PC
- Live webcam
- Unauthorized face detection
- Snapshot email alerts from camera

Run locally for full AI:

```powershell
python main.py
```

## Alternative one-click from Blueprint
If Render asks for Blueprint, select `render.yaml` from this repo.
