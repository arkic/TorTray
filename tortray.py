#!/usr/bin/env python3
import base64
import json
import os
import plistlib
import signal
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from datetime import datetime

import rumps

APP_ID = "com.arktor.tray"
APP_NAME = "TorTray"
DEFAULT_SOCKS_PORT = 9050
DEFAULT_CONTROL_PORT = 9051

APP_SUPPORT = Path.home() / "Library" / "Application Support" / "TorTray"
CONFIG_PATH = APP_SUPPORT / "config.json"
LOG_PATH = APP_SUPPORT / "tor.log"
LAUNCH_AGENTS = Path.home() / "Library" / "LaunchAgents"
PLIST_PATH = LAUNCH_AGENTS / f"{APP_ID}.plist"


DEFAULT_CONFIG = {
    "run_on_launch": False,
    "bridge": "snowflake",
    "tor_path": "tor",
    "socks_port": DEFAULT_SOCKS_PORT,
    "control_port": DEFAULT_CONTROL_PORT,
    "pt_paths": {
        "obfs4proxy": "/opt/homebrew/bin/obfs4proxy:/usr/local/bin/obfs4proxy",
        "snowflake-client": "/opt/homebrew/bin/snowflake-client:/usr/local/bin/snowflake-client",
        "meek-client": "/opt/homebrew/bin/meek-client:/usr/local/bin/meek-client"
    },
    "obfs4_bridges": [
        "# Paste your obfs4 Bridge lines here",
        "# Example format:",
        "# obfs4 IP:PORT FINGERPRINT cert=CERT iat-mode=0"
    ]
}


def ensure_app_support():
    APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2))


def load_config():
    ensure_app_support()
    return json.loads(CONFIG_PATH.read_text())


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def resolve_first_existing(paths: str):
    for p in paths.split(":"):
        if Path(p).exists():
            return p
    return None




class TorTray(rumps.App):
    def __init__(self):
        super().__init__(
            "TorTray",       # Only text in menu bar
            quit_button=None,
            menu=[
                rumps.MenuItem("Connect", callback=self.toggle_connect),
                None,
                rumps.MenuItem("Run on Launch", callback=self.toggle_run_on_launch),
                {"Bridges": [
                    rumps.MenuItem("obfs4", callback=self.set_bridge),
                    rumps.MenuItem("Snowflake", callback=self.set_bridge),
                    rumps.MenuItem("meek-azure", callback=self.set_bridge),
                    rumps.MenuItem("None", callback=self.set_bridge),
                ]},
                None,
                rumps.MenuItem("Edit Config", callback=self.edit_config),
                rumps.MenuItem("Show Tor Logs", callback=self.show_logs),
                rumps.MenuItem("Clear Logs", callback=self.clear_logs),
                rumps.MenuItem("Quit", callback=self.quit_app)
            ]
        )


        self.cfg = load_config()
        self.tor_proc = None
        self.log_file = None
        self.log_lock = threading.Lock()
        self._set_bridge_checks(self.cfg.get("bridge", "snowflake"))
        self.menu["Run on Launch"].state = self.cfg.get("run_on_launch", False)
        self.status_timer = rumps.Timer(self._poll_status, 2)
        self.status_timer.start()
        
        # Initialize the log file
        self._init_log_file()


    def _init_log_file(self):
        """Initialize the log file with a session header"""
        with self.log_lock:
            with open(LOG_PATH, 'a') as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"TorTray Session Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*60}\n")

    def toggle_connect(self, _):
        if self.tor_proc and self.tor_proc.poll() is None:
            self._disconnect()
        else:
            self._connect()

    def toggle_run_on_launch(self, sender):
        new_state = not sender.state
        sender.state = new_state
        self.cfg["run_on_launch"] = new_state
        save_config(self.cfg)
        if new_state:
            self._install_login_item()
        else:
            self._remove_login_item()

    def set_bridge(self, sender):
        name = sender.title.lower().replace(" ", "")
        self.cfg["bridge"] = name if name != "none" else "none"
        save_config(self.cfg)
        self._set_bridge_checks(self.cfg["bridge"])

    def edit_config(self, _):
        subprocess.Popen(["open", str(CONFIG_PATH)])

    def show_logs(self, _):
        """Open the log file in the default text editor"""
        if not LOG_PATH.exists():
            rumps.notification(APP_NAME, "No logs", "No log file exists yet")
            return
        subprocess.Popen(["open", str(LOG_PATH)])

    def clear_logs(self, _):
        """Clear the log file"""
        with self.log_lock:
            with open(LOG_PATH, 'w') as f:
                f.write(f"Logs cleared: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        rumps.notification(APP_NAME, "Logs cleared", "The log file has been cleared")

    def quit_app(self, _):
        self._disconnect()
        self._append_log("TorTray shutting down")
        rumps.quit_application()

    def _set_bridge_checks(self, current):
        for title in ("obfs4", "Snowflake", "meek-azure", "None"):
            self.menu["Bridges"][title].state = (title.lower().replace(" ", "") == current)

    def _connect(self):
        try:
            tor_cmd, torrc = self._build_tor_command()
        except RuntimeError as e:
            rumps.notification(APP_NAME, "Config error", str(e))
            self._append_log(f"Config error: {e}")
            return
        
        tmp = tempfile.NamedTemporaryFile(prefix="tortray_", suffix=".torrc", delete=False)
        tmp.write(torrc.encode())
        tmp.close()
        
        self._append_log(f"Starting Tor with bridge: {self.cfg.get('bridge', 'none')}")
        self._append_log(f"Torrc file: {tmp.name}")
        
        try:
            self.tor_proc = subprocess.Popen(
                [tor_cmd, "-f", tmp.name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
        except FileNotFoundError:
            rumps.notification(APP_NAME, "Missing tor", "Install tor via Homebrew: brew install tor")
            self._append_log("ERROR: Tor binary not found. Install with: brew install tor")
            return
        
        threading.Thread(target=self._read_tor_output, daemon=True).start()
        self.menu["Connect"].title = "Disconnect"

    def _disconnect(self):
        if self.tor_proc and self.tor_proc.poll() is None:
            self._append_log("Disconnecting Tor...")
            self.tor_proc.terminate()
            try:
                self.tor_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.tor_proc.kill()
        self.tor_proc = None
        self.menu["Connect"].title = "Connect"

    def _read_tor_output(self):
        for line in self.tor_proc.stdout:
            self._append_log(line.rstrip())
        self._append_log("(Tor process exited)")

    def _append_log(self, line):
        """Append a line to the log file"""
        with self.log_lock:
            with open(LOG_PATH, 'a') as f:
                timestamp = datetime.now().strftime('%b %d %H:%M:%S.%f')[:-3]
                f.write(f"{timestamp} {line}\n")
                f.flush()

    def _poll_status(self, _):
        alive = self.tor_proc is not None and self.tor_proc.poll() is None
        socks_ok = self._port_open("127.0.0.1", self.cfg.get("socks_port", DEFAULT_SOCKS_PORT)) if alive else False

    def _port_open(self, host, port):
        try:
            with socket.create_connection((host, port), timeout=0.3):
                return True
        except OSError:
            return False

    def _build_tor_command(self):
        cfg = self.cfg
        tor_cmd = cfg.get("tor_path", "tor")
        socks = int(cfg.get("socks_port", DEFAULT_SOCKS_PORT))
        control = int(cfg.get("control_port", DEFAULT_CONTROL_PORT))
        
        lines = [
            f"SOCKSPort {socks}",
            f"ControlPort {control}",
            "CookieAuthentication 1",
            "Log notice stdout",
            "ClientOnly 1",
        ]
        
        bridge = cfg.get("bridge", "snowflake")
        
        if bridge == "obfs4":
            obfs4 = resolve_first_existing(cfg["pt_paths"]["obfs4proxy"]) or "obfs4proxy"
            bridges = [b for b in cfg.get("obfs4_bridges", []) if not b.strip().startswith("#") and b.strip()]
            if not bridges:
                raise RuntimeError("No obfs4 bridges in config.json. Add obfs4 bridge lines to use this option.")
            lines += [
                "UseBridges 1",
                f"ClientTransportPlugin obfs4 exec {obfs4}"
            ] + [f"Bridge {b}" for b in bridges]
            
        elif bridge == "snowflake":
            sfc = resolve_first_existing(cfg["pt_paths"]["snowflake-client"]) or "snowflake-client"
            # Fixed Snowflake bridge configuration with proper fingerprint
            lines += [
                "UseBridges 1",
                f"ClientTransportPlugin snowflake exec {sfc} -log /dev/null",
                # Using the official Snowflake bridge
                "Bridge snowflake 192.0.2.4:80 8838024498816A039FCBBAB14E6F40A0843051FA fingerprint=8838024498816A039FCBBAB14E6F40A0843051FA url=https://1098762253.rsc.cdn77.org/ fronts=www.cdn77.com,www.phpmyadmin.net ice=stun:stun.l.google.com:19302,stun:stun.altar.com.pl:3478,stun:stun.antisip.com:3478,stun:stun.bluesip.net:3478,stun:stun.dus.net:3478,stun:stun.epygi.com:3478,stun:stun.sonetel.com:3478,stun:stun.uls.co.za:3478,stun:stun.voipgate.com:3478,stun:stun.voys.nl:3478 utls-imitate=hellorandomizedalpn"
            ]
            
        elif bridge == "meek-azure":
            meek = resolve_first_existing(cfg["pt_paths"]["meek-client"]) or "meek-client"
            # Fixed meek-azure bridge configuration
            lines += [
                "UseBridges 1",
                f"ClientTransportPlugin meek_lite exec {meek}",
                "Bridge meek_lite 192.0.2.18:80 BE776A53492E1E044A26F17306E1BC46A55A1625 url=https://meek.azureedge.net/ front=ajax.aspnetcdn.com"
            ]
        
        return tor_cmd, "\n".join(lines) + "\n"

    def _install_login_item(self):
        LAUNCH_AGENTS.mkdir(parents=True, exist_ok=True)
        python_exec = sys.executable
        script_path = Path(__file__).resolve()
        plist = {
            "Label": APP_ID,
            "ProgramArguments": [python_exec, str(script_path)],
            "RunAtLoad": True,
            "KeepAlive": False,
            "StandardOutPath": str(APP_SUPPORT / "launch_stdout.log"),
            "StandardErrorPath": str(APP_SUPPORT / "launch_stderr.log"),
        }
        with open(PLIST_PATH, "wb") as f:
            plistlib.dump(plist, f)
        subprocess.run(["launchctl", "load", str(PLIST_PATH)])

    def _remove_login_item(self):
        if PLIST_PATH.exists():
            subprocess.run(["launchctl", "unload", str(PLIST_PATH)])
            try:
                PLIST_PATH.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    TorTray().run()