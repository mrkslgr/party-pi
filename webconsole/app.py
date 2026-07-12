from flask import Flask, jsonify, request, session, redirect, url_for
from flask_socketio import SocketIO
import subprocess
import re
import threading
import time
import os
import json
import requests as http
from datetime import timedelta

try:
    import config
except ImportError:
    raise SystemExit("config.py fehlt — kopiere config.example.py nach config.py und trage deine Werte ein.")

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.permanent_session_lifetime = timedelta(hours=24)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
PIN = config.PIN

DEVICES = config.DEVICES

SPOTIFY_CLIENT_ID     = config.SPOTIFY_CLIENT_ID
SPOTIFY_CLIENT_SECRET = config.SPOTIFY_CLIENT_SECRET
SPOTIFY_REDIRECT_URI  = config.SPOTIFY_REDIRECT_URI
SPOTIFY_SCOPES        = "user-read-playback-state user-modify-playback-state"
TOKEN_FILE            = config.TOKEN_FILE

# ── Spotify token management ──────────────────────────────────────────────────

_token_lock = threading.Lock()

def _load_token():
    try:
        with open(TOKEN_FILE) as f:
            return json.load(f)
    except Exception:
        return None

def _save_token(data):
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f)

def _refresh_token(token_data):
    r = http.post("https://accounts.spotify.com/api/token", data={
        "grant_type": "refresh_token",
        "refresh_token": token_data["refresh_token"],
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    })
    if r.ok:
        new = r.json()
        token_data["access_token"] = new["access_token"]
        token_data["expires_at"] = time.time() + new["expires_in"] - 60
        if "refresh_token" in new:
            token_data["refresh_token"] = new["refresh_token"]
        _save_token(token_data)
        return token_data
    return None

def get_access_token():
    with _token_lock:
        data = _load_token()
        if not data:
            return None
        if time.time() >= data.get("expires_at", 0):
            data = _refresh_token(data)
        return data["access_token"] if data else None

def spotify_get(path):
    token = get_access_token()
    if not token:
        return None
    r = http.get(f"https://api.spotify.com/v1/{path}",
                 headers={"Authorization": f"Bearer {token}"})
    return r if r.ok else None

def spotify_post(path):
    token = get_access_token()
    if not token:
        return False
    r = http.post(f"https://api.spotify.com/v1/{path}",
                  headers={"Authorization": f"Bearer {token}"})
    return r.status_code in (200, 204)

# ── Auth routes ───────────────────────────────────────────────────────────────

def requires_auth(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("auth"):
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

@app.route("/api/login", methods=["POST"])
def login():
    if request.json.get("pin") == PIN:
        session.permanent = True
        session["auth"] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 403

@app.route("/spotify/auth")
def spotify_auth():
    params = (
        f"client_id={SPOTIFY_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={SPOTIFY_REDIRECT_URI}"
        f"&scope={SPOTIFY_SCOPES.replace(' ', '%20')}"
    )
    return redirect(f"https://accounts.spotify.com/authorize?{params}")

@app.route("/callback")
def spotify_callback():
    code = request.args.get("code")
    if not code:
        return "Fehler: kein Code von Spotify", 400
    r = http.post("https://accounts.spotify.com/api/token", data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    })
    if not r.ok:
        return f"Token-Fehler: {r.text}", 500
    data = r.json()
    data["expires_at"] = time.time() + data["expires_in"] - 60
    _save_token(data)
    return redirect("/")

# ── Bluetooth ─────────────────────────────────────────────────────────────────

def mac_to_pcm(mac):
    return "/org/bluealsa/hci0/dev_{}/a2dpsrc/sink".format(mac.replace(":", "_"))

def bt_cmd(*args):
    result = subprocess.run(
        ["bluetoothctl", *args],
        capture_output=True, text=True, timeout=5
    )
    return result.stdout

def bt_powered():
    try:
        with open("/sys/class/bluetooth/hci0/powered") as f:
            return f.read().strip() == "1"
    except Exception:
        return "UP" in subprocess.run(["hciconfig", "hci0"], capture_output=True, text=True).stdout

def _bt_connections():
    out = subprocess.run(["hcitool", "con"], capture_output=True, text=True, timeout=5).stdout
    return out.upper()

def bt_connected(mac):
    return mac.upper() in _bt_connections()

def get_volume(mac):
    pcm = mac_to_pcm(mac)
    out = subprocess.run(
        ["bluealsa-cli", "volume", pcm],
        capture_output=True, text=True
    ).stdout
    m = re.search(r'L:\s*(\d+)', out)
    return round(int(m.group(1)) / 127 * 100) if m else None

def set_volume(mac, percent):
    val = round(max(0, min(100, percent)) / 100 * 127)
    subprocess.run(["bluealsa-cli", "volume", mac_to_pcm(mac), str(val), str(val)])

# ── API routes ────────────────────────────────────────────────────────────────

@app.route("/api/status")
@requires_auth
def status():
    powered = bt_powered()
    devices = {}
    for key, d in DEVICES.items():
        connected = bt_connected(d["mac"]) if powered else False
        devices[key] = {
            "name": d["name"],
            "connected": connected,
            "volume": get_volume(d["mac"]) if connected else None,
        }
    return jsonify({"powered": powered, "devices": devices})

@app.route("/api/power/on", methods=["POST"])
@requires_auth
def power_on():
    bt_cmd("power", "on")
    return jsonify({"ok": True})

@app.route("/api/power/off", methods=["POST"])
@requires_auth
def power_off():
    bt_cmd("power", "off")
    return jsonify({"ok": True})

@app.route("/api/connect/<key>", methods=["POST"])
@requires_auth
def connect(key):
    if key not in DEVICES:
        return jsonify({"ok": False}), 404
    bt_cmd("connect", DEVICES[key]["mac"])
    return jsonify({"ok": True})

@app.route("/api/volume/<key>", methods=["POST"])
@requires_auth
def volume_set(key):
    if key not in DEVICES:
        return jsonify({"ok": False}), 404
    val = request.json.get("volume", 80)
    set_volume(DEVICES[key]["mac"], int(val))
    return jsonify({"ok": True, "volume": int(val)})

_analysis_cache = {}  # track_id -> analysis data

@app.route("/api/player")
@requires_auth
def player_status():
    r = spotify_get("me/player")
    if not r or r.status_code == 204 or not r.content:
        return jsonify({"ok": False, "linked": bool(get_access_token())})
    try:
        d = r.json()
    except Exception:
        return jsonify({"ok": False, "linked": bool(get_access_token())})
    item = d.get("item") or {}
    artists = ", ".join(a["name"] for a in item.get("artists", []))
    track_id = item.get("id", "")
    return jsonify({
        "ok": True,
        "linked": True,
        "playing": d.get("is_playing", False),
        "track": item.get("name", ""),
        "artist": artists,
        "album_art": (item.get("album", {}).get("images") or [{}])[0].get("url", ""),
        "progress": d.get("progress_ms", 0),
        "duration": item.get("duration_ms", 0),
        "track_id": track_id,
    })

@app.route("/api/analysis/<track_id>")
@requires_auth
def track_analysis(track_id):
    if track_id in _analysis_cache:
        return jsonify(_analysis_cache[track_id])
    r = spotify_get(f"audio-analysis/{track_id}")
    if not r or not r.content:
        return jsonify({"ok": False})
    try:
        data = r.json()
    except Exception:
        return jsonify({"ok": False})
    # extract segments: start, duration, loudness_max, pitches[12]
    segments = [
        {
            "s": round(seg["start"], 3),
            "d": round(seg["duration"], 3),
            "l": round(seg.get("loudness_max", -60), 2),
            "p": [round(x, 2) for x in seg.get("pitches", [0]*12)],
        }
        for seg in data.get("segments", [])
    ]
    beats = [round(b["start"], 3) for b in data.get("beats", [])]
    result = {"ok": True, "segments": segments, "beats": beats}
    _analysis_cache[track_id] = result
    return jsonify(result)

@app.route("/api/player/next", methods=["POST"])
@requires_auth
def player_next():
    return jsonify({"ok": spotify_post("me/player/next")})

@app.route("/api/player/previous", methods=["POST"])
@requires_auth
def player_prev():
    return jsonify({"ok": spotify_post("me/player/previous")})

@app.route("/api/player/pause", methods=["POST"])
@requires_auth
def player_pause():
    return jsonify({"ok": spotify_post("me/player/pause")})

@app.route("/api/player/play", methods=["POST"])
@requires_auth
def player_play():
    return jsonify({"ok": spotify_post("me/player/play")})

@app.route("/tv")
def tv():
    with open("/opt/party-pi/webconsole/tv.html") as f:
        return f.read()

@app.route("/")
def index():
    with open("/opt/party-pi/webconsole/index.html") as f:
        return f.read()

# ── Background: auto-connect ──────────────────────────────────────────────────

def auto_connect_loop():
    while True:
        if bt_powered():
            for d in DEVICES.values():
                if not bt_connected(d["mac"]):
                    bt_cmd("connect", d["mac"])
        time.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=auto_connect_loop, daemon=True).start()
    from audio import start_audio_thread
    start_audio_thread(socketio)
    ssl = ("/opt/party-pi/cert.pem", "/opt/party-pi/key.pem")
    threading.Thread(target=lambda: socketio.run(app, host="0.0.0.0", port=8443, ssl_context=ssl, allow_unsafe_werkzeug=True), daemon=True).start()
    socketio.run(app, host="0.0.0.0", port=8080, allow_unsafe_werkzeug=True)
