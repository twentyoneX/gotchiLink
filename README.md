# gotchiLink 💻🌐

**gotchiLink** is a modern, high-performance web dashboard for Pwnagotchi. It provides a clean, mobile-friendly interface to monitor your device and manage handshakes in real-time.

Designed specifically for the community, it features a sleek dark theme and native system monitoring for maximum accuracy.

---

## ✨ Features

*   **Modern Dark UI**: A clean, "App-like" experience for mobile and desktop.
*   **Hardened System Stats**: Uses native Linux system calls to provide accurate **RAM**, **CPU**, and **Temp** data.
*   **Handshake Manager**: View, download, or delete captured handshakes directly from the dashboard.
*   **Dynamic PWND Badge**: Displays your lifetime total handshake count.
*   **Jayofelony Ready**: Optimized for the latest Jayofelony firmware releases.

---

## 🚀 Installation Guide

### 1. SSH into your Pwnagotchi
Connect to your device via terminal:
```bash
ssh pi@10.0.0.2

2. Create/Navigate to the Custom Plugins Folder

On Jayofelony images, custom plugins should live in this specific folder. Run this command to ensure it exists and move into it:
code Bash

sudo mkdir -p /usr/local/share/pwnagotchi/custom-plugins/
cd /usr/local/share/pwnagotchi/custom-plugins/

3. Download the Plugin

Download the dashboard file directly from this repository:
code Bash

sudo wget https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/gotchiLink/main/pwnagotchi_custom_ui.py

4. Configure your Pwnagotchi

Now you need to enable the plugin and tell Pwnagotchi where to look for it. Open your configuration file:
code Bash

sudo nano /etc/pwnagotchi/config.toml

Inside the nano editor:

    Check that the custom_plugins path is correct. Find the [main] section and ensure this line is there:
    code Toml

    main.custom_plugins = "/usr/local/share/pwnagotchi/custom-plugins/"

    Scroll to the very bottom of the file and add the following block:
    code Toml

    [main.plugins.pwnagotchi_custom_ui]
    enabled = true

    Save your changes: Press CTRL + O, then press Enter.

    Exit the editor: Press CTRL + X.

5. Restart the Software

Restart the pwnagotchi service to apply all your changes:
code Bash

sudo systemctl restart pwnagotchi

🔗 How to Access the Dashboard

Wait about 60 seconds for the device to boot, then open your browser and go to:

👉 http://pwnagotchi.local:8080/plugins/pwnagotchi_custom_ui/
💡 Pro-Tip: Companion Plugins

For the best experience, we recommend using gotchiLink alongside these plugins:

    display_password: Shows cracked passwords on your e-ink screen.

    cracked: Provides a web list of all your cracked network keys.

🛠 Troubleshooting

If the dashboard doesn't appear in your Plugins list:

    Ensure the filename in the folder is exactly pwnagotchi_custom_ui.py.

    Run ls -la /usr/local/share/pwnagotchi/custom-plugins/ to verify the file is there.

    Check the system logs for errors: sudo tail -f /var/log/pwnagotchi.log

⚖️ License

This project is licensed under the GPL-3.0 License.
