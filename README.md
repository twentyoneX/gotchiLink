# gotchiLink

A modern, mobile-friendly web dashboard plugin for [Pwnagotchi](https://pwnagotchi.ai/) — inspired by the PwnagotchLink iOS app.

Replaces the default `pwnagotchi.local:8080` look with a clean dashboard you can use from any browser, on any device. No app required.

> ⚠️ The original web UI at `pwnagotchi.local:8080` is **not affected**. Both run side by side.

---

## Features

- **Live face** — real-time face expression, mood state, and status message
- **Stats grid** — Mode / Channel / APs / RAM / CPU / Temperature
- **PWND counter** — lifetime handshake count badge in the header
- **Handshakes tab** — full list of captured `.pcap` files read from disk, with:
  - ⬇ **Download** individual `.pcap` files directly to your device
  - 🗑 **Delete** handshakes with a confirmation modal
- **Restart modal** — restart in MANU or AUTO mode from the UI
- **General & System info** — name, Pwnagotchi version, plugin version, board model, enabled plugins, uptime
- **Dark mode** — follows system preference automatically
- **Zero dependencies** — no `psutil`, no extra packages, uses native `/proc` reads
- Works on **mobile, tablet, and desktop** browsers

---

## Screenshots

<table>
  <tr>
    <td><img width="467" height="800" alt="image" src="https://github.com/user-attachments/assets/a6708636-07e5-47ae-9d0b-edcb08361af3" /></td>
    <td><img width="467" height="800" alt="image" src="https://github.com/user-attachments/assets/c941f5f4-f705-4740-92ef-28a2e44fffb9" /></td>
  </tr>
</table>





---

## Requirements

| Requirement | Version |
|---|---|
| Pwnagotchi | 2.8.x / 2.9.x |
| Python | 3.x |
| Flask | already bundled with Pwnagotchi |

No extra pip packages needed.

---

## Install

### Option A — copy from your computer

```bash
scp pwnagotchi_custom_ui.py pi@10.42.0.200:/home/pi/
```

Then on the Pi, move it to the custom plugins directory:

```bash
ssh pi@10.42.0.200
sudo mv /home/pi/pwnagotchi_custom_ui.py /usr/local/share/pwnagotchi/custom-plugins/
sudo chmod 644 /usr/local/share/pwnagotchi/custom-plugins/pwnagotchi_custom_ui.py
```

### Option B — directly on the device

```bash
ssh pi@10.42.0.200
sudo wget -O /usr/local/share/pwnagotchi/custom-plugins/pwnagotchi_custom_ui.py \
  https://raw.githubusercontent.com/twentyoneX/gotchiLink/main/pwnagotchi_custom_ui.py
```

---

## Enable

Add to `/etc/pwnagotchi/config.toml`:

```toml
[main.plugins.pwnagotchi_custom_ui]
enabled = true
```

> ⚠️ Make sure it is a proper TOML section `[main.plugins.pwnagotchi_custom_ui]` with `enabled = true` on the next line — not a flat one-liner.

Then restart:

```bash
sudo systemctl restart pwnagotchi
```

Check the logs to confirm it loaded:

```bash
sudo tail -f /etc/pwnagotchi/log/pwnagotchi.log | grep gotchiLink
```

You should see:
```
[gotchiLink] loaded — http://pwnagotchi.local:8080/plugins/pwnagotchi_custom_ui/
```

---

## Usage

Open in any browser:

```
http://pwnagotchi.local:8080/plugins/pwnagotchi_custom_ui/
```

Or by IP (useful when connecting over USB):

```
http://10.42.0.200:8080/plugins/pwnagotchi_custom_ui/
```

> **Tip:** On USB tether, your Pwnagotchi's IP may not be `10.42.0.2` — check with `arp -n` or `ip neigh show` to find the actual IP.

---

## API Endpoints

The plugin exposes a small REST API you can query directly:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/plugins/pwnagotchi_custom_ui/api/state` | Current device state as JSON |
| `GET` | `/plugins/pwnagotchi_custom_ui/api/handshakes` | List of `.pcap` files on disk |
| `GET` | `/plugins/pwnagotchi_custom_ui/api/handshakes/download/<file>` | Download a specific `.pcap` |
| `GET` | `/plugins/pwnagotchi_custom_ui/api/handshakes/delete?file=<file>` | Delete a `.pcap` and companion files |
| `GET` | `/plugins/pwnagotchi_custom_ui/api/restart?mode=MANU\|AUTO` | Restart in the specified mode |

Example state response:

```json
{
  "name": "pwnagotchi",
  "face": "(^- -^)",
  "mood": "HAPPY",
  "message": "Kicked 4 stations Made 5 new friends Got 0 handshakes",
  "channel": 6,
  "aps": 12,
  "mode": "AUTO",
  "handshakes": 3,
  "pwnd": 47,
  "temp": 53,
  "cpu": 7,
  "mem": 50,
  "uptime": "1:23:45",
  "pwnagotchi_version": "2.9.5.4",
  "plugin_version": "1.1.7",
  "board": "Raspberry Pi Zero 2 W Rev 1.0",
  "enabled_plugins": 8
}
```

---

## Connecting over USB on Linux

If your PC assigns a different IP than expected:

```bash
# Find the Pwnagotchi's actual IP
ip neigh show dev enx<your_usb_interface>

# Or scan the subnet
arp -n | grep enx<your_usb_interface>
```

The Pwnagotchi typically lands somewhere in the `10.42.0.x` range.

---

## Disable / Uninstall

To disable without removing the file:

```toml
[main.plugins.pwnagotchi_custom_ui]
enabled = false
```

To fully remove:

```bash
sudo rm /usr/local/share/pwnagotchi/custom-plugins/pwnagotchi_custom_ui.py
sudo systemctl restart pwnagotchi
```

---

## Troubleshooting

**Plugin not loading / 404 at the URL**
- Make sure the file is in `/usr/local/share/pwnagotchi/custom-plugins/` — check with `ls` that directory
- Verify the config.toml entry is a proper `[section]` block, not a flat key
- Check logs: `sudo tail -50 /etc/pwnagotchi/log/pwnagotchi.log`

**Handshakes tab empty**
- Confirm your handshakes are in `/home/pi/handshakes/` or `/root/handshakes/`
- The plugin auto-detects both paths

**Temperature / CPU / RAM showing `—`**
- These populate after the first epoch (about 30–60 seconds after boot)

**Can't SSH / connect**
- Your Pwnagotchi's IP on USB may not be `10.42.0.2` — run `ip neigh show` on your PC to find it

---

## Contributing

Pull requests are welcome. Ideas for future features:

- GPS map overlay for handshakes
- WPA-sec upload integration
- Push notifications on new handshake
- Search / filter in handshakes list

---

## License

GPL-3.0 — same license as Pwnagotchi itself.

---

## Credits

Inspired by the [PwnagotchLink](https://github.com/G4vr0ch3/PwnagotchLink) iOS app by G4vr0ch3.
