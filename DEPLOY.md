# Always-Online Hosting (Option B)

Your laptop sleep/shutdown will **always** stop Option A tunnels.
To stay online even when the laptop is off, host the app on a cloud VPS.

## Critical camera rule

| Setup | Works when laptop is off? |
|--|--|
| Laptop webcam + tunnel | No |
| Cloud VPS + IP/RTSP camera | Yes |
| Cloud VPS + laptop webcam | No (no webcam on the server) |

For true 24/7 security monitoring you need an **IP camera** (or phone IP-webcam app) that stays powered.

## Recommended: DigitalOcean Droplet

### 1) Create server
1. Sign up at https://www.digitalocean.com
2. Create Droplet:
   - Image: Ubuntu 22.04
   - Size: at least **4 GB RAM** (8 GB better for YOLO/DeepFace)
   - Region: nearest to you
3. Add your SSH key and create

### 2) Point a domain (optional)
Example: `security.yourdomain.com` → Droplet public IP

### 3) Install Docker on the server

```bash
ssh root@YOUR_SERVER_IP
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose-plugin git
```

### 4) Deploy this project

```bash
git clone https://github.com/k-v-jaswanth/Real-Time-AI-Security-System.git
cd Real-Time-AI-Security-System
cp .env.example .env
nano .env
```

Set in `.env`:

```env
SECURITY_EMAIL=realtimesecuritysystem@gmail.com
SECURITY_EMAIL_PASSWORD=your-app-password
SECURITY_ALERT_RECIPIENT=friend1@gmail.com
SECURITY_ALERT_RECIPIENT_2=friend2@gmail.com
CAMERA_SOURCE=rtsp://user:pass@YOUR_CAMERA_IP:554/stream1
PORT=5000
```

Then start:

```bash
docker compose up -d --build
```

Open:

- `http://YOUR_SERVER_IP:5000`
- or your domain if configured

### 5) Keep it online
Docker is set with `restart: unless-stopped`, so it comes back after server reboot.

## Cheaper temporary alternative

Buy/keep a cheap always-on mini PC or Raspberry Pi at home:
1. Connect a USB camera
2. Run `python main.py`
3. Use Cloudflare Tunnel / localtunnel

That also survives your laptop shutdown (but not home power cuts).

## What this repo now includes for Option B
- `Dockerfile`
- `docker-compose.yml`
- `requirements-cloud.txt`
- `CAMERA_SOURCE` support for IP/RTSP cameras

## Next action needed from you
Reply with one of these and I can continue setup with exact commands:

1. **I have / will buy an IP camera**
2. **I will use a phone IP webcam app**
3. **I only want the website online (no live camera when laptop is off)**
