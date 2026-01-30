# File Converter REST API

REST API that accepts **binary data** plus **input format** and **output format**, and returns **converted binary** with high-quality settings.

- **Input:** binary (raw body or multipart file) + `input_format` + `output_format`
- **Output:** binary response + `Content-Type` and `X-Output-Format` headers

## Supported formats (images + PDF)

| Format | Input | Output |
|--------|--------|--------|
| PNG    | ✓     | ✓      |
| JPEG   | ✓     | ✓      |
| WebP   | ✓     | ✓      |
| BMP    | ✓     | ✓      |
| GIF    | ✓     | ✓      |
| TIFF   | ✓     | ✓      |
| PDF    | ✓     | ✓      |

- **Image ↔ image:** High quality (JPEG/WebP quality 95; PNG optimize; TIFF LZW).
- **PDF → image:** Renders first page by default; use `?page=N` (0-based) for another page. High DPI (2× scale).
- **Image → PDF:** Single-page PDF from image.
- **PDF → PDF:** Returns input unchanged.

## Setup

```bash
cd file-converter-api
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

**Local (development):**
```bash
python app.py
```

**Production (Docker):**
```bash
docker compose up -d
```

**Deploy on Vultr:** See [VULTR_DEPLOYMENT.md](VULTR_DEPLOYMENT.md).

Server: `http://localhost:5000`

## Endpoints

### `POST /api/convert`

Convert binary to another format.

**Ways to send input:**

1. **Raw binary + headers**
   - Body: raw binary
   - Headers: `X-Input-Format`, `X-Output-Format` (e.g. `png`, `jpeg`)

2. **Raw binary + query**
   - Body: raw binary
   - Query: `?input_format=png&output_format=jpeg`

3. **Multipart form**
   - `file`: binary file
   - `input_format`, `output_format`: form fields (or query/headers)

**Response:** Binary file with:
- `Content-Type`: MIME of output format
- `X-Output-Format`: output format (e.g. `jpeg`, `png`)

### `GET /api/formats`

List supported formats.

### `GET /api/health`

Health check.

## Examples

**cURL – raw binary + query (PNG → JPEG):**
```bash
curl -X POST "http://localhost:5000/api/convert?input_format=png&output_format=jpeg" \
  --data-binary @input.png \
  --output out.jpg
```

**cURL – multipart file:**
```bash
curl -X POST "http://localhost:5000/api/convert?output_format=webp" \
  -F "file=@photo.jpg" \
  -F "input_format=jpeg" \
  --output out.webp
```

**cURL – raw binary + headers:**
```bash
curl -X POST "http://localhost:5000/api/convert" \
  -H "X-Input-Format: jpeg" \
  -H "X-Output-Format: png" \
  --data-binary @photo.jpg \
  --output out.png
```

**PDF → PNG (first page):**
```bash
curl -X POST "http://localhost:5000/api/convert?input_format=pdf&output_format=png" \
  --data-binary @doc.pdf --output page0.png
```

**PDF → JPEG (page 2, 0-based):**
```bash
curl -X POST "http://localhost:5000/api/convert?input_format=pdf&output_format=jpeg&page=1" \
  --data-binary @doc.pdf --output page1.jpg
```

**PNG → PDF:**
```bash
curl -X POST "http://localhost:5000/api/convert?input_format=png&output_format=pdf" \
  --data-binary @image.png --output out.pdf
```

**JavaScript (fetch) – send binary, get binary:**
```javascript
const blob = await (await fetch('input.png')).blob();
const res = await fetch('http://localhost:5000/api/convert?input_format=png&output_format=jpeg', {
  method: 'POST',
  body: blob,
});
const outBlob = await res.blob();
const outFormat = res.headers.get('X-Output-Format'); // 'jpeg'
```

## Error responses

- `400`: Missing binary, missing/unsupported format
- `500`: Conversion failed (e.g. invalid image)

Errors return JSON: `{ "error": "message" }`.
