# Party Pi — Konfiguration
# Kopiere diese Datei nach config.py und trage deine Werte ein.
# config.py wird NICHT ins Git eingecheckt.

# ── Web-Interface ─────────────────────────────────────────────────────────────

# Geheimer Schlüssel für Flask-Sessions (beliebiger langer zufälliger String)
SECRET_KEY = "aender-mich-bitte"

# PIN zum Einloggen ins Web-Interface
PIN = "DEINE_PIN"

# ── Spotify API ───────────────────────────────────────────────────────────────
# Erstellen unter: https://developer.spotify.com/dashboard
# Redirect URI dort eintragen: https://<RASPI_IP>:8443/callback

SPOTIFY_CLIENT_ID     = ""
SPOTIFY_CLIENT_SECRET = ""
SPOTIFY_REDIRECT_URI  = "https://192.168.0.X:8443/callback"

# ── Bluetooth-Geräte ──────────────────────────────────────────────────────────
# Schlüssel: beliebige ID (z.B. Seriennummer), Wert: MAC + Anzeigename
# MAC ermitteln: bluetoothctl -> devices
#
# Beispiel:
# DEVICES = {
#     "speaker1": {"mac": "AA:BB:CC:DD:EE:FF", "name": "Lautsprecher 1"},
#     "speaker2": {"mac": "AA:BB:CC:DD:EE:FF", "name": "Lautsprecher 2"},
# }

DEVICES = {
    "speaker1": {"mac": "XX:XX:XX:XX:XX:XX", "name": "Mein Lautsprecher"},
}

# ── Pfade ─────────────────────────────────────────────────────────────────────

# Wo der Spotify OAuth-Token gespeichert wird (ausserhalb des Repos!)
TOKEN_FILE = "/opt/party-pi/spotify_token.json"
