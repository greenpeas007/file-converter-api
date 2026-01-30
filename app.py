"""
REST API: accepts binary data + input/output format, returns converted binary.
Supports image formats (PNG, JPEG, WebP, BMP, GIF, TIFF) and PDF.
Optional API key auth: master key (env API_KEY) or consumer keys (created via POST /api/keys).
Send X-API-Key or Authorization: Bearer <key>.
"""
import io
import json
import os
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, request, Response, jsonify
from flask_cors import CORS

try:
    from PIL import Image
except ImportError:
    Image = None
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

app = Flask(__name__)
CORS(app)

# Master key (env): used to create consumer keys and to access all APIs. Consumer keys (stored in file) can access convert/formats only.
API_KEY = os.environ.get("API_KEY")
API_KEYS_FILE = os.environ.get("API_KEYS_FILE", "data/api_keys.json")
CONSUMER_KEYS = {}  # key_string -> {"name": str, "created_at": str}
_keys_lock = threading.Lock()


def _load_consumer_keys():
    global CONSUMER_KEYS
    path = Path(API_KEYS_FILE)
    if not path.exists():
        CONSUMER_KEYS = {}
        return
    try:
        with open(path, "r") as f:
            data = json.load(f)
        CONSUMER_KEYS = {item["key"]: {"name": item["name"], "created_at": item["created_at"]} for item in data.get("keys", [])}
    except (json.JSONDecodeError, KeyError, OSError):
        CONSUMER_KEYS = {}


def _save_consumer_keys():
    path = Path(API_KEYS_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump({"keys": [{"key": k, "name": v["name"], "created_at": v["created_at"]} for k, v in CONSUMER_KEYS.items()]}, f, indent=2)


_load_consumer_keys()

IMAGE_FORMATS = {"png", "jpeg", "webp", "bmp", "gif", "tiff"}
ALL_INPUT_FORMATS = IMAGE_FORMATS | {"pdf"}
ALL_OUTPUT_FORMATS = IMAGE_FORMATS | {"pdf"}


def normalize_format(fmt):
    if not fmt:
        return None
    fmt = fmt.strip().lower()
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt == "tif":
        fmt = "tiff"
    if fmt in IMAGE_FORMATS or fmt == "pdf":
        return fmt
    return None


def get_binary_input():
    """Get binary body: from raw body or from multipart file."""
    if request.content_type and "multipart/form-data" in request.content_type:
        f = request.files.get("file")
        if f:
            return f.read()
        return None
    return request.get_data(cache=False)


def get_format_param(name, default=None):
    """Get format from query, form, or header."""
    # Query: ?input_format=png&output_format=jpeg
    q = request.args.get(name)
    if q:
        return q.strip()
    # Form (multipart)
    if request.form:
        q = request.form.get(name)
        if q:
            return q.strip()
    # Headers: X-Input-Format, X-Output-Format
    header = "X-" + name.replace("_", "-").title()
    h = request.headers.get(header)
    if h:
        return h.strip()
    return default


def _save_image_high_quality(img, output_fmt, buf):
    """Encode PIL Image to buffer in target format with high quality."""
    if output_fmt == "jpeg" and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    elif output_fmt == "jpeg" and img.mode != "RGB":
        img = img.convert("RGB")
    save_kw = {}
    pillow_format = {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP", "bmp": "BMP", "gif": "GIF", "tiff": "TIFF"}[output_fmt]
    if output_fmt == "jpeg":
        save_kw["quality"] = 95
        save_kw["subsampling"] = 0
    elif output_fmt == "webp":
        save_kw["quality"] = 95
    elif output_fmt == "png":
        save_kw["optimize"] = True
        save_kw["compress_level"] = 6
    elif output_fmt == "tiff":
        save_kw["compression"] = "tiff_lzw"
    img.save(buf, format=pillow_format, **save_kw)


def _image_mime(fmt):
    return {
        "png": "image/png",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "bmp": "image/bmp",
        "gif": "image/gif",
        "tiff": "image/tiff",
    }.get(fmt, "application/octet-stream")


def convert_image(binary_in, input_fmt, output_fmt):
    """Convert image binary to target format with high quality. Returns (bytes, mime_type)."""
    if not Image:
        raise RuntimeError("Pillow not installed")
    input_fmt = normalize_format(input_fmt)
    output_fmt = normalize_format(output_fmt)
    if not input_fmt or not output_fmt:
        raise ValueError("Unsupported or missing input/output format")
    if input_fmt not in IMAGE_FORMATS:
        raise ValueError(f"Unsupported input format: {input_fmt}")
    if output_fmt not in IMAGE_FORMATS:
        raise ValueError(f"Unsupported output format: {output_fmt}")

    img = Image.open(io.BytesIO(binary_in))
    buf = io.BytesIO()
    _save_image_high_quality(img, output_fmt, buf)
    return buf.getvalue(), _image_mime(output_fmt)


def convert_pdf_to_image(binary_in, output_fmt, page=0):
    """Render PDF page to image. Returns (bytes, mime_type). Page is 0-based."""
    if not fitz:
        raise RuntimeError("PyMuPDF not installed")
    if not Image:
        raise RuntimeError("Pillow not installed")
    output_fmt = normalize_format(output_fmt)
    if output_fmt not in IMAGE_FORMATS:
        raise ValueError(f"Unsupported output format: {output_fmt}")

    doc = fitz.open(stream=binary_in, filetype="pdf")
    if page < 0 or page >= len(doc):
        doc.close()
        raise ValueError(f"Page {page} out of range (document has {len(doc)} pages)")
    p = doc[page]
    # 2x scale for high quality (~144 DPI -> ~288 DPI)
    mat = fitz.Matrix(2.0, 2.0)
    pix = p.get_pixmap(matrix=mat, alpha=False)
    doc.close()

    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    buf = io.BytesIO()
    _save_image_high_quality(img, output_fmt, buf)
    return buf.getvalue(), _image_mime(output_fmt)


def convert_image_to_pdf(binary_in, input_fmt):
    """Convert image binary to PDF. Returns (bytes, mime_type)."""
    if not Image:
        raise RuntimeError("Pillow not installed")
    input_fmt = normalize_format(input_fmt)
    if input_fmt not in IMAGE_FORMATS:
        raise ValueError(f"Unsupported input format: {input_fmt}")

    img = Image.open(io.BytesIO(binary_in))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PDF")
    return buf.getvalue(), "application/pdf"


def convert_binary(binary_in, input_fmt, output_fmt, page=0):
    """Dispatch to the right converter. Returns (bytes, mime_type)."""
    input_fmt = normalize_format(input_fmt)
    output_fmt = normalize_format(output_fmt)
    if not input_fmt or not output_fmt:
        raise ValueError("Unsupported or missing input/output format")
    if input_fmt not in ALL_INPUT_FORMATS:
        raise ValueError(f"Unsupported input format: {input_fmt}")
    if output_fmt not in ALL_OUTPUT_FORMATS:
        raise ValueError(f"Unsupported output format: {output_fmt}")

    if input_fmt in IMAGE_FORMATS and output_fmt in IMAGE_FORMATS:
        return convert_image(binary_in, input_fmt, output_fmt)
    if input_fmt == "pdf" and output_fmt in IMAGE_FORMATS:
        return convert_pdf_to_image(binary_in, output_fmt, page=page)
    if input_fmt in IMAGE_FORMATS and output_fmt == "pdf":
        return convert_image_to_pdf(binary_in, input_fmt)
    if input_fmt == "pdf" and output_fmt == "pdf":
        return binary_in, "application/pdf"
    raise ValueError(f"Conversion from {input_fmt} to {output_fmt} not supported")


def _get_request_key():
    """Extract API key from X-API-Key or Authorization: Bearer header."""
    return request.headers.get("X-API-Key") or (
        request.headers.get("Authorization") or ""
    ).replace("Bearer ", "").strip()


def _require_api_key():
    """Return None if auth OK (master or consumer key), else (response, status_code)."""
    if not API_KEY and not CONSUMER_KEYS:
        return None
    key = _get_request_key()
    if not key:
        return jsonify({"error": "Missing or invalid API key"}), 401
    if API_KEY and key == API_KEY:
        return None
    if key in CONSUMER_KEYS:
        return None
    return jsonify({"error": "Missing or invalid API key"}), 401


def _require_master_key():
    """Return None if master key present, else (response, status_code). Used for POST/GET /api/keys."""
    if not API_KEY:
        return jsonify({"error": "API key management is not configured (set API_KEY)"}), 503
    key = _get_request_key()
    if not key or key != API_KEY:
        return jsonify({"error": "Missing or invalid API key"}), 401
    return None


@app.before_request
def check_api_key():
    if request.path == "/api/health":
        return None
    if request.path == "/api/keys":
        err = _require_master_key()
        if err:
            return err
        return None
    # /api/convert, /api/formats: require master or consumer key when any auth is configured
    err = _require_api_key()
    if err:
        return err
    return None


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "file-converter-api"})


@app.route("/api/convert", methods=["POST"])
def convert():
    """
    Convert binary file to another format.
    Input: binary (raw body or multipart 'file'), input_format, output_format.
    Output: binary response + headers Content-Type, X-Output-Format.
    """
    try:
        binary_in = get_binary_input()
        if not binary_in:
            return jsonify({"error": "No binary data: send raw body or multipart 'file'"}), 400

        input_format = get_format_param("input_format")
        output_format = get_format_param("output_format")
        if not output_format:
            return jsonify({"error": "output_format is required (query, form, or X-Output-Format)"}), 400
        if not input_format:
            return jsonify({"error": "input_format is required (query, form, or X-Input-Format)"}), 400

        page = 0
        if request.args.get("page") is not None:
            try:
                page = int(request.args.get("page"))
            except (TypeError, ValueError):
                pass

        out_bytes, mime = convert_binary(binary_in, input_format, output_format, page=page)
        fmt_header = normalize_format(output_format) or output_format.lower()
        if fmt_header == "jpg":
            fmt_header = "jpeg"
        ext = "pdf" if fmt_header == "pdf" else fmt_header

        resp = Response(out_bytes, status=200, mimetype=mime)
        resp.headers["X-Output-Format"] = fmt_header
        resp.headers["Content-Disposition"] = f"inline; filename=converted.{ext}"
        return resp
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"Conversion failed: {str(e)}"}), 500


@app.route("/api/formats", methods=["GET"])
def formats():
    """List supported input/output formats (images + PDF)."""
    return jsonify({
        "formats": ["png", "jpeg", "jpg", "webp", "bmp", "gif", "tiff", "tif", "pdf"],
        "note": "Use 'jpeg' or 'jpg' for JPEG; 'tiff' or 'tif' for TIFF. PDF: first page when converting to image; use ?page=N for other pages (0-based).",
    })


@app.route("/api/keys", methods=["POST"])
def create_api_key():
    """
    Create a new consumer API key. Requires master key (env API_KEY).
    Body (optional): {"name": "consumer-app-name"}.
    Returns the new key once; store it securely.
    """
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "consumer").strip() or "consumer"
    new_key = secrets.token_urlsafe(32)
    created_at = datetime.now(timezone.utc).isoformat()
    with _keys_lock:
        CONSUMER_KEYS[new_key] = {"name": name, "created_at": created_at}
        _save_consumer_keys()
    return jsonify({
        "api_key": new_key,
        "name": name,
        "created_at": created_at,
        "message": "Store this key securely; it will not be shown again.",
    }), 201


@app.route("/api/keys", methods=["GET"])
def list_api_keys():
    """List consumer key names and created_at (no key values). Requires master key."""
    with _keys_lock:
        items = [{"name": v["name"], "created_at": v["created_at"]} for v in CONSUMER_KEYS.values()]
    return jsonify({"keys": items})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
