from flask import Flask, request, Response
import requests
from urllib.parse import urlparse, urljoin, quote, unquote, quote_plus
import re
import time
from threading import Lock
import gc
from collections import OrderedDict
import base64

app = Flask(__name__)

# --- YAPILANDIRMA ---
CACHE_TTL = 30
MAX_CACHE_SIZE = 50
MAX_TS_SIZE = 5 * 1024 * 1024
MAX_TOTAL_CACHE_SIZE = 100 * 1024 * 1024

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
                timestamp, value = self.cache[key]
                if time.time() - timestamp < CACHE_TTL:
                    self.cache.move_to_end(key)
                    return value
                else:
                    self._remove_item(key)
            return None

    def put(self, key, value):
        with self.lock:
            value_size = len(value) if isinstance(value, (bytes, str)) else 0
            if self.max_item_size and value_size > self.max_item_size:
                return

            if key in self.cache:
                self._remove_item(key)

            while (len(self.cache) >= self.max_size or 
                   self.current_size + value_size > MAX_TOTAL_CACHE_SIZE):
                if not self.cache: break
                self._remove_oldest()

            self.cache[key] = (time.time(), value)
            self.current_size += value_size

    def _remove_item(self, key):
        if key in self.cache:
            _, value = self.cache.pop(key)
            self.current_size -= len(value) if isinstance(value, (bytes, str)) else 0

    def _remove_oldest(self):
        if self.cache:
            oldest_key = next(iter(self.cache))
            self._remove_item(oldest_key)

    def cleanup_expired(self):
        with self.lock:
            now = time.time()
            expired = [k for k, (t, _) in self.cache.items() if now - t >= CACHE_TTL]
            for k in expired: self._remove_item(k)

    def clear(self):
        with self.lock:
            self.cache.clear()
            self.current_size = 0

ts_cache = LRUCache(MAX_CACHE_SIZE, MAX_TS_SIZE)
key_cache = LRUCache(MAX_CACHE_SIZE // 2)

last_cleanup = time.time()
def periodic_cleanup():
    global last_cleanup
    if time.time() - last_cleanup > 60:
        ts_cache.cleanup_expired()
        key_cache.cleanup_expired()
        gc.collect()
        last_cleanup = time.time()

def extract_channel_id(url):
    patterns = [
        r'/sbs(\d+)/mono\.m3u8$',
        r'/watch/stream-(\d+)\.php$',
        r'/stream/stream-(\d+)\.php$',
        r'-(\d+)\.php$',
        r'(\d+)'
    ]
    for p in patterns:
        match = re.search(p, url)
        if match: return match.group(1)
    return None

def resolve_m3u8_link(url, headers=None):
    current_headers = headers or {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://inattv1289.xyz/'
    }
    
    try:
        # 1. Dinamik Base URL Al
        xml_res = requests.get('https://raw.githubusercontent.com/thecrewwh/dl_url/refs/heads/main/dl.xml', timeout=5)
        base_matches = re.findall(r'src\s*=\s*"([^"]*)', xml_res.text)
        if not base_matches: return {"resolved_url": None, "headers": current_headers}
        baseurl = base_matches[0]

        channel_id = extract_channel_id(url)
        if not channel_id: return {"resolved_url": None, "headers": current_headers}

        # 2. Stream Sayfası
        stream_url = urljoin(baseurl, f"stream/stream-{channel_id}.php")
        current_headers.update({'Referer': baseurl, 'Origin': baseurl.rstrip('/')})
        
        res = requests.get(stream_url, headers=current_headers, timeout=10)
        p2_links = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>.*?Player\s*2', res.text, re.DOTALL | re.IGNORECASE)
        if not p2_links: return {"resolved_url": None, "headers": current_headers}

        # 3. Player 2 Sayfası
        url2 = urljoin(baseurl, p2_links[0].replace('//cast', '/cast'))
        current_headers['Referer'] = url2
        
        res = requests.get(url2, headers=current_headers, timeout=10)
        iframes = re.findall(r'<iframe\s+src="([^"]*)', res.text)
        if not iframes: return {"resolved_url": None, "headers": current_headers}

        # 4. Iframe İçeriği ve Auth
        iframe_url = iframes[0]
        res = requests.get(iframe_url, headers=current_headers, timeout=10)
        content = res.text

        def get_b64(var_name, text):
            m = re.search(rf'{var_name}\s*=\s*atob\("([^"]*)"\)', text)
            return base64.b64decode(m.group(1)).decode('utf-8') if m else None

        auth_ts = get_b64('c', content)
        auth_rnd = get_b64('d', content)
        auth_sig = quote_plus(get_b64('e', content) or "")
        auth_host = get_b64('a', content)
        auth_php = get_b64('b', content)
        channel_key = (re.findall(r'channelKey\s*=\s*"([^"]*)"', content) or [None])[0]

        if not all([auth_ts, auth_host, channel_key]): return {"resolved_url": None, "headers": current_headers}

        # 5. Token Al ve Server Lookup
        auth_url = f"{auth_host}{auth_php}?channel_id={channel_key}&ts={auth_ts}&rnd={auth_rnd}&sig={auth_sig}"
        requests.get(auth_url, headers=current_headers, timeout=10)

        host_path = (re.findall(r'm3u8\s*=\s*.*?"([^"]*)"', content) or [""])[0]
        server_path = (re.findall(r'fetchWithRetry\(\s*\'([^\']*)', content) or [""])[0]
        
        lookup_url = f"https://{urlparse(iframe_url).netloc}{server_path}{channel_key}"
        server_data = requests.get(lookup_url, headers=current_headers, timeout=10).json()
        server_key = server_data.get('server_key')

        final_url = f"https://{server_key}{host_path}{server_key}/{channel_key}/mono.m3u8"
        ref = f"https://{urlparse(iframe_url).netloc}"
        
        return {
            "resolved_url": final_url,
            "headers": {"User-Agent": current_headers['User-Agent'], "Referer": ref, "Origin": ref}
        }
    except Exception as e:
        print(f"Hata: {e}")
        return {"resolved_url": None, "headers": current_headers}

@app.route('/proxy/m3u')
def proxy_m3u():
    periodic_cleanup()
    m3u_url = request.args.get('url', '').strip()
    if not m3u_url: return "URL eksik", 400

    res = resolve_m3u8_link(m3u_url)
    if not res["resolved_url"]: return "Çözülemedi", 500

    try:
        m3u_res = requests.get(res["resolved_url"], headers=res["headers"], timeout=10)
        m3u_res.raise_for_status()
        
        base_path = res["resolved_url"].rsplit('/', 1)[0] + "/"
        h_query = "&".join([f"h_{quote(k)}={quote(v)}" for k, v in res["headers"].items()])
        
        output = []
        for line in m3u_res.text.splitlines():
            line = line.strip()
            if not line: continue
            if line.startswith("#EXT-X-KEY"):
                m = re.search(r'URI="([^"]+)"', line)
                if m:
                    proxy_key = f"/proxy/key?url={quote(urljoin(base_path, m.group(1)))}&{h_query}"
                    line = line.replace(m.group(1), proxy_key)
            elif not line.startswith("#"):
                line = f"/proxy/ts?url={quote(urljoin(base_path, line))}&{h_query}"
            output.append(line)
            
        return Response("\n".join(output), content_type="application/vnd.apple.mpegurl")
    except Exception as e:
        return str(e), 500

@app.route('/proxy/ts')
def proxy_ts():
    ts_url = request.args.get('url')
    headers = {unquote(k[2:]).replace("_", "-"): unquote(v) for k, v in request.args.items() if k.startswith("h_")}
    
    cached = ts_cache.get(ts_url)
    if cached: return Response(cached, content_type="video/mp2t")

    try:
        r = requests.get(ts_url, headers=headers, timeout=10)
        if len(r.content) <= MAX_TS_SIZE:
            ts_cache.put(ts_url, r.content)
        return Response(r.content, content_type="video/mp2t")
    except: return "Hata", 500

@app.route('/proxy/key')
def proxy_key():
    key_url = request.args.get('url')
    headers = {unquote(k[2:]).replace("_", "-"): unquote(v) for k, v in request.args.items() if k.startswith("h_")}
    
    cached = key_cache.get(key_url)
    if cached: return Response(cached, content_type="application/octet-stream")

    try:
        r = requests.get(key_url, headers=headers, timeout=10)
        key_cache.put(key_url, r.content)
        return Response(r.content, content_type="application/octet-stream")
    except: return "Hata", 500

@app.route('/')
def index(): return "DaddyLive Proxy Aktif"

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=7860)
