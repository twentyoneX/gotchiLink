"""
pwnagotchi_custom_ui.py

A modern, gotchiLink-style web dashboard for Pwnagotchi.
Served at http://pwnagotchi.local:8080/plugins/pwnagotchi_custom_ui/

Install:
    Copy this file to /etc/pwnagotchi/plugins/

Enable in /etc/pwnagotchi/config.toml:
    main.plugins.pwnagotchi_custom_ui.enabled = true

Author:  you
Version: 1.1.7
License: GPL-3.0
"""

import json
import logging
import os
import threading
import time
import re

import pwnagotchi.plugins as plugins


class PwnagotchiCustomUI(plugins.Plugin):
    __author__      = 'you'
    __version__     = '1.1.7'
    __license__     = 'GPL-3.0'
    __description__ = 'Modern gotchiLink web dashboard for Pwnagotchi'
    __name__        = 'pwnagotchi_custom_ui'
    __help__        = 'Serves a clean mobile-friendly UI at /plugins/pwnagotchi_custom_ui/'
    __dependencies__ = {}
    __defaults__    = {'enabled': False}

    # ------------------------------------------------------------------
    def __init__(self):
        self._state = {
            'name':               'pwnagotchi',
            'face':               '(- _ -)',
            'mood':               'IDLE',
            'message':            '',
            'channel':            0,
            'aps':                0,
            'mode':               'AUTO',
            'handshakes':         0,
            'session_handshakes': [],
            'pwnd':               0,
            'temp':               0,
            'cpu':                0,
            'mem':                0,
            'uptime':             '0s',
            'pwnagotchi_version': '?',
            'plugin_version':     self.__version__,
            'board':              '?',
            'enabled_plugins':    0,
        }
        self._stop_event = threading.Event()
        self.handshake_dir = '/root/handshakes'
        self._last_cpu = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_loaded(self):
        logging.info('[gotchiLink] loaded — http://pwnagotchi.local:8080/plugins/pwnagotchi_custom_ui/')
        self._stop_event.clear()
        t = threading.Thread(target=self._stats_loop, daemon=True)
        t.start()

    def on_ready(self, agent):
        try:
            self._state['name'] = agent.config()['main']['name']
        except Exception:
            pass

        try:
            self.handshake_dir = agent.config().get('bettercap', {}).get('handshakes', '/root/handshakes')
        except Exception:
            pass

    def on_unload(self, ui):
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Background sys-stats thread — Native Linux checks
    # ------------------------------------------------------------------

    def _stats_loop(self):
        while not self._stop_event.is_set():
            self._refresh_sys_stats()
            self._update_static_info()
            self._stop_event.wait(3)

    def _update_static_info(self):
        # Board update
        if self._state['board'] in ('?', 'Raspberry Pi'):
            try:
                with open('/proc/device-tree/model') as f:
                    self._state['board'] = f.read().replace('\x00', '').strip()
            except Exception:
                self._state['board'] = 'Raspberry Pi'

        # Version update
        if self._state['pwnagotchi_version'] == '?':
            try:
                import pwnagotchi
                if hasattr(pwnagotchi, '__version__'):
                    self._state['pwnagotchi_version'] = pwnagotchi.__version__
            except Exception:
                pass
            
            if self._state['pwnagotchi_version'] == '?':
                try:
                    with open('/etc/pwnagotchi/version', 'r') as f:
                        self._state['pwnagotchi_version'] = f.read().strip()
                except Exception:
                    pass

        # Plugin count
        try:
            self._state['enabled_plugins'] = len([p for p in plugins.loaded.values() if p])
        except Exception:
            pass
            
        # Initial PWND count fallback (before UI updates catch it)
        if self._state['pwnd'] == 0:
            try:
                d = self._get_hs_dir()
                if os.path.isdir(d):
                    files = [f for f in os.listdir(d) if f.endswith('.pcap') or f.endswith('.pcapng')]
                    self._state['pwnd'] = len(files)
            except Exception:
                pass

    def _refresh_sys_stats(self):
        # Native CPU check
        try:
            with open('/proc/stat', 'r') as f:
                lines = f.readlines()
            for line in lines:
                if line.startswith('cpu '):
                    parts = [float(i) for i in line.split()[1:]]
                    idle = parts[3] + parts[4]  # idle + iowait
                    total = sum(parts)
                    if not self._last_cpu:
                        self._last_cpu = (idle, total)
                    else:
                        idle_delta = idle - self._last_cpu[0]
                        total_delta = total - self._last_cpu[1]
                        self._last_cpu = (idle, total)
                        if total_delta > 0:
                            self._state['cpu'] = round(100.0 * (1.0 - idle_delta / total_delta))
                    break
        except Exception:
            pass
            
        # Native RAM check
        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
            mem_total, mem_avail = 0, 0
            for line in lines:
                if line.startswith('MemTotal:'):
                    mem_total = int(line.split()[1])
                elif line.startswith('MemAvailable:'):
                    mem_avail = int(line.split()[1])
            if mem_total > 0:
                self._state['mem'] = round(100.0 * (1.0 - (mem_avail / mem_total)))
        except Exception:
            pass

        # Native Temp check
        try:
            with open('/sys/class/thermal/thermal_zone0/temp') as f:
                self._state['temp'] = round(int(f.read().strip()) / 1000)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # State hooks
    # ------------------------------------------------------------------

    def _get_ui_val(self, ui, key):
        try:
            if hasattr(ui, 'get'):
                v = ui.get(key)
                if v is not None: return v
            if hasattr(ui, '_elements') and key in ui._elements:
                v = ui._elements[key]
                if hasattr(v, 'value'): return v.value
                return str(v)
        except Exception:
            pass
        return None

    def on_ui_update(self, ui):
        try:
            face = self._get_ui_val(ui, 'face')
            if face: self._state['face'] = face
            
            mood = self._get_ui_val(ui, 'state')
            if mood: self._state['mood'] = mood
            
            msg = self._get_ui_val(ui, 'status')
            if msg is not None: self._state['message'] = msg
            
            ch = self._get_ui_val(ui, 'channel')
            if ch is not None: self._state['channel'] = ch
            
            aps = self._get_ui_val(ui, 'aps')
            if aps is not None: self._state['aps'] = aps
            
            up = self._get_ui_val(ui, 'uptime')
            if up: self._state['uptime'] = up
            
            mode = self._get_ui_val(ui, 'mode')
            if mode: self._state['mode'] = mode
            
            # Extract lifetime PWND count from the "0 (14)" format
            shakes = self._get_ui_val(ui, 'shakes')
            if shakes is not None:
                shakes_str = str(shakes)
                match = re.search(r'\((\d+)\)', shakes_str)
                if match:
                    self._state['pwnd'] = int(match.group(1))
                else:
                    match_fallback = re.search(r'(\d+)', shakes_str)
                    if match_fallback:
                        self._state['pwnd'] = int(match_fallback.group(1))
                    
        except Exception as e:
            logging.debug('[gotchiLink] on_ui_update error: %s', e)

    def on_handshake(self, agent, filename, access_point, client_station):
        try:
            entry = {
                'ssid':     access_point.get('hostname', 'Unknown'),
                'mac':      access_point.get('mac', '??:??:??:??:??:??'),
                'time':     time.strftime('%H:%M'),
                'date':     time.strftime('%d/%m/%Y'),
                'filename': os.path.basename(filename),
            }
            self._state['session_handshakes'].insert(0, entry)
            self._state['handshakes'] += 1
            self._state['pwnd'] += 1
        except Exception as e:
            logging.debug('[gotchiLink] on_handshake err: %s', e)

    # ------------------------------------------------------------------
    # Disk handshake listing
    # ------------------------------------------------------------------

    def _get_hs_dir(self):
        if os.path.isdir(self.handshake_dir):
            return self.handshake_dir
        if os.path.isdir('/home/pi/handshakes'):
            return '/home/pi/handshakes'
        return self.handshake_dir

    def _list_disk_handshakes(self):
        result = []
        try:
            d = self._get_hs_dir()
            if not os.path.isdir(d):
                return result
                
            files = [f for f in os.listdir(d) if f.endswith('.pcap') or f.endswith('.pcapng')]
            files.sort(key=lambda f: -os.path.getmtime(os.path.join(d, f)))
            
            for fname in files:
                fpath = os.path.join(d, fname)
                base  = fname.rsplit('.', 1)[0]
                parts = base.rsplit('_', 1)
                ssid  = parts[0] if len(parts) >= 1 else base
                mac   = parts[1].replace('-', ':') if len(parts) == 2 else '??'
                size_kb = round(os.path.getsize(fpath) / 1024, 1)
                mtime   = time.strftime('%d/%m/%Y %H:%M', time.localtime(os.path.getmtime(fpath)))
                
                result.append({
                    'ssid':     ssid,
                    'mac':      mac,
                    'filename': fname,
                    'size':     size_kb,
                    'mtime':    mtime,
                })
        except Exception as e:
            logging.error('[gotchiLink] list_disk_handshakes err: %s', e)
        return result

    # ------------------------------------------------------------------
    # HTTP webhook
    # ------------------------------------------------------------------

    def on_webhook(self, path, request):
        from flask import Response, jsonify, send_file

        p = ('/' + (path or '').lstrip('/')).rstrip('/')
        if p == '': p = '/'

        if p == '/':
            html = _DASHBOARD_HTML.replace('__INITIAL_STATE__', json.dumps(self._state))
            return Response(html, mimetype='text/html')

        if p == '/api/state':
            return jsonify(self._state)

        if p == '/api/handshakes':
            return jsonify(self._list_disk_handshakes())

        if p.startswith('/api/handshakes/download/'):
            fname = os.path.basename(p.split('/api/handshakes/download/', 1)[1])
            fpath = os.path.join(self._get_hs_dir(), fname)
            if os.path.isfile(fpath) and (fname.endswith('.pcap') or fname.endswith('.pcapng')):
                return send_file(fpath, as_attachment=True, download_name=fname, mimetype='application/octet-stream')
            return Response('Not found', status=404)

        if p == '/api/handshakes/delete':
            try:
                fname = request.args.get('file')
                if not fname:
                    return jsonify({'status': 'error', 'error': 'No file specified.'}), 400
                
                fname = os.path.basename(fname)
                fpath = os.path.join(self._get_hs_dir(), fname)
                
                if os.path.isfile(fpath) and (fname.endswith('.pcap') or fname.endswith('.pcapng')):
                    os.remove(fpath)
                    for ext in ('.22000', '.hccapx'):
                        companion = fpath.rsplit('.', 1)[0] + ext
                        if os.path.isfile(companion): 
                            os.remove(companion)
                    return jsonify({'status': 'ok', 'deleted': fname})
                return jsonify({'status': 'error', 'error': 'File not found on device'}), 404
            except Exception as e:
                return jsonify({'status': 'error', 'error': str(e)}), 500

        if p == '/api/restart':
            try:
                mode = request.args.get('mode', 'MANU').upper()
                import pwnagotchi
                pwnagotchi.restart(mode)
                return jsonify({'status': 'ok', 'mode': mode})
            except Exception as e:
                return jsonify({'status': 'error', 'error': str(e)}), 500

        return Response('Not found', status=404)


# ======================================================================
# Embedded dashboard — single-file, zero external deps
# ======================================================================

_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>gotchiLink</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg:     #f0f0f5;
  --card:   #ffffff;
  --text:   #1a1a1a;
  --muted:  #888888;
  --border: rgba(0,0,0,0.09);
  --blue:   #1a7fe8;
  --green:  #34a853;
  --orange: #e07b00;
  --red:    #d93025;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg:     #111111;
    --card:   #1c1c1e;
    --text:   #f2f2f7;
    --muted:  #8e8e93;
    --border: rgba(255,255,255,0.08);
  }
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg); color: var(--text);
  max-width: 520px; margin: 0 auto; padding-bottom: 80px;
}

/* top bar */
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; background: var(--card);
  border-bottom: 0.5px solid var(--border);
  position: sticky; top: 0; z-index: 20;
}
.topbar-title { font-size: 15px; font-weight: 600; }
.icon-btn {
  width: 36px; height: 36px; border-radius: 50%;
  background: var(--bg); border: 0.5px solid var(--border);
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; cursor: pointer; color: var(--text); user-select: none;
}
.icon-btn:active { opacity: .6; }

/* hostname row */
.hostname-row { 
  display: flex; align-items: center; justify-content: space-between; 
  padding: 14px 16px 4px; gap: 8px; 
}
.hostname { font-size: 22px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; }
.badge-container { display: flex; gap: 6px; align-items: center; flex-shrink: 0; }
.badge {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 20px;
}
.badge-green { background: #e8f5e9; color: #2e7d32; }
.badge-dot { width: 7px; height: 7px; border-radius: 50%; }
.badge-dot-green { background: var(--green); animation: pulse 2s infinite; }
.badge-pwnd { background: rgba(26, 127, 232, 0.15); color: var(--blue); }

hr.divider { border: none; border-top: 0.5px solid var(--border); margin: 10px 16px; }

/* card */
.card {
  background: var(--card); border-radius: 16px;
  margin: 0 12px 14px; border: 0.5px solid var(--border); overflow: hidden;
}

/* live view */
.live-label {
  display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600;
  color: var(--green); letter-spacing: .07em; padding: 12px 16px 4px;
}
.live-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--green); animation: pulse 2s infinite; }
.face-row { display: flex; align-items: center; gap: 20px; padding: 8px 16px 16px; }
.face-wrap { flex-shrink: 0; min-width: 120px; }
.face { font-family: monospace; font-size: 22px; font-weight: 700; white-space: nowrap; }
.face-msg {
  font-family: monospace; font-size: 13px; color: var(--muted);
  line-height: 1.5; padding-left: 8px; border-left: 2px solid var(--border);
}

/* session row */
.session-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 16px; border-top: 0.5px solid var(--border);
}
.session-label { font-size: 11px; font-weight: 600; letter-spacing: .07em; color: var(--muted); }
.session-count { font-size: 16px; font-weight: 700; color: var(--blue); }

/* stats grid */
.stats-grid { display: grid; grid-template-columns: repeat(3,1fr); border-top: 0.5px solid var(--border); }
.stat-cell { padding: 10px 14px; border-right: 0.5px solid var(--border); }
.stat-cell:nth-child(3n)  { border-right: none; }
.stat-cell:nth-child(n+4) { border-top: 0.5px solid var(--border); }
.stat-lbl { font-size: 10px; color: var(--muted); letter-spacing: .07em; margin-bottom: 3px; }
.stat-val { font-size: 20px; font-weight: 700; }
.stat-val.warn { color: var(--orange); }
.stat-val.hot  { color: var(--red); }

/* power row */
.power-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 16px 12px; border-top: 0.5px solid var(--border);
  font-size: 13px; color: var(--muted);
}

/* section header */
.section-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px 8px;
}
.section-title { font-size: 16px; font-weight: 700; }
.count-badge {
  background: #e3f0fb; color: #1a5ea8;
  font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: 20px;
}

/* info rows */
.info-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 11px 16px; border-bottom: 0.5px solid var(--border); font-size: 14px;
}
.info-row:last-child { border-bottom: none; }
.info-key { color: var(--muted); flex-shrink: 0; }
.info-val { font-weight: 500; text-align: right; max-width: 60%; word-break: break-all; }

/* handshake list */
.hs-list { padding: 0 12px 4px; }
.hs-card {
  background: var(--card); border-radius: 14px; margin-bottom: 8px;
  border: 0.5px solid var(--border); padding: 12px 14px;
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
}
.hs-info { flex: 1; min-width: 0; }
.hs-name { font-size: 15px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hs-mac  { font-size: 11px; color: var(--muted); font-family: monospace; margin-top: 2px; }
.hs-meta { font-size: 11px; color: var(--muted); margin-top: 2px; }
.hs-actions { display: flex; gap: 6px; flex-shrink: 0; }
.hs-btn {
  width: 34px; height: 34px; border-radius: 9px; border: 0.5px solid var(--border);
  background: var(--bg); display: flex; align-items: center; justify-content: center;
  font-size: 16px; cursor: pointer; color: var(--text); text-decoration: none;
}
.hs-btn:active { opacity: .6; }
.hs-btn.del { color: var(--red); }
.hs-empty   { padding: 40px 0; text-align: center; color: var(--muted); font-size: 14px; }
.hs-loading { padding: 30px 0; text-align: center; color: var(--muted); font-size: 13px; }

/* modals */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.5);
  display: none; align-items: flex-end; z-index: 100;
}
.modal-overlay.open { display: flex; }
.modal, .confirm-modal {
  background: var(--card); border-radius: 20px 20px 0 0;
  padding: 20px 16px 36px; width: 100%;
}
.modal-face { text-align: center; font-family: monospace; font-size: 26px; margin-bottom: 8px; }
.modal h2, .confirm-modal h2 { font-size: 18px; font-weight: 700; text-align: center; margin-bottom: 6px; }
.modal p, .confirm-modal p   { font-size: 13px; color: var(--muted); text-align: center; margin-bottom: 20px; line-height: 1.5; }
.btn-primary {
  display: block; width: 100%; padding: 15px; border-radius: 14px;
  background: var(--blue); color: #fff; font-size: 16px; font-weight: 600;
  border: none; cursor: pointer; margin-bottom: 10px;
}
.btn-primary:active { opacity: .85; }
.btn-danger {
  display: block; width: 100%; padding: 15px; border-radius: 14px;
  background: var(--red); color: #fff; font-size: 16px; font-weight: 600;
  border: none; cursor: pointer; margin-bottom: 10px;
}
.btn-danger:active { opacity: .85; }
.btn-row { display: flex; gap: 10px; }
.btn-secondary {
  flex: 1; padding: 13px; border-radius: 14px;
  background: var(--bg); border: 0.5px solid var(--border);
  font-size: 14px; font-weight: 500; cursor: pointer; color: var(--text);
}
.btn-secondary:active { opacity: .75; }

/* tab bar */
.tab-bar {
  position: fixed; bottom: 0; left: 50%; transform: translateX(-50%);
  width: 100%; max-width: 520px;
  display: flex; justify-content: center; gap: 64px;
  padding: 10px 20px 18px;
  background: var(--card); border-top: 0.5px solid var(--border);
}
.tab { display: flex; flex-direction: column; align-items: center; gap: 3px; cursor: pointer; user-select: none; }
.tab-icon  { font-size: 20px; }
.tab-label { font-size: 10px; font-weight: 500; color: var(--muted); }
.tab.active .tab-label { color: var(--blue); }

/* animations */
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.35} }
@keyframes spin   { to { transform: rotate(360deg); } }
.spinning { animation: spin .7s linear infinite; display: inline-block; }
</style>
</head>
<body>

<!-- Top bar -->
<div class="topbar">
  <div class="icon-btn" id="refresh-btn" title="Refresh">↻</div>
  <span class="topbar-title">gotchiLink</span>
  <div class="icon-btn" id="restart-open-btn" title="Restart">⏻</div>
</div>

<!-- Hostname & Badges -->
<div class="hostname-row">
  <span class="hostname" id="hostname">pwnagotchi</span>
  <div class="badge-container">
    <span class="badge badge-green"><span class="badge-dot badge-dot-green"></span>Online</span>
    <span class="badge badge-pwnd">PWND&nbsp;<span id="pwnd-count">0</span></span>
  </div>
</div>
<hr class="divider">

<!-- ====== DASHBOARD ====== -->
<div id="dashboard-section">

  <!-- Live card -->
  <div class="card">
    <div class="live-label"><span class="live-dot"></span>LIVE VIEW</div>
    <div class="face-row">
      <div class="face-wrap">
        <div class="face" id="face">(- _ -)</div>
      </div>
      <div class="face-msg" id="message"></div>
    </div>
    <div class="session-row">
      <div class="session-label">🔑 SESSION HANDSHAKES</div>
      <div class="session-count" id="session-count">0</div>
    </div>
    <div class="stats-grid">
      <div class="stat-cell">
        <div class="stat-lbl">MODE</div><div class="stat-val" id="mode">—</div>
      </div>
      <div class="stat-cell">
        <div class="stat-lbl">📡 CH</div><div class="stat-val" id="channel">—</div>
      </div>
      <div class="stat-cell">
        <div class="stat-lbl">🌐 APS</div><div class="stat-val" id="aps">—</div>
      </div>
      
      <!-- Reordered Stats: RAM, CPU, TEMP -->
      <div class="stat-cell">
        <div class="stat-lbl">💾 RAM</div><div class="stat-val" id="mem">—%</div>
      </div>
      <div class="stat-cell">
        <div class="stat-lbl">CPU</div><div class="stat-val" id="cpu">—%</div>
      </div>
      <div class="stat-cell">
        <div class="stat-lbl">🌡 TEMP</div><div class="stat-val" id="temp">—°C</div>
      </div>
    </div>
    <div class="power-row"><span>⬌ Power</span><span>USB</span></div>
  </div>

  <!-- General info -->
  <div class="section-header"><span class="section-title">General informations</span></div>
  <div class="card" style="margin-bottom:14px;">
    <div class="info-row">
      <span class="info-key">🏷 Name</span>
      <span class="info-val" id="info-name">—</span>
    </div>
    <div class="info-row">
      <span class="info-key">⬡ Pwnagotchi version</span>
      <span class="info-val" id="info-pwn-version">—</span>
    </div>
    <div class="info-row">
      <span class="info-key">🔌 Plugin version</span>
      <span class="info-val" id="info-plugin-version">—</span>
    </div>
    <div class="info-row">
      <span class="info-key">🧩 Enabled plugins</span>
      <span class="info-val" id="info-plugins">—</span>
    </div>
    <div class="info-row">
      <span class="info-key">⏱ Uptime</span>
      <span class="info-val" id="info-uptime">—</span>
    </div>
  </div>

  <!-- System info -->
  <div class="section-header"><span class="section-title">System informations</span></div>
  <div class="card" style="margin-bottom:14px;">
    <div class="info-row">
      <span class="info-key">🖥 Board</span>
      <span class="info-val" id="info-board">—</span>
    </div>
    <div class="info-row">
      <span class="info-key">⚡ Power supply</span>
      <span class="info-val">USB</span>
    </div>
  </div>

</div>

<!-- ====== HANDSHAKES ====== -->
<div id="handshakes-section" style="display:none;">
  <div class="section-header">
    <span class="section-title">Handshakes</span>
    <span class="count-badge" id="hs-badge">0 total</span>
  </div>
  <div class="hs-list" id="hs-list">
    <div class="hs-loading">Loading handshakes…</div>
  </div>
</div>

<!-- Restart modal -->
<div class="modal-overlay" id="restart-modal">
  <div class="modal">
    <div class="modal-face">( ¬_¬ )</div>
    <h2>Restart your Pwnagotchi?</h2>
    <p id="modal-desc">Loading…</p>
    <button class="btn-primary" id="btn-switch-mode">…</button>
    <div class="btn-row">
      <button class="btn-secondary" id="btn-same-mode">…</button>
      <button class="btn-secondary" id="modal-cancel-btn">Cancel</button>
    </div>
  </div>
</div>

<!-- Delete confirm modal -->
<div class="modal-overlay" id="delete-modal">
  <div class="confirm-modal">
    <h2>Delete handshake?</h2>
    <p id="delete-desc">This will permanently remove the .pcap file.</p>
    <button class="btn-danger" id="btn-confirm-delete">Delete</button>
    <div class="btn-row">
      <button class="btn-secondary" id="delete-cancel-btn">Cancel</button>
    </div>
  </div>
</div>

<!-- Tab bar -->
<div class="tab-bar">
  <div class="tab active" id="tab-dashboard" onclick="showTab('dashboard')">
    <div class="tab-icon">💻</div>
    <div class="tab-label">Dashboard</div>
  </div>
  <div class="tab" id="tab-handshakes" onclick="showTab('handshakes')">
    <div class="tab-icon">🌐</div>
    <div class="tab-label">Handshakes</div>
  </div>
</div>

<script>
const POLL_INTERVAL = 5000;
const BASE = '/plugins/pwnagotchi_custom_ui';
let state = __INITIAL_STATE__;
let polling;
let pendingDeleteFile = null;
let allHandshakes = [];

// ── helpers ──────────────────────────────────────────────────────────
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}
function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── render dashboard ─────────────────────────────────────────────────
function render(s) {
  setText('hostname',  s.name || 'pwnagotchi');
  setText('face',      s.face || '(- _ -)');
  
  setText('message',   s.message || '');
  setText('channel',   s.channel !== undefined && s.channel !== null ? s.channel : '—');
  setText('aps',       s.aps     !== undefined && s.aps     !== null ? s.aps     : '—');
  setText('mode',      s.mode    || '—');
  setText('session-count', (s.session_handshakes || []).length);
  setText('pwnd-count', s.pwnd !== undefined ? s.pwnd : 0);

  // Formatting numerical data
  const tempEl = document.getElementById('temp');
  const t = (s.temp !== undefined && s.temp !== null && s.temp !== '') ? String(s.temp) : null;
  
  if (t !== null) {
    const tNum = parseFloat(t);
    tempEl.textContent = tNum + '°C';
    tempEl.className = 'stat-val ' + (tNum >= 70 ? 'hot' : tNum >= 55 ? 'warn' : '');
  } else {
    tempEl.textContent = '—°C';
    tempEl.className = 'stat-val';
  }

  const cpu = (s.cpu !== undefined && s.cpu !== null && String(s.cpu).trim() !== '') ? String(s.cpu) + '%' : '—%';
  const mem = (s.mem !== undefined && s.mem !== null && String(s.mem).trim() !== '') ? String(s.mem) + '%' : '—%';
  setText('cpu', cpu);
  setText('mem', mem);

  // general info
  setText('info-name',           s.name                || '—');
  setText('info-pwn-version',    s.pwnagotchi_version  || '—');
  setText('info-plugin-version', s.plugin_version      || '—');
  setText('info-plugins',        s.enabled_plugins !== undefined && s.enabled_plugins !== null ? s.enabled_plugins : '—');
  setText('info-uptime',         s.uptime              || '—');

  // system info
  setText('info-board', s.board || '—');
}

// ── handshakes rendering ──────────────────────────────────────────────
function renderHandshakes(list) {
  allHandshakes = list;
  const el    = document.getElementById('hs-list');
  const badge = document.getElementById('hs-badge');
  badge.textContent = list.length + ' total';

  if (!list.length) {
    el.innerHTML = '<div class="hs-empty">No handshakes captured yet.</div>';
    return;
  }

  el.innerHTML = list.map((h, i) => `
    <div class="hs-card" id="hs-card-${i}">
      <div class="hs-info">
        <div class="hs-name">${esc(h.ssid)}</div>
        <div class="hs-mac">${esc(h.mac)}</div>
        <div class="hs-meta">${esc(h.mtime)} &nbsp;·&nbsp; ${esc(h.size)} KB</div>
      </div>
      <div class="hs-actions">
        <a class="hs-btn"
           href="${BASE}/api/handshakes/download/${esc(h.filename)}"
           download="${esc(h.filename)}"
           title="Download .pcap">⬇</a>
        <div class="hs-btn del" onclick="confirmDelete(${i})" title="Delete">🗑</div>
      </div>
    </div>`).join('');
}

function loadHandshakes() {
  document.getElementById('hs-list').innerHTML = '<div class="hs-loading">Loading…</div>';
  fetch(BASE + '/api/handshakes')
    .then(r => r.json())
    .then(list => renderHandshakes(list))
    .catch(() => {
      document.getElementById('hs-list').innerHTML =
        '<div class="hs-empty">Could not load handshakes.</div>';
    });
}

// ── delete flow ───────────────────────────────────────────────────────
function confirmDelete(idx) {
  const h = allHandshakes[idx];
  if (!h) return;
  pendingDeleteFile = h.filename;
  document.getElementById('delete-desc').textContent =
    'Delete "' + h.ssid + '" (' + h.filename + ')? This cannot be undone.';
  document.getElementById('delete-modal').classList.add('open');
}

function doDelete() {
  if (!pendingDeleteFile) return;
  const fname = pendingDeleteFile;
  pendingDeleteFile = null;
  closeDeleteModal();
  
  fetch(BASE + '/api/handshakes/delete?file=' + encodeURIComponent(fname))
  .then(async r => {
    const isJson = r.headers.get('content-type')?.includes('application/json');
    if (isJson) {
      const d = await r.json();
      if (d.status === 'ok') loadHandshakes();
      else alert('Delete failed: ' + (d.error || 'Unknown error'));
    } else {
      const text = await r.text();
      alert('Delete response error: Server blocked request.\n' + text.substring(0, 100));
    }
  })
  .catch(err => alert('Delete request network failed: ' + err));
}

function closeDeleteModal() {
  document.getElementById('delete-modal').classList.remove('open');
  pendingDeleteFile = null;
}

// ── polling ───────────────────────────────────────────────────────────
function refresh() {
  const btn = document.getElementById('refresh-btn');
  btn.innerHTML = '<span class="spinning">↻</span>';
  fetch(BASE + '/api/state')
    .then(r => r.json())
    .then(s => { state = s; render(s); })
    .catch(e => console.warn('[custom_ui] poll failed:', e))
    .finally(() => { btn.innerHTML = '↻'; });
}
function startPolling() { polling = setInterval(refresh, POLL_INTERVAL); }
function stopPolling()  { clearInterval(polling); }

// ── tabs ──────────────────────────────────────────────────────────────
function showTab(t) {
  document.getElementById('dashboard-section').style.display  = t === 'dashboard'  ? 'block' : 'none';
  document.getElementById('handshakes-section').style.display = t === 'handshakes' ? 'block' : 'none';
  document.getElementById('tab-dashboard').classList.toggle('active',  t === 'dashboard');
  document.getElementById('tab-handshakes').classList.toggle('active', t === 'handshakes');
  if (t === 'handshakes') loadHandshakes();
}

// ── restart modal ─────────────────────────────────────────────────────
function openModal() {
  const cur   = (state.mode || 'AUTO').toUpperCase();
  const other = cur === 'AUTO' ? 'MANU' : 'AUTO';
  document.getElementById('modal-desc').textContent =
    cur === 'AUTO'
      ? 'Currently in AUTO mode. Switch to MANU to stop attacks.'
      : 'Currently in MANU mode. Switch to AUTO to resume scanning.';
  const btnSwitch = document.getElementById('btn-switch-mode');
  btnSwitch.textContent = 'Restart in ' + other + ' mode';
  btnSwitch.onclick = () => restartDevice(other);
  const btnSame = document.getElementById('btn-same-mode');
  btnSame.textContent = 'Restart ' + cur;
  btnSame.onclick = () => restartDevice(cur);
  document.getElementById('restart-modal').classList.add('open');
}
function closeModal() {
  document.getElementById('restart-modal').classList.remove('open');
}
function restartDevice(mode) {
  fetch(BASE + '/api/restart?mode=' + encodeURIComponent(mode))
  .catch(e => console.warn('[custom_ui] restart failed:', e));
  closeModal();
}

// ── events ────────────────────────────────────────────────────────────
document.getElementById('refresh-btn').addEventListener('click', refresh);
document.getElementById('restart-open-btn').addEventListener('click', openModal);
document.getElementById('modal-cancel-btn').addEventListener('click', closeModal);
document.getElementById('restart-modal').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});
document.getElementById('btn-confirm-delete').addEventListener('click', doDelete);
document.getElementById('delete-cancel-btn').addEventListener('click', closeDeleteModal);
document.getElementById('delete-modal').addEventListener('click', function(e) {
  if (e.target === this) closeDeleteModal();
});

// ── boot ──────────────────────────────────────────────────────────────
render(state);
startPolling();
</script>
</body>
</html>
"""
