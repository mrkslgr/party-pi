#!/bin/bash
set -euo pipefail

DEVICE_NAME="${1:-Party Pi}"

echo "==> Party Pi Setup: '$DEVICE_NAME'"

# --- 1. System update ---
echo "==> System update..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# --- 2. PipeWire + Bluetooth ---
echo "==> PipeWire Bluetooth-Support installieren..."
sudo apt-get install -y -qq \
    pipewire \
    pipewire-audio \
    wireplumber \
    libspa-0.2-bluetooth \
    bluez \
    bluez-tools

# PipeWire für den aktuellen User aktivieren
systemctl --user enable pipewire pipewire-pulse wireplumber 2>/dev/null || true
systemctl --user start  pipewire pipewire-pulse wireplumber 2>/dev/null || true

# --- 3. raspotify installieren ---
echo "==> raspotify installieren..."
curl -sL https://dtcooper.github.io/raspotify/install.sh | sh

# --- 4. raspotify konfigurieren ---
echo "==> raspotify konfigurieren..."
sudo tee /etc/raspotify/conf > /dev/null <<EOF
# Party Pi — raspotify Konfiguration
LIBRESPOT_NAME="$DEVICE_NAME"
LIBRESPOT_BITRATE="320"

# Über PipeWire ausgeben
LIBRESPOT_BACKEND="pipe"
EOF

sudo systemctl enable raspotify
sudo systemctl restart raspotify

# --- 5. WirePlumber: Bluetooth-Sink automatisch als Default ---
echo "==> WirePlumber-Regel für Bluetooth-Default setzen..."
mkdir -p ~/.config/wireplumber/main.lua.d
cat > ~/.config/wireplumber/main.lua.d/51-bluetooth-default.lua <<'EOF'
-- Setzt einen neu verbundenen Bluetooth-Sink automatisch als Standard-Ausgang
rule = {
  matches = {
    {
      { "node.name", "matches", "bluez_output.*" },
    },
  },
  apply_properties = {
    ["node.nick"] = "Party Speaker",
    ["priority.session"] = 2000,
  },
}

table.insert(alsa_monitor.rules, rule)
EOF

systemctl --user restart wireplumber 2>/dev/null || true

# --- 6. Bluetooth Auto-Connect aktivieren ---
echo "==> Bluetooth Auto-Connect konfigurieren..."
sudo sed -i 's/#AutoConnect = false/AutoConnect = true/' /etc/bluetooth/main.conf 2>/dev/null || true
sudo systemctl restart bluetooth

echo ""
echo "==> Fertig! Nächster Schritt: Bluetooth-Lautsprecher koppeln."
echo ""
echo "    bluetoothctl"
echo "    > power on"
echo "    > agent on"
echo "    > scan on"
echo "    # Warte bis dein Gerät erscheint, dann:"
echo "    > pair XX:XX:XX:XX:XX:XX"
echo "    > trust XX:XX:XX:XX:XX:XX"
echo "    > connect XX:XX:XX:XX:XX:XX"
echo "    > exit"
echo ""
echo "    Danach: Spotify öffnen -> Gerät wählen -> '$DEVICE_NAME'"
