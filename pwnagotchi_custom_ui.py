"""
pwnagotchi_custom_ui.py - Version 1.3.0
FULL TERMINAL DASHBOARD (Unified Info Widget + Version Detection Fix)
"""
import json
import logging
import os
import threading
import time
import re
import pwnagotchi.plugins as plugins

class PwnagotchiCustomUI(plugins.Plugin):
    __author__      = 'mrx'
    __version__     = '1.3.0'
    __name__        = 'pwnagotchi_custom_ui'

    def __init__(self):
        self._state = {
            'name':               'pwnagotchi',
            'face':               '(- _ -)',
            'message':            'INITIALIZING...',
            'channel':            '-',
            'aps':                '0',
            'mode':               'AUTO',
            'handshakes':         0,
            'session_handshakes': [],
            'pwnd':               0,
            'temp':               0,
            'cpu':                0,
            'mem':                0,
            'uptime':             '0s',
            'pwnagotchi_version': '?',
            'plugin_version':     '1.3.0',
            'board':              '?',
            'enabled_plugins':    0,
        }
        self._stop_event = threading.Event()
        self.handshake_dir = '/root/handshakes'
        self._last_cpu = None

    def on_loaded(self):
        self._stop_event.clear()
        threading.Thread(target=self._stats_loop, daemon=True).start()

    def on_ready(self, agent):
        try:
            self._state['name'] = agent.config()['main']['name']
            self.handshake_dir = agent.config().get('bettercap', {}).get('handshakes', '/root/handshakes')
            
            # Direct version grab on ready
            import pwnagotchi
            self._state['pwnagotchi_version'] = getattr(pwnagotchi, '__version__', getattr(pwnagotchi, 'version', '?'))
        except: pass

    def _stats_loop(self):
        while not self._stop_event.is_set():
            self._refresh_sys_stats()
            # Robust version/board fallback
            if self._state['board'] == '?':
                try:
                    with open('/proc/device-tree/model') as f: self._state['board'] = f.read().replace('\x00', '').strip()
                except: self._state['board'] = 'Raspberry Pi'
            
            if self._state['pwnagotchi_version'] == '?':
                try:
                    with open('/etc/pwnagotchi/version') as f: self._state['pwnagotchi_version'] = f.read().strip()
                except: pass

            self._state['enabled_plugins'] = len([p for p in plugins.loaded.values() if p])
            self._stop_event.wait(3)

    def _refresh_sys_stats(self):
        try:
            with open('/proc/stat', 'r') as f:
                for line in f:
                    if line.startswith('cpu '):
                        p = [float(i) for i in line.split()[1:]]
                        idle, total = p[3] + p[4], sum(p)
                        if self._last_cpu:
                            id_d, to_d = idle - self._last_cpu[0], total - self._last_cpu[1]
                            if to_d > 0: self._state['cpu'] = round(100.0 * (1.0 - id_d / to_d))
                        self._last_cpu = (idle, total); break
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
                tot, av = int(lines[0].split()[1]), int(lines[2].split()[1])
                if tot > 0: self._state['mem'] = round(100.0 * (1.0 - (av / tot)))
            with open('/sys/class/thermal/thermal_zone0/temp') as f:
                self._state['temp'] = round(int(f.read().strip()) / 1000)
        except: pass

    def on_ui_update(self, ui):
        try:
            for k in ['face', 'channel', 'aps', 'uptime', 'mode']:
                v = ui.get(k)
                if v: self._state[k] = str(v)
            m = ui.get('status')
            if m is not None: self._state['message'] = str(m)
            s = ui.get('shakes')
            if s:
                match = re.search(r'\((\d+)\)', str(s)) or re.search(r'(\d+)', str(s))
                if match: self._state['pwnd'] = int(match.group(1))
        except: pass

    def on_handshake(self, agent, filename, access_point, client_station):
        try:
            entry = {'ssid': access_point.get('hostname', 'Unknown'), 'filename': os.path.basename(filename)}
            self._state['session_handshakes'].insert(0, entry)
        except: pass

    def _get_hs_dir(self):
        return self.handshake_dir if os.path.isdir(self.handshake_dir) else '/home/pi/handshakes'

    def _list_handshakes(self):
        res = []
        try:
            d = self._get_hs_dir()
            files = [f for f in os.listdir(d) if f.endswith('.pcap') or f.endswith('.pcapng')]
            files.sort(key=lambda f: -os.path.getmtime(os.path.join(d, f)))
            for f in files:
                fpath = os.path.join(d, f)
                res.append({
                    'ssid': f.rsplit('_', 1)[0], 'filename': f,
                    'size': str(round(os.path.getsize(fpath) / 1024, 1)) + " KB",
                    'mtime': time.strftime('%d/%m/%Y %H:%M', time.localtime(os.path.getmtime(fpath)))
                })
        except: pass
        return res

    def on_webhook(self, path, request):
        from flask import Response, jsonify, send_file
        p = (path or '').strip('/')
        if p == 'api/state': return jsonify(self._state)
        if p == 'api/handshakes': return jsonify(self._list_handshakes())
        if p.startswith('api/handshakes/download/'):
            return send_file(os.path.join(self._get_hs_dir(), os.path.basename(p.split('/')[-1])), as_attachment=True)
        if p == 'api/handshakes/delete':
            fpath = os.path.join(self._get_hs_dir(), os.path.basename(request.args.get('file', '')))
            if os.path.isfile(fpath): os.remove(fpath)
            return jsonify({'status': 'ok'})
        if p == 'api/restart':
            import pwnagotchi as pw; pw.restart(request.args.get('mode', 'MANU').upper()); return jsonify({'status': 'ok'})
        return Response(_HTML.replace('__INITIAL_STATE__', json.dumps(self._state)), mimetype='text/html')

_HTML = r"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>gotchiLink</title><style>
* { box-sizing: border-box; }
:root { --bg:#050505; --card:#111; --green:#00ff41; --dim:rgba(0,255,65,0.08); --border:rgba(0,255,65,0.2); --blue:#00aaff; --muted:#666; }
body { background:var(--bg); color:var(--green); font-family:monospace; margin:0; padding-bottom:80px; text-transform:uppercase; overflow-x:hidden; }
body::after { content:''; position:fixed; inset:0; background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.04) 2px,rgba(0,0,0,.04) 4px); pointer-events:none; }
.topbar { display:flex; justify-content:space-between; align-items:center; padding:12px 16px; background:#000; border-bottom:1px solid var(--border); position:sticky; top:0; z-index:10; }
.hostname-row { display:flex; justify-content:space-between; align-items:center; padding:14px 16px; border-bottom:1px solid var(--border); }
.badge { font-size:10px; border:1px solid var(--green); padding:2px 8px; border-radius:3px; }
.card { border:1px solid var(--border); margin:12px; padding:0; background:var(--card); border-radius:4px; overflow:hidden; }
.face-row { display:flex; align-items:center; padding:18px 15px; gap:15px; }
.face { font-size:28px; color:#fff; min-width:120px; text-align:center; }
.face-msg { font-size:11px; color:var(--muted); line-height:1.5; padding-left:15px; border-left:1px solid var(--border); flex:1; }
.session-row { display:flex; justify-content:space-between; padding:10px 16px; background:var(--dim); border-top:1px solid var(--border); font-size:10px; font-weight:bold; }
.grid { display:grid; grid-template-columns: 1fr 1fr 1fr; text-align:center; border-top:1px solid var(--border); }
.stat-cell { padding:12px; border-right:1px solid var(--border); border-bottom:1px solid var(--border); }
.stat-cell:nth-child(3n) { border-right:none; }
.lbl { font-size:9px; color:#008822; margin-bottom:5px; }
.val { font-size:17px; font-weight:bold; color:#eee; }
.info-row { display:flex; justify-content:space-between; padding:11px 16px; border-bottom:1px solid rgba(0,255,65,0.05); font-size:12px; }
.info-key { color:var(--muted); }
.tab-bar { position:fixed; bottom:0; width:100%; display:flex; background:#000; border-top:1px solid var(--border); }
.tab { flex:1; text-align:center; padding:18px; cursor:pointer; color:#005511; font-weight:bold; letter-spacing:1px; }
.tab.active { color:var(--green); background:var(--dim); }
.hs-card { border-bottom:1px solid var(--border); padding:12px 16px; display:flex; justify-content:space-between; align-items:center; }
.btn { background:var(--dim); border:1px solid var(--green); color:var(--green); padding:6px 12px; cursor:pointer; text-decoration:none; margin-left:5px; font-size:11px; }
</style></head><body>
<div class="topbar"><span onclick="location.reload()">↻ REFRESH</span><span style="letter-spacing:4px; font-weight:bold;">GOTCHILINK</span><span onclick="doRestart()">⏻ RESTART</span></div>
<div class="hostname-row"><span id="n">> PWNAGOTCHI</span><div><span class="badge">ONLINE</span> <span class="badge" style="color:var(--blue); border-color:var(--blue);">PWND <span id="pwn">0</span></span></div></div>
<div id="dash">
  <div class="card">
    <div class="face-row"><div class="face" id="f">(- _ -)</div><div class="face-msg" id="m"></div></div>
    <div class="session-row"><span>SESSION HANDSHAKES</span><span id="sh" style="color:var(--blue)">0</span></div>
    <div class="grid">
      <div class="stat-cell"><div class="lbl">MODE</div><div class="val" id="mode">-</div></div>
      <div class="stat-cell"><div class="lbl">CHAN</div><div class="val" id="ch">-</div></div>
      <div class="stat-cell"><div class="lbl">APS</div><div class="val" id="aps">0</div></div>
      <div class="stat-cell"><div class="lbl">RAM</div><div class="val" id="ram">0%</div></div>
      <div class="stat-cell"><div class="lbl">CPU</div><div class="val" id="cpu">0%</div></div>
      <div class="stat-cell"><div class="lbl">TEMP</div><div class="val" id="tmp">0C</div></div>
    </div>
  </div>
  <div class="card">
    <div class="info-row"><span class="info-key">NAME</span><span id="in">-</span></div>
    <div class="info-row"><span class="info-key">VERSION</span><span id="iv">-</span></div>
    <div class="info-row"><span class="info-key">PLUGIN</span><span id="ip">-</span></div>
    <div class="info-row"><span class="info-key">ENABLED PLUGINS</span><span id="ie">-</span></div>
    <div class="info-row"><span class="info-key">UPTIME</span><span id="iu">-</span></div>
    <div class="info-row"><span class="info-key">BOARD</span><span id="ib">-</span></div>
    <div class="info-row"><span class="info-key">POWER SUPPLY</span><span>USB</span></div>
  </div>
</div>
<div id="hss" style="display:none;"><div id="hl"></div></div>
<div class="tab-bar"><div id="t1" class="tab active" onclick="tab('dash')">DASHBOARD</div><div id="t2" class="tab" onclick="tab('hss')">HANDSHAKES</div></div>
<script>
const base = '/plugins/pwnagotchi_custom_ui/';
function upd() {
  fetch(base+'api/state').then(r=>r.json()).then(s=>{
    document.getElementById('f').innerText = s.face;
    document.getElementById('m').innerText = s.message;
    document.getElementById('mode').innerText = s.mode;
    document.getElementById('ch').innerText = s.channel;
    document.getElementById('aps').innerText = s.aps;
    document.getElementById('ram').innerText = s.mem+'%';
    document.getElementById('cpu').innerText = s.cpu+'%';
    document.getElementById('tmp').innerText = s.temp+'C';
    document.getElementById('pwn').innerText = s.pwnd;
    document.getElementById('sh').innerText = s.session_handshakes.length;
    document.getElementById('in').innerText = s.name;
    document.getElementById('iv').innerText = s.pwnagotchi_version;
    document.getElementById('ip').innerText = s.plugin_version;
    document.getElementById('ie').innerText = s.enabled_plugins;
    document.getElementById('iu').innerText = s.uptime;
    document.getElementById('ib').innerText = s.board;
    document.getElementById('n').innerText = '> '+s.name;
  });
}
function tab(id) {
  document.getElementById('dash').style.display = id==='dash'?'block':'none';
  document.getElementById('hss').style.display = id==='hss'?'block':'none';
  document.getElementById('t1').className = id==='dash'?'tab active':'tab';
  document.getElementById('t2').className = id==='hss'?'tab active':'tab';
  if(id==='hss') loadHS();
}
function loadHS() {
  fetch(base+'api/handshakes').then(r=>r.json()).then(l => {
    document.getElementById('hl').innerHTML = l.map(h => `
      <div class="hs-card">
        <div><div style="font-weight:bold;color:#fff">${h.ssid}</div><div style="font-size:10px;color:var(--muted)">${h.mtime} · ${h.size}</div></div>
        <div><a class="btn" href="${base}api/handshakes/download/${h.filename}">⬇</a><button class="btn" style="color:#f33;border-color:#f33" onclick="delHS('${h.filename}')">🗑</button></div>
      </div>`).join('') || '<div style="padding:40px;text-align:center;color:var(--muted)">// empty</div>';
  });
}
function delHS(f) { if(confirm('Delete '+f+'?')) fetch(base+'api/handshakes/delete?file='+f).then(loadHS); }
function doRestart() { const m = prompt("Enter 'AUTO' or 'MANU'"); if(m) fetch(base+'api/restart?mode='+m); }
setInterval(upd, 3000); upd();
</script></body></html>"""
