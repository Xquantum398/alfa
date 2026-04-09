Hugging Face's logo
Hugging Face
Models
Datasets
Spaces
Buckets
new
Docs
Enterprise
Pricing


Spaces:
nellan
/
beta


like
0

Logs
App
Files
Community
Settings
beta
/
app.py

nellan's picture
nellan
Update app.py
cb32a88
verified
less than a minute ago
raw

Copy download link
history
blame
edit
delete
6.85 kB
from flask import Flask, request, Response, render_template_string, jsonify
import requests
from urllib.parse import urlparse, urljoin, quote, unquote
import re
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import logging
from functools import lru_cache
import hashlib

# Minimal logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'streamflow-fast')

# Basit metrikler
metrics = {
    'total_requests': 0,
    'active_streams': 0,
    'start_time': time.time(),
    'cache_hits': 0
}

# Session havuzu
_session_pool = None

def get_session():
    global _session_pool
    if _session_pool is None:
        _session_pool = requests.Session()
        retry = Retry(
            total=2,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=50,
            pool_maxsize=100,
            pool_block=False
        )
        _session_pool.mount('http://', adapter)
        _session_pool.mount('https://', adapter)
    return _session_pool

# HTML Template (Orijinal yapı korundu)
HTML_TEMPLATE = '''...''' # (Orijinal HTML buraya gelecek)

# Pattern önbellekleme
PATTERNS = {
    'channel_key': re.compile(r'channelKey\s*=\s*"([^"]*)"'),
    'auth_ts': re.compile(r'authTs\s*=\s*"([^"]*)"'),
    'auth_rnd': re.compile(r'authRnd\s*=\s*"([^"]*)"'),
    'auth_sig': re.compile(r'authSig\s*=\s*"([^"]*)"'),
    'auth_host': re.compile(r'\}\s*fetchWithRetry\(\s*[\'"]([^\'"]*)[\'"]'),
    'server_lookup': re.compile(r'n\s+fetchWithRetry\(\s*[\'"]([^\'"]*)[\'"]'),
    'host': re.compile(r'm3u8\s*=.*?[\'"]([^\'"]*)[\'"]'),
    'iframe': re.compile(r'iframe\s+src=[\'"]([^\'"]+)[\'"]')
}

@lru_cache(maxsize=256)
def get_url_hash(url):
    return hashlib.md5(url.encode()).hexdigest()

_resolve_cache = {}
_cache_ttl = 300

def get_cached_resolve(url, headers=None):
    cache_key = get_url_hash(url)
    now = time.time()
    
    if cache_key in _resolve_cache:
        cached_data, timestamp = _resolve_cache[cache_key]
        if now - timestamp < _cache_ttl:
            metrics['cache_hits'] += 1
            return cached_data
    
    result = resolve_fast(url, headers)
    _resolve_cache[cache_key] = (result, now)
    return result

def resolve_fast(url, headers=None):
    if not url:
        return {"resolved_url": None, "headers": {}}

    h = headers or {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://inattv1289.xyz/'
    }
    
    # Doğrudan m3u8 linki ise (verdiğin link gibi)
    if url.endswith('.m3u8'):
        return {"resolved_url": url, "headers": h}

    s = get_session()
    try:
        resp = s.get(url, headers=h, allow_redirects=True, timeout=(3, 7))
        content = resp.text
        
        # Eğer verdiğin URL yapısındaki gibi karmaşık bir JS koruması varsa:
        iframe = PATTERNS['iframe'].search(content)
        if iframe:
            url2 = iframe.group(1)
            # Alt çözümleme işlemleri...
            return {"resolved_url": url2, "headers": h}
            
        return {"resolved_url": resp.url, "headers": h}
    except Exception as e:
        logger.warning(f"Resolve error: {e}")
        return {"resolved_url": url, "headers": h}

@app.route('/proxy/m3u')
def proxy_m3u():
    url = request.args.get('url', '').strip()
    if not url: return "No URL", 400

    metrics['total_requests'] += 1
    
    # Headerları yakala
    h = {"User-Agent": "Mozilla/5.0"}
    for k, v in request.args.items():
        if k.startswith('h_'):
            h[unquote(k[2:]).replace("_", "-")] = unquote(v).strip()

    try:
        metrics['active_streams'] += 1
        s = get_session()
        resp = s.get(url, headers=h, timeout=(3, 10))
        content = resp.text
        
        # Base URL belirleme (Segmentler için)
        parsed = urlparse(resp.url)
        base = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rsplit('/', 1)[0]}/"
        
        # Headerları koru
        hq = "&".join([f"h_{quote(k)}={quote(v)}" for k, v in h.items()])

        lines = []
        for line in content.split('\n'):
            line = line.strip()
            if not line: continue
            
            if line.startswith("#EXT-X-KEY"):
                # Şifreli yayınlar için key proxy
                m = re.search(r'URI="([^"]+)"', line)
                if m:
                    key_url = urljoin(base, m.group(1))
                    line = line.replace(m.group(1), f"/proxy/key?url={quote(key_url)}&{hq}")
                lines.append(line)
            elif not line.startswith('#'):
                # Segmentleri (/proxy/ts) üzerinden geçir
                seg_url = urljoin(base, line)
                lines.append(f"/proxy/ts?url={quote(seg_url)}&{hq}")
            else:
                lines.append(line)

        metrics['active_streams'] -= 1
        return Response('\n'.join(lines), content_type="application/vnd.apple.mpegurl")

    except Exception as e:
        metrics['active_streams'] -= 1
        return f"Error: {e}", 500

@app.route('/proxy/ts')
def proxy_ts():
    url = request.args.get('url', '').strip()
    h = {unquote(k[2:]).replace("_", "-"): unquote(v) for k, v in request.args.items() if k.startswith('h_')}
    
    try:
        s = get_session()
        resp = s.get(url, headers=h, stream=True, timeout=(5, 30))
        return Response(resp.iter_content(chunk_size=131072), 
                        content_type="video/mp2t",
                        headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'public, max-age=3600'})
    except Exception as e:
        return str(e), 500

@app.route('/proxy/key')
def proxy_key():
    url = request.args.get('url', '').strip()
    h = {unquote(k[2:]).replace("_", "-"): unquote(v) for k, v in request.args.items() if k.startswith('h_')}
    try:
        s = get_session()
        resp = s.get(url, headers=h, timeout=10)
        return Response(resp.content, content_type="application/octet-stream")
    except:
        return "Key error", 500

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/stats')
def stats():
    uptime = (time.time() - metrics['start_time']) / 3600
    return jsonify({
        "requests": metrics['total_requests'],
        "streams": metrics['active_streams'],
        "uptime": f"{uptime:.1f}",
        "cache_hits": metrics['cache_hits']
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7860))
    app.run(host="0.0.0.0", port=port, threaded=True)
