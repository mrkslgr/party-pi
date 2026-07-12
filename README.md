# Party Pi

Ein Raspberry Pi als Spotify-Connect-Empfänger mit Web-Interface zur Lautstärkeregelung und einem TV-Visualizer.

**Features:**
- Spotify Connect via [raspotify](https://github.com/dtcooper/raspotify) (librespot)
- Bluetooth-Audio zu einem oder mehreren Lautsprechern (BlueALSA)
- Web-Interface (PIN-geschützt): Lautstärke pro Box, BT-Verbindung, Spotify-Steuerung (Play/Pause/Skip)
- TV-Visualizer (`/tv`): 9 Effekte mit Auto-Cycle alle 60 Sekunden, Mikrofon-FFT via Web Audio API
- Party-Slogans mit Glitch-Effekt (random, alle 10–15 Sekunden)

---

## Raspberry Pi einrichten

### Hardware

- Raspberry Pi 4 (empfohlen) oder Pi 3B+
- MicroSD-Karte (mind. 8 GB, Class 10)
- Netzteil (Pi 4: USB-C, 5V/3A)
- Netzwerkverbindung (LAN-Kabel oder WLAN)

### OS flashen

1. [Raspberry Pi Imager](https://www.raspberrypi.com/software/) herunterladen und starten
2. **OS wählen:** `Raspberry Pi OS Lite (64-bit)` — kein Desktop nötig
3. **SD-Karte wählen**
4. Vor dem Flashen auf das **Zahnrad-Icon** klicken und konfigurieren:
   - Hostname: `party-pi`
   - SSH aktivieren (mit Passwort oder Public Key)
   - WLAN einrichten (SSID + Passwort)
   - Benutzername und Passwort setzen (z.B. `pi`)
   - Zeitzone: `Europe/Berlin`
5. SD-Karte flashen, in den Pi einlegen, Pi starten

### Ersten SSH-Login

```bash
ssh pi@party-pi.local
# oder per IP:
ssh pi@192.168.0.X
```

IP herausfinden falls unbekannt:
```bash
# Am Router nachschauen, oder:
ping party-pi.local
```

### System aktualisieren

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo reboot
```

---

## Voraussetzungen

- Raspberry Pi (getestet: Pi 4) mit Raspberry Pi OS (Bookworm)
- Python 3.10+
- Bluetooth-Lautsprecher
- Spotify Premium + Developer-Account

---

## Installation

### 1. Repo klonen

```bash
git clone https://github.com/DEIN_USER/party-pi.git /opt/party-pi
cd /opt/party-pi
```

### 2. Abhängigkeiten installieren

```bash
sudo apt-get install -y python3-pip bluez bluez-alsa-utils
pip3 install flask flask-socketio requests eventlet
```

raspotify installieren:

```bash
curl -sL https://dtcooper.github.io/raspotify/install.sh | sh
```

### 3. Konfiguration

```bash
cp webconsole/config.example.py webconsole/config.py
nano webconsole/config.py
```

Folgendes eintragen:
- `SECRET_KEY` — beliebiger langer zufälliger String (z.B. `python3 -c "import secrets; print(secrets.token_hex(32))"`)
- `PIN` — Login-PIN fürs Web-Interface
- `SPOTIFY_CLIENT_ID` + `SPOTIFY_CLIENT_SECRET` — aus dem [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
- `SPOTIFY_REDIRECT_URI` — `https://<IP-DES-PI>:8443/callback` (muss exakt so im Dashboard eingetragen sein)
- `DEVICES` — MAC-Adressen deiner Bluetooth-Lautsprecher (siehe Schritt 4)
- `TOKEN_FILE` — Pfad zum Spotify-Token (Standard: `/opt/party-pi/spotify_token.json`, außerhalb des Repos!)

### 4. Bluetooth-Lautsprecher koppeln

```bash
bluetoothctl
```

```
power on
agent on
scan on
# Warte bis dein Gerät erscheint, dann:
pair  XX:XX:XX:XX:XX:XX
trust XX:XX:XX:XX:XX:XX
connect XX:XX:XX:XX:XX:XX
exit
```

MAC-Adresse ablesen:

```bash
bluetoothctl devices
# oder verbundene Geräte:
hcitool con
```

Diese MACs in `config.py` unter `DEVICES` eintragen:

```python
DEVICES = {
    "box1": {"mac": "AA:BB:CC:DD:EE:FF", "name": "Wohnzimmer"},
    "box2": {"mac": "AA:BB:CC:DD:EE:FF", "name": "Küche"},
}
```

### 5. raspotify konfigurieren

Audio direkt per BlueALSA an den Lautsprecher routen (stabiler als pipe-Backend):

```bash
sudo nano /etc/raspotify/conf
```

```ini
LIBRESPOT_NAME="Party Pi"
LIBRESPOT_BITRATE="320"
LIBRESPOT_BACKEND="alsa"
LIBRESPOT_DEVICE="bluealsa:DEV=XX:XX:XX:XX:XX:XX,PROFILE=a2dp"
LIBRESPOT_INITIAL_VOLUME="100"
LIBRESPOT_VOLUME_CTRL="fixed"
```

> Trage bei `LIBRESPOT_DEVICE` die MAC des **primären** Lautsprechers ein.

```bash
sudo systemctl restart raspotify
```

### 6. SSL-Zertifikat erstellen

HTTPS ist erforderlich, damit der Browser Mikrofon-Zugriff für den TV-Visualizer erlaubt:

```bash
openssl req -x509 -newkey rsa:4096 -keyout /opt/party-pi/key.pem \
  -out /opt/party-pi/cert.pem -days 3650 -nodes \
  -subj "/CN=party-pi" \
  -addext "subjectAltName=IP:$(hostname -I | awk '{print $1}')"
```

Zertifikat und Key landen in `/opt/party-pi/` — außerhalb des Repos, werden nicht eingecheckt.

### 7. sudo-Berechtigung für bluetoothctl

Das Web-Interface verbindet Lautsprecher automatisch per bluetoothctl:

```bash
echo "$(whoami) ALL=(ALL) NOPASSWD: /usr/bin/bluetoothctl" | sudo tee /etc/sudoers.d/party-pi
```

### 8. Systemd-Service einrichten

```bash
sudo nano /etc/systemd/system/party-pi.service
```

```ini
[Unit]
Description=Party Pi Webconsole
After=network.target bluetooth.target

[Service]
ExecStart=/usr/bin/python3 /opt/party-pi/webconsole/app.py
WorkingDirectory=/opt/party-pi/webconsole
Restart=always
User=DEIN_USER

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable party-pi
sudo systemctl start party-pi
```

Service-Status prüfen:

```bash
sudo systemctl status party-pi
sudo journalctl -u party-pi -f
```

---

## Spotify OAuth verbinden

1. Im Browser `https://<IP>:8443/spotify/auth` öffnen
2. Selbstsigniertes Zertifikat akzeptieren (einmalig)
3. Spotify-Account autorisieren
4. Token wird automatisch in `TOKEN_FILE` gespeichert und bei Ablauf erneuert

> Der Token-File liegt außerhalb des Repos und wird nicht eingecheckt.

---

## Troubleshooting

**Port 8443 belegt nach Neustart:**
```bash
sudo fuser -k 8443/tcp
sudo systemctl restart party-pi
```

**`bluealsa-cli` meldet "maximum number of active connections":**

D-Bus Verbindungslimit erschöpft. Pi neu starten:
```bash
sudo reboot
```

**Bluetooth-Lautsprecher erscheint als "nicht verbunden" im Interface:**
```bash
hcitool con   # zeigt tatsächlich verbundene Geräte
```

**Spotify spielt auf falschem Gerät:**

Prüfe `LIBRESPOT_DEVICE` in `/etc/raspotify/conf` — MAC muss mit dem verbundenen Lautsprecher übereinstimmen.

---

## URLs

| URL | Beschreibung |
|-----|-------------|
| `http://<IP>:8080/` | Web-Interface (HTTP) |
| `https://<IP>:8443/` | Web-Interface (HTTPS) |
| `https://<IP>:8443/tv` | TV-Visualizer (HTTPS erforderlich für Mikrofon) |
| `https://<IP>:8443/spotify/auth` | Spotify OAuth starten |

---

## TV-Visualizer

Öffne `/tv` auf einem Fernseher oder Display. Beim ersten Laden auf **Mikrofon aktivieren** klicken — der Browser nutzt die Web Audio API für Echtzeit-FFT vom Mikrofon.

**9 Effekte (auto-cycle alle 60 Sekunden mit Crossfade):**

| Effekt | Beschreibung |
|--------|-------------|
| MIRROR | Bars oben+unten gespiegelt, Laser-Spokes aus der Mitte |
| BARS | Vertikale Bars mit horizontalen Laser-Scan-Lines |
| LASER | Rotierende Spoke-Passes + Full-Screen-Through-Lines |
| KREIS | 5 gegenläufige Ringe mit Spike-Krone |
| TUNNEL | Hexagon-Tunnel der auf dich zurast |
| STORM | Partikel-Explosion bei Bass-Kicks |
| GRID | Perspektiv-Raster (Boden + Decke) |
| AURORA | Nordlicht-Wellenbänder |
| VORTEX | 5-armige Spiralgalaxie |

Ein dünner Balken am unteren Rand zeigt den Countdown bis zum nächsten Effektwechsel.

---

## Projektstruktur

```
party-pi/
├── webconsole/
│   ├── app.py              # Flask-Backend (Spotify, Bluetooth, Volume)
│   ├── audio.py            # Server-seitiger FFT-Bridge (nicht aktiv)
│   ├── tv.html             # TV-Visualizer
│   ├── index.html          # Web-Interface
│   ├── config.example.py   # Konfigurationsvorlage
│   └── config.py           # Deine Konfiguration (gitignored!)
├── setup.sh                # Einrichtungsskript (veraltet, siehe README)
├── .gitignore
└── README.md
```

---

## Architektur

```
Spotify App
    │ Spotify Connect
    ▼
raspotify (librespot)
    │ ALSA / BlueALSA
    ▼
Bluetooth-Lautsprecher
    │ Ton im Raum
    ▼
Mikrofon im Browser
    │ Web Audio API (getUserMedia + AnalyserNode)
    ▼
TV-Visualizer Canvas (tv.html)
```

Lautstärke wird direkt per `bluealsa-cli` auf den Bluetooth-PCM gesetzt (0–127 → 0–100%).
