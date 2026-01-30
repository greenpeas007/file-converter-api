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

**Important:** GitHub no longer accepts account passwords for Git. Use a [Personal Access Token (PAT)](https://github.com/settings/tokens) instead. When prompted for "Password", paste your PAT.

```bash
mkdir -p /opt/file-converter-api
cd /opt/file-converter-api

# Replace YOUR_USER with your GitHub username (e.g. greenpeas007)
git clone https://github.com/YOUR_USER/file-converter-api.git .

# When prompted:
#   Username: your-github-username
#   Password: your Personal Access Token (NOT your GitHub password)
```

**Or use SSH** (if you've added your SSH key to the server and to GitHub):

```bash
git clone git@github.com:YOUR_USER/file-converter-api.git .
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

### (Optional) Set API key for secured access

To require an API key on `/api/convert` and `/api/formats`, set `API_KEY` before starting:

```bash
export API_KEY="your-secret-key-here"
```

Or create a `.env` file in `/opt/file-converter-api`:

```
API_KEY=your-secret-key-here
```

Clients must send `X-API-Key: your-secret-key-here` or `Authorization: Bearer your-secret-key-here`. `/api/health` stays open (no key required).

### Build and run with Docker Compose

```bash
cd /opt/file-converter-api
docker compose build --no-cache
docker compose up -d
```

If you set `API_KEY` in the environment or in `.env`, it will be passed to the container automatically.

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

**If you set `API_KEY`** (master key), include it in requests to `/api/convert` and `/api/formats`. You can also create **consumer keys** for each app; consumers use their key the same way.

**Create a consumer key** (master key required):

```bash
curl -X POST "http://YOUR_VULTR_IP:5000/api/keys" \
  -H "X-API-Key: your-master-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-app"}'
# Returns: {"api_key": "...", "name": "my-app", "created_at": "...", "message": "Store this key securely; it will not be shown again."}
```

Give the returned `api_key` to the consumer; they use it as `X-API-Key` or `Authorization: Bearer <key>` for `/api/convert` and `/api/formats`. Consumer keys are stored in `data/api_keys.json` (persisted via Docker volume).

---

## 5. (Optional) HTTPS with a domain

You need a **domain** that points to your Vultr IP (e.g. `api.yourdomain.com` → `155.138.231.51`). Caddy will get a free TLS certificate from Let's Encrypt automatically.

### Step 1: Point your domain to the server

In your domain DNS (where you bought the domain), add an **A record**:

- **Name:** `api` (or `converter`, or `@` for root)
- **Value:** `YOUR_VULTR_IP` (e.g. `155.138.231.51`)
- **TTL:** 300 or default

Wait a few minutes for DNS to propagate.

### Step 2: Open ports 80 and 443 on the server

On the **Vultr server**:

```bash
ufw allow 80
ufw allow 443
ufw --force enable
ufw status
```

### Step 3: Install Caddy

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install -y caddy
```

### Step 4: Configure Caddy

Create or edit the Caddyfile (replace `api.yourdomain.com` with your domain):

```bash
nano /etc/caddy/Caddyfile
```

Put this in the file (one block only if this is your first site):

```
api.yourdomain.com {
    reverse_proxy localhost:5000
}
```

Save and exit (Ctrl+O, Enter, Ctrl+X).

### Step 5: Start Caddy

```bash
systemctl enable caddy
systemctl reload caddy
```

Caddy will request a certificate from Let's Encrypt. If DNS is correct, HTTPS will work in a minute.

### Step 6: Use HTTPS

- **Health:** `https://api.yourdomain.com/api/health`
- **Convert:** `https://api.yourdomain.com/api/convert?input_format=png&output_format=jpeg` (POST with body)
- **Formats:** `https://api.yourdomain.com/api/formats`

(Optional) To redirect HTTP → HTTPS, use this in `/etc/caddy/Caddyfile`:

```
api.yourdomain.com {
    reverse_proxy localhost:5000
}
http://api.yourdomain.com {
    redir https://api.yourdomain.com{uri} permanent
}
```

Then run `systemctl reload caddy`.

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
