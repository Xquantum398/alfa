from flask import Flask, request, Response
import requests
from urllib.parse import urlparse, urljoin, quote, unquote
import time
from threading import Lock
from collections import OrderedDict
import gc

app = Flask(__name__)

# CACHE AYARLARI
CACHE_TTL = 30
MAX_CACHE_SIZE = 50
MAX_TS_SIZE = 5 * 1024 * 1024
MAX_TOTAL_CACHE_SIZE = 100 * 1024 * 1024

# ================= CACHE =================
class LRUCache:
    def __init__(self, max_size, max_item_size=None):
        self.max_size = max_size
        self.max_item_size = max_item_size
        self.cache = OrderedDict()
        self.lock = Lock()
        self.current_size = 0

    def get(self, key):
        with self.lock:
            if key in self.cache:
                ts, val = self.cache[key]
                if time.time() - ts < CACHE_TTL:
                    self.cache.move_to_end(key)
                    return val
                else:
                    self._remove(key)
            return None

    def put(self, key, value):
        with self.lock:
            size = len(value)
            if self.max_item_size and size > self.max_item_size:
                return

            if key in self.cache:
                self._remove(key)

            while len(self.cache) >= self.max_size or self.current_size + size > MAX_TOTAL_CACHE_SIZE:
                self._remove_oldest()

            self.cache[key] = (time.time(), value)
            self.current_size += size

    def _remove(self, key):
        if key in self.cache:
            _, val = self.cache[key]
            self.current_size -= len(val)
            del self.cache[key]

    def _remove_oldest(self):
        if self.cache:
            self._remove(next(iter(self.cache)))

ts_cache = LRUCache(MAX_CACHE_SIZE, MAX_TS_SIZE)
key_cache = LRUCache(20)

# ================= HEADER =================
def get_headers(url):
    parsed = urlparse(url)
    host = parsed.netloc

    # 🔥 inattv fix
    if "d72577a9dd0ec43.sbs" in host:
        return {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://inattv1285.xyz/",
            "Origin": "https://inattv1285.xyz"
        }

    base = f"{parsed.scheme}://{parsed.netloc}"
    return {
        "User-Agent": "Mozilla/5.0",
        "Referer": base + "/",
        "Origin": base
    }

# ================= M3U =================
@app.route('/proxy/m3u')
def proxy_m3u():
    url = request.args.get('url', '').strip()
    if not url:
        return "URL missing", 400

    headers = get_headers(url)

    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()

        content = r.text
        base = url.rsplit("/", 1)[0] + "/"

        headers_query = "&".join([
            f"h_{quote(k)}={quote(v)}" for k, v in headers.items()
        ])

        output = []

        for line in content.splitlines():
            line = line.strip()

            if line.startswith("#"):
                output.append(line)
                continue

            full = urljoin(base, line)
            proxied = f"/proxy/ts?url={quote(full)}&{headers_query}"
            output.append(proxied)

        return Response("\n".join(output),
                        content_type="application/vnd.apple.mpegurl")

    except Exception as e:
        return str(e), 500

# ================= TS =================
@app.route('/proxy/ts')
def proxy_ts():
    url = request.args.get('url', '')
    if not url:
        return "URL missing", 400

    headers = {
        unquote(k[2:]).replace("_", "-"): unquote(v)
        for k, v in request.args.items()
        if k.startswith("h_")
    }

    cached = ts_cache.get(url)
    if cached:
        return Response(cached, content_type="video/mp2t")

    try:
        r = requests.get(url, headers=headers, stream=True, timeout=10)
        r.raise_for_status()

        data = b''
        for chunk in r.iter_content(8192):
            data += chunk
            if len(data) > MAX_TS_SIZE:
                break

        ts_cache.put(url, data)
        return Response(data, content_type="video/mp2t")

    except Exception as e:
        return str(e), 500

# ================= KEY =================
@app.route('/proxy/key')
def proxy_key():
    url = request.args.get('url', '')
    if not url:
        return "URL missing", 400

    headers = {
        unquote(k[2:]).replace("_", "-"): unquote(v)
        for k, v in request.args.items()
        if k.startswith("h_")
    }

    cached = key_cache.get(url)
    if cached:
        return Response(cached, content_type="application/octet-stream")

    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()

        key_cache.put(url, r.content)
        return Response(r.content, content_type="application/octet-stream")

    except Exception as e:
        return str(e), 500

# ================= MAIN =================
@app.route('/')
def index():
    return "M3U8 Proxy OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860)
