#!/usr/bin/env python3
"""ZKas Dual Alert v0.2.2 — Unofficial Community Tool - local web setup and background monitoring."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import monitor

APP_VERSION = "0.2.2"
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CONFIG = DATA / "config.json"
WEB_CONFIG = DATA / "web_config.json"
LOG = DATA / "alert.log"
DEFAULT_USER = "admin"
DEFAULT_PASSWORD = "12345678"

MONITOR_THREAD = None
MONITOR_STOP = threading.Event()
MONITOR_LOCK = threading.Lock()
SESSIONS = {}


def ensure_data_dir():
    DATA.mkdir(parents=True, exist_ok=True)
    # Automatic migration from older portable releases that stored data beside app.py.
    for name in ("config.json", "web_config.json", "state.json", "alert.log"):
        old = ROOT / name
        new = DATA / name
        if old.exists() and not new.exists():
            try:
                shutil.copy2(old, new)
            except OSError:
                pass


def log(msg):
    ensure_data_dir()
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return base64.b64encode(salt).decode() + ":" + base64.b64encode(dk).decode()


def verify_password(password, encoded):
    try:
        s, d = encoded.split(":", 1)
        salt = base64.b64decode(s)
        expected = base64.b64decode(d)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def save_web(data):
    ensure_data_dir()
    WEB_CONFIG.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_web():
    ensure_data_dir()
    if WEB_CONFIG.exists():
        try:
            return json.loads(WEB_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            pass
    data = {
        "username": DEFAULT_USER,
        "password_hash": hash_password(DEFAULT_PASSWORD),
        "bind": "127.0.0.1",
        "port": 3040,
    }
    save_web(data)
    return data


def default_config():
    return {
        "bridge": {
            "base_url": "http://127.0.0.1:3033",
            "poll_seconds": 30,
            "timeout_seconds": 5,
            "down_after_failures": 3,
            "alert_existing_on_first_run": False,
        },
        "alerts": {
            "zkas_block": True,
            "kas_block": True,
            "kas_reward_known": True,
            "bridge_down": True,
            "bridge_recovered": True,
        },
        "notifications": {
            "console": {"enabled": True},
            "smtp": {
                "enabled": False,
                "host": "smtp.gmail.com",
                "port": 587,
                "security": "starttls",
                "username": "",
                "password": "",
                "from": "",
                "to": "",
            },
            "twilio": {"enabled": False, "account_sid": "", "auth_token": "", "from_number": "", "to_number": ""},
            "ntfy": {"enabled": False, "url": "", "token": ""},
            "discord": {"enabled": False, "webhook_url": ""},
        },
        "state_file": "state.json",
    }


def save_config(cfg):
    ensure_data_dir()
    CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def load_config():
    ensure_data_dir()
    if not CONFIG.exists():
        save_config(default_config())
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        cfg = default_config()
        save_config(cfg)
        return cfg


def monitor_running():
    return MONITOR_THREAD is not None and MONITOR_THREAD.is_alive()


def _monitor_worker():
    try:
        monitor.STOP = False
        monitor.monitor(CONFIG, stop_event=MONITOR_STOP)
    except Exception as exc:
        log(f"Monitor stopped with error: {exc}")


def start_monitor():
    global MONITOR_THREAD, MONITOR_STOP
    with MONITOR_LOCK:
        if monitor_running():
            return True, "Monitor is already running."
        MONITOR_STOP = threading.Event()
        MONITOR_THREAD = threading.Thread(target=_monitor_worker, name="ZKasDualAlertMonitor", daemon=True)
        MONITOR_THREAD.start()
        return True, "Monitor started automatically."


def stop_monitor():
    global MONITOR_THREAD
    with MONITOR_LOCK:
        if not monitor_running():
            return True, "Monitor is already stopped."
        MONITOR_STOP.set()
        MONITOR_THREAD.join(timeout=6)
        if MONITOR_THREAD.is_alive():
            return False, "Monitor is stopping; wait a few seconds and refresh."
        MONITOR_THREAD = None
        return True, "Monitor stopped."


def bridge_status(url):
    try:
        snap = monitor.BridgeSource(url, timeout=3).fetch()
        workers = "-" if snap.active_workers is None else snap.active_workers
        shares = "-" if snap.total_shares is None else snap.total_shares
        return True, f"Connected — ZKAS blocks: {snap.zkas_total} | KAS blocks: {snap.kas_total} | workers: {workers} | shares: {shares}"
    except Exception as exc:
        return False, f"Not connected: {exc}"


def run_notification_test(kind="test"):
    cfg = monitor.deep_resolve(load_config())
    notifiers = monitor.build_notifiers(cfg)
    base_url = cfg.get("bridge", {}).get("base_url", "http://127.0.0.1:3033")

    if kind == "zkas":
        subject = "🧪 TEST — 🚨 ZKAS BLOCK FOUND"
        body = f"SIMULATION ONLY — no real block was found.\nChain: ZKAS\nBridge: {base_url}\nMining state and counters were not changed."
    elif kind == "kas":
        subject = "🧪 TEST — 🚨 KAS BLOCK FOUND"
        body = f"SIMULATION ONLY — no real block was found.\nChain: KAS\nBridge: {base_url}\nMining state and counters were not changed."
    else:
        subject = "ZKas Dual Alert — Unofficial Community Tool test"
        body = f"Notifications are working. Bridge: {base_url}"

    results = monitor.notify_all(notifiers, subject, body)
    external = [r for r in results if r[0] != "ConsoleNotifier"]
    if not external:
        return False, "No external notification channel is enabled."

    lines = []
    all_ok = True
    for name, ok, detail in external:
        label = {
            "SMTPNotifier": "Email",
            "DiscordNotifier": "Discord",
            "TwilioNotifier": "SMS",
            "NtfyNotifier": "Push",
        }.get(name, name)
        lines.append(f"{label}: {'SENT' if ok else 'FAILED — ' + detail}")
        all_ok = all_ok and ok
    return all_ok, " | ".join(lines)


def esc(value):
    return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


CSS = """
body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#0b1020;color:#eef2ff;margin:0}
.wrap{max-width:900px;margin:32px auto;padding:0 18px}.card{background:#141b31;border:1px solid #293453;border-radius:16px;padding:22px;margin:16px 0}
h1{margin-bottom:4px}.muted{color:#aab4d0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
label{display:block;margin:10px 0 5px;font-weight:600}input[type=text],input[type=password],input[type=number]{box-sizing:border-box;width:100%;padding:11px;border-radius:9px;border:1px solid #3b486c;background:#0c1326;color:white}
button,.btn{background:#e8ecff;color:#10162a;border:0;border-radius:9px;padding:10px 14px;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block;margin:4px}
.ok{color:#76e6a7}.bad{color:#ff8b8b}.soon{opacity:.55}.pill{padding:5px 9px;border-radius:999px;background:#273250}.warn{background:#332914;border:1px solid #705a22;padding:12px;border-radius:10px}
.statusok{background:#153424;border:1px solid #2f7650}.statusbad{background:#3b1c22;border:1px solid #7b3944}
@media(max-width:650px){.grid{grid-template-columns:1fr}}
"""


def page(title, body):
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head><body><div class="wrap">{body}</div></body></html>"""


def checkbox(name, label, checked):
    mark = "checked" if checked else ""
    return f'<label><input type="checkbox" name="{name}" {mark}> {esc(label)}</label>'


def login_page(error=""):
    return page("ZKas Dual Alert — Unofficial Community Tool Login", f"""
<div class="card"><h1>ZKas Dual Alert</h1><p><b>Unofficial Community Tool</b></p><p class="muted">v{APP_VERSION} · local read-only mining alerts · not affiliated with or endorsed by the ZKas project</p>
<h2>Login</h2>{f'<p class="bad">{esc(error)}</p>' if error else ''}
<form method="post" action="/login"><label>Username</label><input name="username" value="admin">
<label>Password</label><input type="password" name="password"><p><button>Login</button></p></form>
<p class="warn">Default login: <b>admin / 12345678</b>. Change it before exposing the UI outside a trusted machine/network.</p></div>""")


def dashboard(message="", success=True):
    cfg = load_config()
    b = cfg["bridge"]
    a = cfg["alerts"]
    smtp = cfg["notifications"]["smtp"]
    disc = cfg["notifications"]["discord"]
    ok, status = bridge_status(b.get("base_url", "http://127.0.0.1:3033"))
    msg_html = ""
    if message:
        cls = "statusok" if success else "statusbad"
        msg_html = f'<div class="card {cls}">{esc(message)}</div>'

    return page("ZKas Dual Alert — Unofficial Community Tool", f"""
<h1>ZKas Dual Alert <span class="pill">v{APP_VERSION}</span></h1>
<p><b>Unofficial Community Tool</b></p>
<p class="muted">Independent read-only companion for compatible ZKas/Kaspa solo-dual-mode bridges. Not affiliated with or endorsed by the ZKas project.</p>
{msg_html}
<div class="card"><h2>Bridge</h2><p class="{'ok' if ok else 'bad'}">{esc(status)}</p>
<form method="post" action="/save">
<label>Dashboard address</label><input type="text" name="base_url" value="{esc(b.get('base_url'))}">
<div class="grid"><div><label>Poll seconds</label><input type="number" min="5" name="poll_seconds" value="{int(b.get('poll_seconds',30))}"></div>
<div><label>Failures before offline alert</label><input type="number" min="1" name="down_after_failures" value="{int(b.get('down_after_failures',3))}"></div></div>

<h2>Alerts</h2>
{checkbox('zkas_block','ZKAS Block Found',a.get('zkas_block',True))}
{checkbox('kas_block','KAS Block Found',a.get('kas_block',True))}
{checkbox('kas_reward_known','KAS Reward Known',a.get('kas_reward_known',True))}
{checkbox('bridge_down','Bridge Offline',a.get('bridge_down',True))}
{checkbox('bridge_recovered','Bridge Recovered',a.get('bridge_recovered',True))}

<h2>Notifications</h2>
<h3>Email</h3>
{checkbox('smtp_enabled','Enable Email',smtp.get('enabled',False))}
<div class="grid"><div><label>Gmail / SMTP username</label><input name="smtp_username" value="{esc(smtp.get('username'))}"></div>
<div><label>Send alerts to</label><input name="smtp_to" value="{esc(smtp.get('to'))}"></div></div>
<label>Gmail App Password</label><input type="password" name="smtp_password" placeholder="Leave blank to keep saved password">
<p class="muted">Saved password: {'Yes' if smtp.get('password') else 'No'}. Gmail requires an App Password. Email is optional.</p>

<h3>Discord</h3>
{checkbox('discord_enabled','Enable Discord',disc.get('enabled',False))}
<label>Discord webhook URL</label><input type="password" name="discord_webhook" placeholder="Leave blank to keep saved webhook">
<p class="muted">Saved webhook: {'Yes' if disc.get('webhook_url') else 'No'}.</p>

<div class="grid soon"><div><h3>Phone Push</h3><p>Coming soon</p></div><div><h3>SMS / Text</h3><p>Coming soon</p></div></div>
<p><button type="submit">Save Settings</button></p></form>

<form method="post" action="/test"><button>Send Test Alert</button></form>
<form method="post" action="/simulate"><button name="chain" value="zkas">Simulate ZKAS Block</button><button name="chain" value="kas">Simulate KAS Block</button></form>
<form method="post" action="/monitor"><button name="action" value="{'stop' if monitor_running() else 'start'}">{'Stop' if monitor_running() else 'Start'} Monitor</button></form>
<p class="muted">Monitor: {'RUNNING' if monitor_running() else 'STOPPED'}</p>
</div>

<div class="card"><h2>Security</h2>
<p>No seed phrases, private keys, wallet-spending permissions, node-control commands, or miner-control commands are used.</p>
<a class="btn" href="/password">Change Login Password</a> <a class="btn" href="/logout">Logout</a></div>""")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_html(self, html, code=200, cookie=None):
        data = html.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def form(self):
        n = int(self.headers.get("Content-Length", "0"))
        return {k: v[-1] for k, v in parse_qs(self.rfile.read(n).decode()).items()}

    def authed(self):
        cookie = self.headers.get("Cookie", "")
        token = next((x.split("=", 1)[1] for x in cookie.split("; ") if x.startswith("zkas_session=")), None)
        return token in SESSIONS

    def do_GET(self):
        if self.path == "/login":
            return self.send_html(login_page())
        if self.path == "/logout":
            cookie = self.headers.get("Cookie", "")
            token = next((x.split("=", 1)[1] for x in cookie.split("; ") if x.startswith("zkas_session=")), None)
            if token:
                SESSIONS.pop(token, None)
            return self.send_html(login_page(), cookie="zkas_session=; Max-Age=0; HttpOnly; SameSite=Strict")
        if not self.authed():
            return self.send_html(login_page())
        if self.path == "/":
            return self.send_html(dashboard())
        if self.path == "/password":
            return self.send_html(page("Change Password", """<div class="card"><h1>Change Login Password</h1>
<form method="post" action="/password"><label>Current password</label><input type="password" name="current">
<label>New password</label><input type="password" name="new"><p><button>Change Password</button></p></form><a href="/">Back</a></div>"""))
        self.send_error(404)

    def do_POST(self):
        if self.path == "/login":
            f = self.form()
            w = load_web()
            if f.get("username") == w["username"] and verify_password(f.get("password", ""), w["password_hash"]):
                token = secrets.token_urlsafe(32)
                SESSIONS[token] = time.time()
                return self.send_html(dashboard("Logged in."), cookie=f"zkas_session={token}; HttpOnly; SameSite=Strict")
            return self.send_html(login_page("Invalid username or password."), 401)

        if not self.authed():
            return self.send_html(login_page(), 401)

        if self.path == "/save":
            f = self.form()
            cfg = load_config()
            cfg["bridge"]["base_url"] = f.get("base_url", "http://127.0.0.1:3033").strip()
            cfg["bridge"]["poll_seconds"] = max(5, int(f.get("poll_seconds", "30")))
            cfg["bridge"]["down_after_failures"] = max(1, int(f.get("down_after_failures", "3")))
            for k in ("zkas_block", "kas_block", "kas_reward_known", "bridge_down", "bridge_recovered"):
                cfg["alerts"][k] = k in f

            smtp = cfg["notifications"]["smtp"]
            smtp["enabled"] = "smtp_enabled" in f
            smtp["username"] = f.get("smtp_username", "").strip()
            smtp["from"] = smtp["username"]
            smtp["to"] = f.get("smtp_to", "").strip()
            pwd = f.get("smtp_password", "")
            if pwd:
                smtp["password"] = pwd.replace(" ", "")

            disc = cfg["notifications"]["discord"]
            disc["enabled"] = "discord_enabled" in f
            webhook = f.get("discord_webhook", "").strip()
            if webhook:
                disc["webhook_url"] = webhook

            save_config(cfg)
            return self.send_html(dashboard("Settings saved."))

        if self.path == "/test":
            ok, msg = run_notification_test("test")
            return self.send_html(dashboard(msg, ok))

        if self.path == "/simulate":
            chain = self.form().get("chain", "").lower()
            if chain not in ("zkas", "kas"):
                return self.send_html(dashboard("Invalid simulation type.", False), 400)
            ok, msg = run_notification_test(chain)
            return self.send_html(dashboard(msg, ok))

        if self.path == "/monitor":
            action = self.form().get("action")
            ok, msg = stop_monitor() if action == "stop" else start_monitor()
            return self.send_html(dashboard(msg, ok))

        if self.path == "/password":
            f = self.form()
            w = load_web()
            if not verify_password(f.get("current", ""), w["password_hash"]):
                return self.send_html(page("Change Password", "<div class=card><p class=bad>Current password is incorrect.</p><a href=/password>Back</a></div>"), 400)
            if len(f.get("new", "")) < 8:
                return self.send_html(page("Change Password", "<div class=card><p class=bad>New password must be at least 8 characters.</p><a href=/password>Back</a></div>"), 400)
            w["password_hash"] = hash_password(f["new"])
            save_web(w)
            return self.send_html(dashboard("Login password changed."))

        self.send_error(404)


def main():
    ensure_data_dir()
    w = load_web()
    load_config()
    log(f"ZKas Dual Alert — Unofficial Community Tool Web v{APP_VERSION}")
    log(f"Open http://{w['bind']}:{w['port']}  (default login admin / 12345678)")
    ok, msg = start_monitor()
    log(msg)
    server = ThreadingHTTPServer((w["bind"], int(w["port"])), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_monitor()
        server.server_close()


if __name__ == "__main__":
    main()
