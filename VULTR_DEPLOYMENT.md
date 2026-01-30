# Deploy File Converter API on Vultr

Steps to run the File Converter API on a Vultr cloud instance using Docker.

## Prerequisites

- Vultr account (https://www.vultr.com)
- SSH key or password for the instance

---

## 1. Create a Vultr instance

1. **Vultr Dashboard** → **Products** → **Deploy Server**
2. **Server type:** Regular Performance (or preferred plan)
3. **Size:** 1 vCPU, 1 GB RAM is enough for light use; use 2 GB+ for more traffic
4. **Location:** Choose nearest to your users
5. **OS:** **Ubuntu 22.04 LTS**
6. **SSH key:** Add your key (recommended)
7. Deploy and note the **server IP**

---

## 2. Connect and prepare the server

```bash
ssh root@YOUR_VULTR_IP
# Or: ssh ubuntu@YOUR_VULTR_IP if you created an ubuntu user
```

### Install Docker (if not already installed)

```bash
apt update && apt upgrade -y
apt install -y curl

curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

### Open firewall for the API port

```bash
# Allow HTTP (80) and HTTPS (443) if you'll put a reverse proxy in front
ufw allow 22
ufw allow 5000
# ufw allow 80
# ufw allow 443
ufw --force enable
```

---

## 3. Deploy the API

### Option A: Clone from Git (if the project is in a repo)

```bash
mkdir -p /opt/file-converter-api
cd /opt/file-converter-api

# Replace with your repo URL
git clone https://github.com/YOUR_USER/file-converter-api.git .
# Or copy only the needed files (see Option B)
```

### Option B: Copy project files from your machine

On your **local machine** (from the folder that contains `file-converter-api`):

```bash
scp -r file-converter-api root@YOUR_VULTR_IP:/opt/
```

Then on the server:

```bash
cd /opt/file-converter-api
```

### Build and run with Docker Compose

```bash
cd /opt/file-converter-api
docker compose build --no-cache
docker compose up -d
```

Check that the container is running:

```bash
docker compose ps
curl http://localhost:5000/api/health
```

You should see: `{"status":"ok","service":"file-converter-api"}`

---

## 4. Use the API

From anywhere (replace with your server IP):

```bash
curl http://YOUR_VULTR_IP:5000/api/health
curl http://YOUR_VULTR_IP:5000/api/formats
```

Convert a file (example: PNG → JPEG):

```bash
curl -X POST "http://YOUR_VULTR_IP:5000/api/convert?input_format=png&output_format=jpeg" \
  --data-binary @image.png --output out.jpg
```

---

## 5. (Optional) HTTPS with a domain

If you have a domain pointing to `YOUR_VULTR_IP` (e.g. `converter.yourdomain.com`):

1. Install Caddy (or Nginx) on the same server.
2. Reverse proxy to `http://127.0.0.1:5000`.

**Example with Caddy:**

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install caddy
```

Create `/etc/caddy/Caddyfile`:

```
converter.yourdomain.com {
    reverse_proxy localhost:5000
}
```

Reload Caddy:

```bash
systemctl reload caddy
```

Then use: `https://converter.yourdomain.com/api/convert` (Caddy will get a TLS cert automatically).

---

## 6. Updates and maintenance

**Restart the API:**

```bash
cd /opt/file-converter-api
docker compose restart
```

**Rebuild after code changes:**

```bash
cd /opt/file-converter-api
git pull   # if using Git
docker compose build --no-cache
docker compose up -d
```

**View logs:**

```bash
docker compose logs -f api
```

**Stop:**

```bash
docker compose down
```

---

## Quick reference

| Task              | Command |
|-------------------|--------|
| Start             | `docker compose up -d` |
| Stop              | `docker compose down` |
| Logs              | `docker compose logs -f api` |
| Rebuild & restart | `docker compose build --no-cache && docker compose up -d` |
| Health check      | `curl http://localhost:5000/api/health` |
