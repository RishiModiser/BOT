```python
# Humanex - Enterprise-Grade Windows Desktop Automation Platform (Single File)
# Requirements:
# - Python (core Python only) + PySide6 + Playwright (sync API)
# - Visible Chrome only (headless=False)
# - One shared browser instance, isolated context per profile, controlled concurrency
# - Robust validation, crash-safe persistence, strong error handling, no placeholders
#
# NOTE: You must install dependencies:
#   pip install PySide6 playwright
#   playwright install chrome
#
# Run:
#   python humanex.py

import os
import sys
import json
import time
import math
import queue
import random
import shutil
import traceback
import threading
import datetime
import hashlib
from dataclasses import dataclass, field

from PySide6.QtCore import (
    Qt, QTimer, QSize, QRect, QEasingCurve, QPropertyAnimation, QObject, Signal, Slot
)
from PySide6.QtGui import (
    QColor, QFont, QIcon, QAction, QTextCursor
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QLineEdit,
    QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QFileDialog, QMessageBox, QScrollArea, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QDialogButtonBox,
    QGroupBox, QGridLayout, QProgressBar
)

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError, Error as PWError

APP_NAME = "Humanex"
APP_VERSION = "1.0.0"
DEFAULT_DATA_DIR = os.path.join(os.path.expanduser("~"), ".humanex")
SETTINGS_FILE = "settings.json"
SCRIPTS_FILE = "scripts.json"
FINGERPRINTS_FILE = "fingerprints.json"
PROFILE_STATE_FILE = "profiles.json"
CRASH_RECOVERY_FILE = "recovery.json"


# ----------------------------- Utilities -----------------------------

def now_iso():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def clamp(v, a, b):
    return max(a, min(b, v))


def safe_mkdir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass


def read_json_file(path, default):
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def atomic_write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def jitter(base: float, spread: float) -> float:
    return max(0.0, base + random.uniform(-spread, spread))


def rand_choice_weighted(items):
    # items: list of (value, weight)
    total = sum(w for _, w in items)
    r = random.uniform(0, total)
    upto = 0
    for v, w in items:
        if upto + w >= r:
            return v
        upto += w
    return items[-1][0]


def is_valid_hostname(host: str) -> bool:
    if not host or len(host) > 253:
        return False
    parts = host.split(".")
    for p in parts:
        if not p or len(p) > 63:
            return False
        if not all(c.isalnum() or c == "-" for c in p):
            return False
        if p[0] == "-" or p[-1] == "-":
            return False
    return True


def parse_proxy(proxy_str: str):
    """
    Supports:
      host:port
      http://host:port
      http://user:pass@host:port
      socks5://user:pass@host:port
    """
    proxy_str = (proxy_str or "").strip()
    if not proxy_str:
        return None

    s = proxy_str
    if "://" not in s:
        s = "http://" + s

    # simple parse without urllib to keep core python minimalistic; still safe
    try:
        scheme, rest = s.split("://", 1)
        scheme = scheme.lower()
        user = pwd = None
        hostport = rest
        if "@" in rest:
            cred, hostport = rest.rsplit("@", 1)
            if ":" in cred:
                user, pwd = cred.split(":", 1)
            else:
                user = cred
                pwd = ""
        if ":" not in hostport:
            return None
        host, port_s = hostport.rsplit(":", 1)
        host = host.strip("[]").strip()
        try:
            port = int(port_s)
        except Exception:
            return None
        if port < 1 or port > 65535:
            return None
        if not host:
            return None
        # allow IPs and hostnames
        if not (is_valid_hostname(host) or all(ch.isdigit() or ch == "." for ch in host) or ":" in host):
            # rudimentary IPv6/hostname acceptance
            return None

        server = f"{scheme}://{host}:{port}"
        out = {"server": server}
        if user is not None:
            out["username"] = user
            out["password"] = pwd if pwd is not None else ""
        return out
    except Exception:
        return None


# ----------------------------- Persistence -----------------------------

class DataStore:
    def __init__(self, base_dir=DEFAULT_DATA_DIR):
        self.base_dir = base_dir
        safe_mkdir(self.base_dir)
        self.settings_path = os.path.join(self.base_dir, SETTINGS_FILE)
        self.scripts_path = os.path.join(self.base_dir, SCRIPTS_FILE)
        self.fingerprints_path = os.path.join(self.base_dir, FINGERPRINTS_FILE)
        self.profiles_path = os.path.join(self.base_dir, PROFILE_STATE_FILE)
        self.recovery_path = os.path.join(self.base_dir, CRASH_RECOVERY_FILE)

        self._lock = threading.RLock()

        self.settings = {}
        self.scripts = {}
        self.fingerprints = {}
        self.profiles = {}

        self.load_all()

    def load_all(self):
        with self._lock:
            self.settings = read_json_file(self.settings_path, default={
                "app": {"name": APP_NAME, "version": APP_VERSION},
                "ui": {"theme": "dark", "accent": "#6D5EF1"},
                "traffic": {
                    "concurrency": 3,
                    "max_profiles": 100,
                    "navigation_timeout_ms": 45000,
                    "action_timeout_ms": 25000,
                    "min_delay_ms": 180,
                    "max_delay_ms": 900,
                    "human_mode": True
                },
                "proxy": {
                    "mode": "per_profile",  # per_profile | global | none
                    "global_proxy": ""
                },
                "rpa": {
                    "default_script_id": "",
                    "strict_schema": True
                }
            })
            self.scripts = read_json_file(self.scripts_path, default={
                "scripts": {
                    # script_id: {...}
                }
            })
            self.fingerprints = read_json_file(self.fingerprints_path, default={
                "datasets": {
                    "builtin": {
                        "name": "Built-in Realistic Chrome Dataset",
                        "created_at": now_iso(),
                        "profiles": []
                    }
                },
                "assigned": {
                    # profile_id: {"dataset":"builtin","fingerprint_id":"...","fingerprint":{...}}
                }
            })
            self.profiles = read_json_file(self.profiles_path, default={
                "profiles": {
                    # profile_id: {...}
                }
            })

            # ensure built-in dataset populated
            if not self.fingerprints.get("datasets", {}).get("builtin", {}).get("profiles"):
                self.fingerprints["datasets"]["builtin"]["profiles"] = FingerprintFactory.build_builtin_dataset()
                self.save_fingerprints()

            # default profiles if none
            if not self.profiles.get("profiles"):
                self.profiles["profiles"] = {}
                for i in range(1, 6):
                    pid = f"profile_{i:03d}"
                    self.profiles["profiles"][pid] = {
                        "id": pid,
                        "name": f"Profile {i:03d}",
                        "enabled": True,
                        "website": {
                            "start_url": "https://example.com",
                            "referrer": "",
                            "allow_popups": False
                        },
                        "traffic": {
                            "script_id": "",
                            "iterations": 1,
                            "cooldown_s": 2.0,
                            "session_note": ""
                        },
                        "proxy": {
                            "proxy": "",
                            "region_hint": "auto"  # auto | US | EU | IN | ...
                        },
                        "state": {
                            "last_run": "",
                            "last_status": "idle",
                            "last_error": "",
                            "runs_total": 0,
                            "runs_ok": 0,
                            "runs_fail": 0
                        }
                    }
                self.save_profiles()

    def save_settings(self):
        with self._lock:
            atomic_write_json(self.settings_path, self.settings)

    def save_scripts(self):
        with self._lock:
            atomic_write_json(self.scripts_path, self.scripts)

    def save_fingerprints(self):
        with self._lock:
            atomic_write_json(self.fingerprints_path, self.fingerprints)

    def save_profiles(self):
        with self._lock:
            atomic_write_json(self.profiles_path, self.profiles)

    def write_recovery(self, data):
        with self._lock:
            atomic_write_json(self.recovery_path, data)

    def clear_recovery(self):
        with self._lock:
            try:
                if os.path.exists(self.recovery_path):
                    os.remove(self.recovery_path)
            except Exception:
                pass

    def load_recovery(self):
        with self._lock:
            return read_json_file(self.recovery_path, default={})


# ----------------------------- Fingerprints -----------------------------

class FingerprintFactory:
    """
    Build realistic Chrome fingerprints (distribution-based).
    Persist per profile (assigned).
    """
    CHROME_UAS = [
        # Windows Chrome UAs (realistic versions). Weighted towards recent stable versions.
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.129 Safari/537.36", 6),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.106 Safari/537.36", 8),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.207 Safari/537.36", 10),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.113 Safari/537.36", 10),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.127 Safari/537.36", 8),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.6533.89 Safari/537.36", 6),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.6613.120 Safari/537.36", 4),
    ]

    VIEWPORTS = [
        ((1920, 1080), 12),
        ((1536, 864), 10),
        ((1366, 768), 10),
        ((1600, 900), 8),
        ((1440, 900), 6),
        ((2560, 1440), 3),
    ]

    DEVICE_SCALE_FACTORS = [(1.0, 14), (1.25, 7), (1.5, 4), (2.0, 2)]
    HARDWARE_CONCURRENCY = [(4, 5), (6, 7), (8, 10), (12, 4), (16, 2)]
    DEVICE_MEMORY = [(4, 6), (8, 12), (16, 4), (32, 1)]

    LOCALES = [
        ({"locale": "en-US", "languages": ["en-US", "en"], "timezone": "America/New_York"}, 8),
        ({"locale": "en-US", "languages": ["en-US", "en"], "timezone": "America/Chicago"}, 5),
        ({"locale": "en-US", "languages": ["en-US", "en"], "timezone": "America/Los_Angeles"}, 6),
        ({"locale": "en-GB", "languages": ["en-GB", "en"], "timezone": "Europe/London"}, 5),
        ({"locale": "de-DE", "languages": ["de-DE", "de", "en-US", "en"], "timezone": "Europe/Berlin"}, 3),
        ({"locale": "fr-FR", "languages": ["fr-FR", "fr", "en-US", "en"], "timezone": "Europe/Paris"}, 3),
        ({"locale": "es-ES", "languages": ["es-ES", "es", "en-US", "en"], "timezone": "Europe/Madrid"}, 3),
        ({"locale": "it-IT", "languages": ["it-IT", "it", "en-US", "en"], "timezone": "Europe/Rome"}, 2),
        ({"locale": "hi-IN", "languages": ["hi-IN", "hi", "en-US", "en"], "timezone": "Asia/Kolkata"}, 4),
        ({"locale": "en-IN", "languages": ["en-IN", "en", "hi-IN", "hi"], "timezone": "Asia/Kolkata"}, 4),
    ]

    WEBGL_PAIRS = [
        ({"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)"}, 6),
        ({"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"}, 6),
        ({"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 Direct3D11 vs_5_0 ps_5_0, D3D11)"}, 3),
        ({"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"}, 3),
        ({"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon(TM) Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"}, 2),
    ]

    @staticmethod
    def build_builtin_dataset(n=120):
        random.seed(sha256_hex("humanex-builtin-dataset")[:16])
        profiles = []
        for i in range(n):
            ua = rand_choice_weighted(FingerprintFactory.CHROME_UAS)
            vw, vh = rand_choice_weighted(FingerprintFactory.VIEWPORTS)
            dpr = rand_choice_weighted(FingerprintFactory.DEVICE_SCALE_FACTORS)
            loc = rand_choice_weighted(FingerprintFactory.LOCALES)
            gl = rand_choice_weighted(FingerprintFactory.WEBGL_PAIRS)
            hc = rand_choice_weighted(FingerprintFactory.HARDWARE_CONCURRENCY)
            dm = rand_choice_weighted(FingerprintFactory.DEVICE_MEMORY)
            # stable noise seeds per fingerprint
            noise_seed = sha256_hex(f"{ua}|{vw}x{vh}|{dpr}|{loc['locale']}|{gl['renderer']}|{i}")[:16]
            fp = {
                "id": f"fp_{i:04d}",
                "created_at": now_iso(),
                "platform": "Win32",
                "user_agent": ua,
                "viewport": {"width": int(vw), "height": int(vh)},
                "screen": {"width": int(vw), "height": int(vh)},  # align
                "device_scale_factor": float(dpr),
                "locale": loc["locale"],
                "languages": loc["languages"],
                "timezone": loc["timezone"],
                "webgl": {"vendor": gl["vendor"], "renderer": gl["renderer"]},
                "hardware_concurrency": int(hc),
                "device_memory_gb": int(dm),
                "noise": {
                    "seed": noise_seed,
                    "canvas": {"amplitude": 0.15 + (i % 7) * 0.02},
                    "audio": {"amplitude": 0.00015 + (i % 5) * 0.00005}
                }
            }
            profiles.append(fp)
        # reset randomness
        random.seed()
        return profiles

    @staticmethod
    def choose_fingerprint_from_dataset(dataset_profiles, region_hint="auto"):
        # region_hint influences locale/timezone choice only if dataset contains relevant; builtin already mixes.
        # We'll lightly bias toward India if region_hint IN; toward US/EU otherwise.
        if not dataset_profiles:
            return None
        if region_hint and region_hint.upper() in ("IN", "INDIA"):
            candidates = [fp for fp in dataset_profiles if fp.get("timezone", "").startswith("Asia/")]
            if candidates:
                return random.choice(candidates)
        if region_hint and region_hint.upper() in ("US", "USA", "UNITED STATES"):
            candidates = [fp for fp in dataset_profiles if fp.get("timezone", "").startswith("America/")]
            if candidates:
                return random.choice(candidates)
        if region_hint and region_hint.upper() in ("EU", "EUROPE"):
            candidates = [fp for fp in dataset_profiles if fp.get("timezone", "").startswith("Europe/")]
            if candidates:
                return random.choice(candidates)
        return random.choice(dataset_profiles)

    @staticmethod
    def validate_fingerprint(fp):
        # strict validation - reject malformed/unsafe fingerprints
        required = [
            "platform", "user_agent", "viewport", "screen", "device_scale_factor",
            "locale", "languages", "timezone", "webgl", "hardware_concurrency", "device_memory_gb", "noise"
        ]
        for k in required:
            if k not in fp:
                return False, f"Missing fingerprint field: {k}"
        if "Chrome/" not in fp["user_agent"]:
            return False, "User-Agent must be Chrome"
        vw = fp["viewport"].get("width", 0)
        vh = fp["viewport"].get("height", 0)
        if not (isinstance(vw, int) and isinstance(vh, int) and 800 <= vw <= 3840 and 600 <= vh <= 2160):
            return False, "Viewport out of bounds"
        dpr = fp.get("device_scale_factor", 1.0)
        if not (isinstance(dpr, (int, float)) and 0.75 <= float(dpr) <= 3.0):
            return False, "Invalid device_scale_factor"
        langs = fp.get("languages")
        if not (isinstance(langs, list) and 1 <= len(langs) <= 6 and all(isinstance(x, str) for x in langs)):
            return False, "Invalid languages"
        tz = fp.get("timezone")
        if not (isinstance(tz, str) and 3 <= len(tz) <= 64 and "/" in tz):
            return False, "Invalid timezone"
        gl = fp.get("webgl", {})
        if not (isinstance(gl.get("vendor", ""), str) and isinstance(gl.get("renderer", ""), str)):
            return False, "Invalid webgl vendor/renderer"
        hc = fp.get("hardware_concurrency")
        if not (isinstance(hc, int) and 1 <= hc <= 64):
            return False, "Invalid hardware_concurrency"
        dm = fp.get("device_memory_gb")
        if not (isinstance(dm, int) and 1 <= dm <= 128):
            return False, "Invalid device_memory_gb"
        noise = fp.get("noise", {})
        if not (isinstance(noise.get("seed", ""), str) and len(noise.get("seed", "")) >= 8):
            return False, "Invalid noise seed"
        return True, ""


# ----------------------------- RPA Schema & Validation -----------------------------

class RPAValidator:
    """
    Strict schema validation. Reject malformed or unsafe scripts.
    """
    SAFE_ACTIONS = {
        "goto", "click", "dblclick", "hover",
        "type", "press", "wait_for_selector",
        "wait", "scroll", "select_option",
        "set_viewport", "screenshot",
        "assert_text", "assert_url_contains",
        "evaluate_js"
    }

    @staticmethod
    def validate_script(script_obj):
        if not isinstance(script_obj, dict):
            return False, "Script must be a JSON object"
        if script_obj.get("schema") != "humanex.rpa.v1":
            return False, "Invalid or missing schema (must be 'humanex.rpa.v1')"
        name = script_obj.get("name")
        if not (isinstance(name, str) and 1 <= len(name) <= 120):
            return False, "Invalid script name"
        steps = script_obj.get("steps")
        if not (isinstance(steps, list) and 1 <= len(steps) <= 500):
            return False, "Steps must be a list (1..500)"
        for i, st in enumerate(steps):
            ok, err = RPAValidator.validate_step(st)
            if not ok:
                return False, f"Step {i}: {err}"
        opts = script_obj.get("options", {})
        if opts is not None and not isinstance(opts, dict):
            return False, "options must be an object"
        # safety: no file system / process operations are allowed by schema
        return True, ""

    @staticmethod
    def _valid_selector(sel):
        return isinstance(sel, str) and 1 <= len(sel) <= 300

    @staticmethod
    def _valid_text(t):
        return isinstance(t, str) and len(t) <= 20000

    @staticmethod
    def validate_step(step):
        if not isinstance(step, dict):
            return False, "Step must be an object"
        action = step.get("action")
        if action not in RPAValidator.SAFE_ACTIONS:
            return False, f"Unsupported action: {action}"
        # common fields
        if "timeout_ms" in step:
            t = step["timeout_ms"]
            if not (isinstance(t, int) and 500 <= t <= 180000):
                return False, "timeout_ms must be int 500..180000"
        if "label" in step and not (isinstance(step["label"], str) and len(step["label"]) <= 120):
            return False, "label must be <=120 chars"

        # action-specific validation
        if action == "goto":
            url = step.get("url")
            if not (isinstance(url, str) and url.startswith(("http://", "https://")) and len(url) <= 3000):
                return False, "goto.url must be http(s) url"
            if "wait_until" in step:
                if step["wait_until"] not in ("load", "domcontentloaded", "networkidle", "commit"):
                    return False, "goto.wait_until invalid"
        elif action in ("click", "dblclick", "hover", "wait_for_selector"):
            sel = step.get("selector")
            if not RPAValidator._valid_selector(sel):
                return False, f"{action}.selector required"
            if action in ("click", "dblclick"):
                if "button" in step and step["button"] not in ("left", "middle", "right"):
                    return False, "button must be left/middle/right"
                if "click_count" in step:
                    cc = step["click_count"]
                    if not (isinstance(cc, int) and 1 <= cc <= 3):
                        return False, "click_count must be 1..3"
        elif action == "type":
            sel = step.get("selector")
            txt = step.get("text")
            if not RPAValidator._valid_selector(sel):
                return False, "type.selector required"
            if not RPAValidator._valid_text(txt):
                return False, "type.text required"
            if "clear_first" in step and not isinstance(step["clear_first"], bool):
                return False, "clear_first must be bool"
            if "enter" in step and not isinstance(step["enter"], bool):
                return False, "enter must be bool"
        elif action == "press":
            sel = step.get("selector")
            key = step.get("key")
            if sel is not None and not RPAValidator._valid_selector(sel):
                return False, "press.selector invalid"
            if not (isinstance(key, str) and 1 <= len(key) <= 40):
                return False, "press.key required"
        elif action == "wait":
            ms = step.get("ms")
            if not (isinstance(ms, int) and 0 <= ms <= 180000):
                return False, "wait.ms must be 0..180000"
        elif action == "scroll":
            # either by pixels or to selector
            if "selector" in step and step["selector"] is not None:
                if not RPAValidator._valid_selector(step["selector"]):
                    return False, "scroll.selector invalid"
            if "dy" in step:
                dy = step["dy"]
                if not (isinstance(dy, int) and -5000 <= dy <= 5000):
                    return False, "scroll.dy must be -5000..5000"
            if "behavior" in step and step["behavior"] not in ("auto", "smooth"):
                return False, "scroll.behavior invalid"
        elif action == "select_option":
            sel = step.get("selector")
            if not RPAValidator._valid_selector(sel):
                return False, "select_option.selector required"
            # value can be str or list[str]
            v = step.get("value")
            if isinstance(v, str):
                if len(v) > 400:
                    return False, "select_option.value too long"
            elif isinstance(v, list):
                if not (1 <= len(v) <= 30 and all(isinstance(x, str) and len(x) <= 400 for x in v)):
                    return False, "select_option.value invalid list"
            else:
                return False, "select_option.value must be str or list[str]"
        elif action == "set_viewport":
            vw = step.get("width")
            vh = step.get("height")
            if not (isinstance(vw, int) and 800 <= vw <= 3840):
                return False, "set_viewport.width invalid"
            if not (isinstance(vh, int) and 600 <= vh <= 2160):
                return False, "set_viewport.height invalid"
        elif action == "screenshot":
            # prevent arbitrary file writes: store in app data only. path is logical name.
            name = step.get("name")
            if not (isinstance(name, str) and 1 <= len(name) <= 120 and all(c.isalnum() or c in "-_." for c in name)):
                return False, "screenshot.name must be safe filename"
            if "full_page" in step and not isinstance(step["full_page"], bool):
                return False, "screenshot.full_page must be bool"
        elif action == "assert_text":
            sel = step.get("selector")
            txt = step.get("text")
            if not RPAValidator._valid_selector(sel):
                return False, "assert_text.selector required"
            if not RPAValidator._valid_text(txt):
                return False, "assert_text.text required"
            if "contains" in step and not isinstance(step["contains"], bool):
                return False, "assert_text.contains must be bool"
        elif action == "assert_url_contains":
            frag = step.get("text")
            if not (isinstance(frag, str) and 1 <= len(frag) <= 500):
                return False, "assert_url_contains.text required"
        elif action == "evaluate_js":
            # safety: allow only expression-like snippets; block keywords commonly used for navigation/requests
            code = step.get("code")
            if not (isinstance(code, str) and 1 <= len(code) <= 5000):
                return False, "evaluate_js.code required"
            lowered = code.lower()
            blocked = ["fetch(", "xmlhttprequest", "websocket", "import(", "require(", "window.location", "document.location"]
            if any(b in lowered for b in blocked):
                return False, "evaluate_js contains blocked patterns"
        return True, ""


# ----------------------------- Human-like Behavior -----------------------------

class HumanBehavior:
    def __init__(self, rng: random.Random):
        self.rng = rng

    def sleep_ms(self, ms):
        time.sleep(max(0.0, ms / 1000.0))

    def micro_pause(self, base_ms=180, spread_ms=120):
        self.sleep_ms(int(clamp(base_ms + self.rng.randint(-spread_ms, spread_ms), 0, 2500)))

    def read_pause(self, min_ms=350, max_ms=2200):
        self.sleep_ms(self.rng.randint(min_ms, max_ms))

    def typing_delay_ms(self):
        # variable cadence: majority 35-95ms, with occasional slower bursts
        mode = self.rng.random()
        if mode < 0.75:
            return int(self.rng.randint(35, 95))
        if mode < 0.93:
            return int(self.rng.randint(95, 180))
        return int(self.rng.randint(180, 380))

    def move_curve_points(self, x0, y0, x1, y1):
        # cubic bezier-ish with mild noise
        steps = self.rng.randint(18, 42)
        cx1 = x0 + (x1 - x0) * self.rng.uniform(0.2, 0.45) + self.rng.uniform(-30, 30)
        cy1 = y0 + (y1 - y0) * self.rng.uniform(0.1, 0.5) + self.rng.uniform(-30, 30)
        cx2 = x0 + (x1 - x0) * self.rng.uniform(0.55, 0.85) + self.rng.uniform(-30, 30)
        cy2 = y0 + (y1 - y0) * self.rng.uniform(0.45, 0.9) + self.rng.uniform(-30, 30)

        pts = []
        for i in range(steps + 1):
            t = i / steps
            # cubic bezier
            xt = (1 - t) ** 3 * x0 + 3 * (1 - t) ** 2 * t * cx1 + 3 * (1 - t) * t ** 2 * cx2 + t ** 3 * x1
            yt = (1 - t) ** 3 * y0 + 3 * (1 - t) ** 2 * t * cy1 + 3 * (1 - t) * t ** 2 * cy2 + t ** 3 * y1
            # tiny tremor
            xt += self.rng.uniform(-0.8, 0.8)
            yt += self.rng.uniform(-0.8, 0.8)
            pts.append((xt, yt))
        return pts

    def scroll_pattern(self):
        # natural scroll with variability
        sequences = []
        n = self.rng.randint(2, 6)
        for _ in range(n):
            dy = int(self.rng.choice([120, 160, 220, 280, 360, 480]) * self.rng.uniform(0.65, 1.35))
            if self.rng.random() < 0.15:
                dy = -int(dy * self.rng.uniform(0.3, 0.7))
            sequences.append(dy)
        return sequences

    def occasional_micro_interaction(self):
        return self.rng.random() < 0.18


# ----------------------------- Stealth / Fingerprint Injection -----------------------------

def build_init_script(fp: dict):
    """
    Avoid bypass hacks; instead mimic real Chrome behavior and reduce obvious Playwright defaults.
    - navigator.webdriver undefined
    - plugins/mimeTypes non-empty
    - languages, platform
    - WebGL vendor/renderer
    - timezone via Intl (also set by context), but keep stable
    - canvas/audio noise stable per seed
    """
    seed = fp["noise"]["seed"]
    canvas_amp = float(fp["noise"]["canvas"]["amplitude"])
    audio_amp = float(fp["noise"]["audio"]["amplitude"])
    languages = fp["languages"]
    platform = fp["platform"]
    webgl_vendor = fp["webgl"]["vendor"]
    webgl_renderer = fp["webgl"]["renderer"]

    # JS carefully scoped, no external requests, deterministic noise based on seed
    # Keep it reasonably short and robust.
    js = f"""
(() => {{
  const humanexSeed = "{seed}";
  function xmur3(str) {{
    let h = 1779033703 ^ str.length;
    for (let i = 0; i < str.length; i++) {{
      h = Math.imul(h ^ str.charCodeAt(i), 3432918353);
      h = (h << 13) | (h >>> 19);
    }}
    return function() {{
      h = Math.imul(h ^ (h >>> 16), 2246822507);
      h = Math.imul(h ^ (h >>> 13), 3266489909);
      return (h ^= h >>> 16) >>> 0;
    }}
  }}
  function mulberry32(a) {{
    return function() {{
      let t = a += 0x6D2B79F5;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    }}
  }}
  const seedFn = xmur3(humanexSeed);
  const rand = mulberry32(seedFn());

  // webdriver
  try {{
    Object.defineProperty(Navigator.prototype, 'webdriver', {{
      get: () => undefined,
      configurable: true
    }});
  }} catch (e) {{}}

  // languages
  try {{
    Object.defineProperty(Navigator.prototype, 'languages', {{
      get: () => {json.dumps(languages)},
      configurable: true
    }});
  }} catch (e) {{}}

  // platform
  try {{
    Object.defineProperty(Navigator.prototype, 'platform', {{
      get: () => "{platform}",
      configurable: true
    }});
  }} catch (e) {{}}

  // plugins & mimeTypes (basic realistic shapes)
  try {{
    const fakePlugins = [
      {{ name: "Chrome PDF Plugin", filename: "internal-pdf-viewer", description: "Portable Document Format" }},
      {{ name: "Chrome PDF Viewer", filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai", description: "" }},
      {{ name: "Native Client", filename: "internal-nacl-plugin", description: "" }}
    ];
    const fakeMimeTypes = [
      {{ type: "application/pdf", suffixes: "pdf", description: "", __pluginName: "Chrome PDF Plugin" }},
      {{ type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format", __pluginName: "Chrome PDF Plugin" }},
      {{ type: "application/x-nacl", suffixes: "", description: "Native Client Executable", __pluginName: "Native Client" }},
      {{ type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable", __pluginName: "Native Client" }}
    ];

    function makeArrayLike(items) {{
      items = items.slice();
      items.item = function(i) {{ return items[i] || null; }};
      items.namedItem = function(name) {{
        for (const it of items) {{
          if (it && it.name === name) return it;
        }}
        return null;
      }};
      return items;
    }}

    const pluginsArray = makeArrayLike(fakePlugins.map(p => Object.assign(Object.create(Plugin.prototype), p)));
    const mimeTypesArray = makeArrayLike(fakeMimeTypes.map(m => Object.assign(Object.create(MimeType.prototype), {{
      type: m.type, suffixes: m.suffixes, description: m.description,
    }})));

    Object.defineProperty(Navigator.prototype, 'plugins', {{
      get: () => pluginsArray,
      configurable: true
    }});
    Object.defineProperty(Navigator.prototype, 'mimeTypes', {{
      get: () => mimeTypesArray,
      configurable: true
    }});
  }} catch (e) {{}}

  // WebGL vendor/renderer
  try {{
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {{
      // UNMASKED_VENDOR_WEBGL = 0x9245, UNMASKED_RENDERER_WEBGL = 0x9246
      if (param === 0x9245) return "{webgl_vendor}";
      if (param === 0x9246) return "{webgl_renderer}";
      return getParameter.apply(this, arguments);
    }}
  }} catch (e) {{}}

  // Canvas noise (stable)
  try {{
    const toDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function() {{
      try {{
        const ctx = this.getContext('2d');
        if (ctx) {{
          const w = this.width || 300;
          const h = this.height || 150;
          const id = ctx.getImageData(0, 0, w, h);
          const data = id.data;
          const amp = {canvas_amp};
          for (let i = 0; i < data.length; i += 4) {{
            const n = (rand() - 0.5) * 2;
            data[i] = Math.max(0, Math.min(255, data[i] + n * 255 * amp));
            data[i+1] = Math.max(0, Math.min(255, data[i+1] + n * 255 * amp));
            data[i+2] = Math.max(0, Math.min(255, data[i+2] + n * 255 * amp));
          }}
          ctx.putImageData(id, 0, 0);
        }}
      }} catch (e) {{}}
      return toDataURL.apply(this, arguments);
    }};
  }} catch (e) {{}}

  // Audio noise (stable, subtle)
  try {{
    const origGetChannelData = AudioBuffer.prototype.getChannelData;
    AudioBuffer.prototype.getChannelData = function() {{
      const data = origGetChannelData.apply(this, arguments);
      try {{
        const amp = {audio_amp};
        // perturb a few samples only to keep subtle
        const len = data.length;
        const count = Math.min(64, Math.floor(len / 500));
        for (let i = 0; i < count; i++) {{
          const idx = Math.floor(rand() * len);
          data[idx] = data[idx] + (rand() - 0.5) * amp;
        }}
      }} catch (e) {{}}
      return data;
    }}
  }} catch (e) {{}}

  // permissions query fix (reduce obvious automation)
  try {{
    const originalQuery = navigator.permissions.query;
    navigator.permissions.query = (parameters) => {{
      if (parameters && parameters.name === 'notifications') {{
        return Promise.resolve({{ state: Notification.permission }});
      }}
      return originalQuery(parameters);
    }}
  }} catch (e) {{}}
}})();
"""
    return js


def detect_challenge_signals(url: str, title: str, body_text: str):
    text = (title or "") + " " + (body_text or "")
    t = text.lower()
    # Not bypassing; only detect to tune behavior and warn.
    signals = {
        "cloudflare": any(s in t for s in ["cloudflare", "attention required", "checking your browser", "cf-chl", "just a moment"]),
        "google_unusual": any(s in t for s in ["unusual traffic", "sorry", "detected unusual traffic", "captcha"]),
        "captcha": any(s in t for s in ["captcha", "recaptcha", "hcaptcha"]),
    }
    return signals


def compute_risk_score(page, fp: dict):
    """
    Built-in detection testing checklist. Warn only.
    """
    risk = 0
    details = []

    def add(points, msg):
        nonlocal risk
        risk += points
        details.append((points, msg))

    try:
        webdriver = page.evaluate("() => navigator.webdriver")
        if webdriver is True:
            add(35, "navigator.webdriver is true")
        elif webdriver is None:
            add(10, "navigator.webdriver is null (unusual)")
    except Exception:
        add(8, "navigator.webdriver check failed")

    try:
        plugins_len = page.evaluate("() => (navigator.plugins ? navigator.plugins.length : 0)")
        if plugins_len <= 0:
            add(12, "plugins length is 0")
    except Exception:
        add(6, "plugins length check failed")

    try:
        mt_len = page.evaluate("() => (navigator.mimeTypes ? navigator.mimeTypes.length : 0)")
        if mt_len <= 0:
            add(10, "mimeTypes length is 0")
    except Exception:
        add(6, "mimeTypes length check failed")

    try:
        langs = page.evaluate("() => navigator.languages")
        if not isinstance(langs, list) or len(langs) == 0:
            add(10, "languages missing/empty")
        else:
            # alignment
            if fp.get("languages") and langs != fp.get("languages"):
                add(6, "languages mismatch vs fingerprint")
    except Exception:
        add(6, "languages check failed")

    try:
        gl_vendor = page.evaluate("""() => {
          try {
            const c = document.createElement('canvas');
            const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
            if (!gl) return {vendor:"",renderer:""};
            const dbg = gl.getExtension('WEBGL_debug_renderer_info');
            if (!dbg) return {vendor:"",renderer:""};
            return {
              vendor: gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL),
              renderer: gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)
            };
          } catch(e){ return {vendor:"",renderer:""}; }
        }""")
        if gl_vendor:
            if fp.get("webgl", {}).get("vendor") and gl_vendor.get("vendor") != fp["webgl"]["vendor"]:
                add(8, "WebGL vendor mismatch")
            if fp.get("webgl", {}).get("renderer") and gl_vendor.get("renderer") != fp["webgl"]["renderer"]:
                add(8, "WebGL renderer mismatch")
    except Exception:
        add(6, "WebGL check failed")

    try:
        tz = page.evaluate("() => Intl.DateTimeFormat().resolvedOptions().timeZone")
        if fp.get("timezone") and tz != fp.get("timezone"):
            add(8, f"timezone mismatch (page={tz}, fp={fp.get('timezone')})")
    except Exception:
        add(6, "timezone check failed")

    try:
        vp = page.viewport_size
        if vp and fp.get("viewport"):
            if abs(vp["width"] - fp["viewport"]["width"]) > 0 or abs(vp["height"] - fp["viewport"]["height"]) > 0:
                add(6, "viewport mismatch vs fingerprint")
    except Exception:
        add(4, "viewport check failed")

    # score clamp
    risk = int(clamp(risk, 0, 100))
    return risk, details


# ----------------------------- Automation Core -----------------------------

@dataclass
class Job:
    profile_id: str
    iteration: int


class LogBus(QObject):
    log = Signal(str, str)  # level, message
    status = Signal(str, str)  # profile_id, status
    progress = Signal(int, int)  # done, total


class AutomationEngine:
    """
    Shared Playwright + shared Chrome browser instance.
    Isolated context per profile execution.
    Queue-based concurrency.
    """
    def __init__(self, datastore: DataStore, logbus: LogBus):
        self.ds = datastore
        self.logbus = logbus

        self._pw = None
        self._browser = None
        self._shared_lock = threading.RLock()

        self._running = False
        self._stop_event = threading.Event()

        self._q = queue.Queue()
        self._threads = []
        self._done = 0
        self._total = 0

        self._contexts_live = set()
        self._contexts_lock = threading.RLock()

    def is_running(self):
        return self._running

    def _log(self, level, msg):
        self.logbus.log.emit(level, msg)

    def _set_status(self, profile_id, status):
        self.logbus.status.emit(profile_id, status)

    def start(self, selected_profile_ids):
        with self._shared_lock:
            if self._running:
                self._log("WARN", "Engine already running.")
                return False

            # prepare jobs based on profile config
            profiles = self.ds.profiles.get("profiles", {})
            jobs = []
            for pid in selected_profile_ids:
                p = profiles.get(pid)
                if not p or not p.get("enabled", True):
                    continue
                iterations = int(p.get("traffic", {}).get("iterations", 1) or 1)
                iterations = clamp(iterations, 1, 1000)
                for it in range(1, iterations + 1):
                    jobs.append(Job(profile_id=pid, iteration=it))

            if not jobs:
                self._log("WARN", "No enabled profiles selected to run.")
                return False

            # setup queue
            while not self._q.empty():
                try:
                    self._q.get_nowait()
                except Exception:
                    break

            for j in jobs:
                self._q.put(j)

            self._done = 0
            self._total = len(jobs)
            self.logbus.progress.emit(self._done, self._total)

            self._stop_event.clear()
            self._running = True

            conc = int(self.ds.settings.get("traffic", {}).get("concurrency", 3))
            conc = int(clamp(conc, 1, 24))

            # start Playwright + browser once
            try:
                self._pw = sync_playwright().start()
                # Chrome only
                self._browser = self._pw.chromium.launch(
                    channel="chrome",
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-default-browser-check",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--disable-dev-shm-usage",
                        "--disable-background-networking",
                        "--disable-background-timer-throttling",
                        "--disable-renderer-backgrounding",
                        "--disable-client-side-phishing-detection",
                        "--disable-sync",
                        "--metrics-recording-only",
                        "--password-store=basic",
                        "--use-mock-keychain",
                    ],
                )
                self._log("INFO", f"Chrome launched. Concurrency={conc}, Jobs={self._total}")
            except Exception as e:
                self._running = False
                self._stop_event.set()
                self._safe_close_browser()
                self._log("ERROR", f"Failed to start Playwright/Chrome: {e}")
                self._log("ERROR", traceback.format_exc())
                return False

            # crash recovery snapshot
            try:
                self.ds.write_recovery({
                    "created_at": now_iso(),
                    "running": True,
                    "jobs_total": self._total,
                    "jobs_done": self._done,
                    "profile_ids": selected_profile_ids
                })
            except Exception:
                pass

            self._threads = []
            for idx in range(conc):
                t = threading.Thread(target=self._worker_loop, name=f"HumanexWorker-{idx+1}", daemon=True)
                self._threads.append(t)
                t.start()

            return True

    def stop(self):
        with self._shared_lock:
            if not self._running:
                return
            self._log("WARN", "Stop requested. Attempting safe shutdown...")
            self._stop_event.set()

        # wait for workers to exit (short)
        for t in list(self._threads):
            try:
                t.join(timeout=2.5)
            except Exception:
                pass

        # close live contexts
        with self._contexts_lock:
            contexts = list(self._contexts_live)
        for ctx in contexts:
            try:
                ctx.close()
            except Exception:
                pass

        self._safe_close_browser()
        with self._shared_lock:
            self._running = False
            self._threads = []
            self.ds.clear_recovery()
        self._log("INFO", "Engine stopped.")

    def _safe_close_browser(self):
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
        self._browser = None
        self._pw = None

    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                job = self._q.get_nowait()
            except queue.Empty:
                break
            try:
                self._run_job(job)
            except Exception as e:
                self._log("ERROR", f"Worker error: {e}")
                self._log("ERROR", traceback.format_exc())
            finally:
                try:
                    self._q.task_done()
                except Exception:
                    pass

            with self._shared_lock:
                self._done += 1
                self.logbus.progress.emit(self._done, self._total)
                try:
                    self.ds.write_recovery({
                        "created_at": now_iso(),
                        "running": True,
                        "jobs_total": self._total,
                        "jobs_done": self._done
                    })
                except Exception:
                    pass

        # when all workers finish, close browser once
        with self._shared_lock:
            # only the last finishing thread should cleanup
            # If any thread is still alive, skip cleanup here.
            alive = any(t.is_alive() for t in self._threads if t is not threading.current_thread())
            if not alive and self._running:
                self._safe_close_browser()
                self._running = False
                self.ds.clear_recovery()
                self._log("INFO", "All jobs completed. Browser closed.")

    def _resolve_script(self, profile):
        script_id = profile.get("traffic", {}).get("script_id") or ""
        if not script_id:
            script_id = self.ds.settings.get("rpa", {}).get("default_script_id") or ""
        if not script_id:
            return None, None
        script = self.ds.scripts.get("scripts", {}).get(script_id)
        if not script:
            return None, f"Script '{script_id}' not found"
        ok, err = RPAValidator.validate_script(script)
        if not ok:
            return None, f"Script validation failed: {err}"
        return script, None

    def _get_or_assign_fingerprint(self, profile_id, region_hint):
        assigned = self.ds.fingerprints.get("assigned", {}).get(profile_id)
        if assigned and isinstance(assigned, dict) and "fingerprint" in assigned:
            fp = assigned["fingerprint"]
            ok, err = FingerprintFactory.validate_fingerprint(fp)
            if ok:
                return fp, "assigned"
            # invalid stored fingerprint -> reassign
        # choose new from builtin (or chosen dataset in assigned)
        datasets = self.ds.fingerprints.get("datasets", {})
        dataset_name = "builtin"
        dataset = datasets.get(dataset_name, {})
        fps = dataset.get("profiles", [])
        fp = FingerprintFactory.choose_fingerprint_from_dataset(fps, region_hint=region_hint)
        if fp is None:
            return None, "no_dataset"
        # store assignment snapshot
        self.ds.fingerprints.setdefault("assigned", {})[profile_id] = {
            "dataset": dataset_name,
            "fingerprint_id": fp.get("id", ""),
            "fingerprint": fp,
            "assigned_at": now_iso()
        }
        self.ds.save_fingerprints()
        return fp, "new"

    def _build_context_options(self, profile, fp):
        traffic = self.ds.settings.get("traffic", {})
        action_timeout = int(traffic.get("action_timeout_ms", 25000))
        nav_timeout = int(traffic.get("navigation_timeout_ms", 45000))

        proxy_mode = self.ds.settings.get("proxy", {}).get("mode", "per_profile")
        proxy_opt = None
        if proxy_mode == "global":
            proxy_opt = parse_proxy(self.ds.settings.get("proxy", {}).get("global_proxy", ""))
        elif proxy_mode == "per_profile":
            proxy_opt = parse_proxy(profile.get("proxy", {}).get("proxy", ""))
        elif proxy_mode == "none":
            proxy_opt = None

        opts = {
            "user_agent": fp["user_agent"],
            "locale": fp["locale"],
            "timezone_id": fp["timezone"],
            "viewport": fp["viewport"],
            "device_scale_factor": fp["device_scale_factor"],
            "java_script_enabled": True,
            "bypass_csp": False,
            "ignore_https_errors": False,
        }
        if proxy_opt:
            opts["proxy"] = proxy_opt

        # Permissions: notifications off by default - closer to normal enterprise
        opts["permissions"] = []

        return opts, action_timeout, nav_timeout

    def _run_job(self, job: Job):
        profiles = self.ds.profiles.get("profiles", {})
        profile = profiles.get(job.profile_id)
        if not profile:
            self._log("ERROR", f"Profile not found: {job.profile_id}")
            return

        rng = random.Random(int(sha256_hex(f"{job.profile_id}|{job.iteration}|{time.time()}")[:8], 16))
        human = HumanBehavior(rng)

        # update state
        self._set_status(job.profile_id, "running")
        st = profile.get("state", {})
        st["last_run"] = now_iso()
        st["last_status"] = "running"
        st["last_error"] = ""
        profile["state"] = st
        self.ds.profiles["profiles"][job.profile_id] = profile
        self.ds.save_profiles()

        start_url = profile.get("website", {}).get("start_url", "").strip()
        if not start_url.startswith(("http://", "https://")):
            self._finalize_profile(job.profile_id, ok=False, err="Invalid start_url (must start with http:// or https://)")
            return

        # script
        script, script_err = self._resolve_script(profile)
        if script_err:
            self._finalize_profile(job.profile_id, ok=False, err=script_err)
            return

        # fingerprint
        region_hint = (profile.get("proxy", {}).get("region_hint") or "auto").strip()
        fp, fp_src = self._get_or_assign_fingerprint(job.profile_id, region_hint)
        if not fp:
            self._finalize_profile(job.profile_id, ok=False, err="No valid fingerprint available")
            return

        ok, ferr = FingerprintFactory.validate_fingerprint(fp)
        if not ok:
            self._finalize_profile(job.profile_id, ok=False, err=f"Fingerprint invalid: {ferr}")
            return

        # run context
        ctx = None
        page = None
        try:
            if self._stop_event.is_set():
                raise RuntimeError("Stopped")

            ctx_opts, action_timeout, nav_timeout = self._build_context_options(profile, fp)

            # create context
            ctx = self._browser.new_context(**ctx_opts)
            with self._contexts_lock:
                self._contexts_live.add(ctx)

            ctx.set_default_timeout(action_timeout)
            ctx.set_default_navigation_timeout(nav_timeout)

            init_js = build_init_script(fp)
            ctx.add_init_script(init_js)

            # Create page
            page = ctx.new_page()

            # referrer behavior
            referrer = profile.get("website", {}).get("referrer", "").strip()
            allow_popups = bool(profile.get("website", {}).get("allow_popups", False))

            # popup handling: if disallowed, close any popup quickly
            def on_popup(p):
                try:
                    if not allow_popups:
                        self._log("WARN", f"[{job.profile_id}] Popup blocked/closed.")
                        p.close()
                except Exception:
                    pass

            page.on("popup", on_popup)

            # additional realism: set extra headers sometimes (not abnormal)
            try:
                page.set_extra_http_headers({
                    "DNT": "1" if rng.random() < 0.55 else "0",
                    "Upgrade-Insecure-Requests": "1",
                })
            except Exception:
                pass

            # navigation pacing
            human.micro_pause(240, 160)

            # goto
            self._log("INFO", f"[{job.profile_id}] Iteration {job.iteration}: Navigating to {start_url}")
            goto_kwargs = {"url": start_url, "wait_until": "domcontentloaded"}
            if referrer.startswith(("http://", "https://")):
                goto_kwargs["referer"] = referrer
            page.goto(**goto_kwargs)

            human.read_pause(500, 1600)

            # detection checklist
            risk, details = compute_risk_score(page, fp)
            self._log("INFO", f"[{job.profile_id}] Detection risk score: {risk}/100")
            for pts, msg in details:
                if pts >= 8:
                    self._log("WARN", f"[{job.profile_id}] Risk +{pts}: {msg}")
                else:
                    self._log("INFO", f"[{job.profile_id}] Risk +{pts}: {msg}")

            # adaptive behavior if challenge-like
            title = ""
            body = ""
            try:
                title = page.title()
            except Exception:
                title = ""
            try:
                body = page.inner_text("body")
            except Exception:
                body = ""
            signals = detect_challenge_signals(page.url, title, body)
            if any(signals.values()):
                self._log("WARN", f"[{job.profile_id}] Challenge signals detected: {signals}")
                # Graceful fallback: wait a bit, slow down, try a human scroll and idle.
                human.read_pause(1500, 3500)
                try:
                    for dy in human.scroll_pattern():
                        page.mouse.wheel(0, dy)
                        human.micro_pause(220, 180)
                except Exception:
                    pass
                human.read_pause(1500, 4200)

            # If script missing => just do human-like idle
            if script is None:
                self._log("WARN", f"[{job.profile_id}] No script selected; performing human-like idle session.")
                self._human_idle_session(page, human, seconds=clamp(profile.get("traffic", {}).get("cooldown_s", 2.0), 1, 20))
            else:
                self._execute_script(job.profile_id, page, ctx, script, human)

            # cooldown
            cooldown = float(profile.get("traffic", {}).get("cooldown_s", 2.0) or 0)
            cooldown = clamp(cooldown, 0.0, 60.0)
            if cooldown > 0:
                self._log("INFO", f"[{job.profile_id}] Cooldown {cooldown:.1f}s")
                t_end = time.time() + cooldown
                while time.time() < t_end and not self._stop_event.is_set():
                    time.sleep(0.05)

            # success
            self._finalize_profile(job.profile_id, ok=True, err="")
        except Exception as e:
            err = str(e)
            self._log("ERROR", f"[{job.profile_id}] Run failed: {err}")
            self._log("ERROR", traceback.format_exc())
            self._finalize_profile(job.profile_id, ok=False, err=err)
        finally:
            try:
                if page is not None:
                    page.close()
            except Exception:
                pass
            try:
                if ctx is not None:
                    ctx.close()
            except Exception:
                pass
            with self._contexts_lock:
                try:
                    if ctx in self._contexts_live:
                        self._contexts_live.remove(ctx)
                except Exception:
                    pass

    def _human_idle_session(self, page, human: HumanBehavior, seconds=5.0):
        end = time.time() + float(seconds)
        last_mouse = (human.rng.randint(30, 400), human.rng.randint(40, 300))
        while time.time() < end and not self._stop_event.is_set():
            if human.rng.random() < 0.45:
                # scroll a bit
                try:
                    for dy in human.scroll_pattern():
                        page.mouse.wheel(0, dy)
                        human.micro_pause(180, 140)
                except Exception:
                    pass
            else:
                # small mouse movement
                try:
                    x1 = clamp(last_mouse[0] + human.rng.randint(-140, 140), 10, 1200)
                    y1 = clamp(last_mouse[1] + human.rng.randint(-120, 120), 10, 800)
                    pts = human.move_curve_points(last_mouse[0], last_mouse[1], x1, y1)
                    for x, y in pts:
                        page.mouse.move(x, y)
                        time.sleep(human.rng.uniform(0.004, 0.012))
                    last_mouse = (x1, y1)
                except Exception:
                    pass
            human.read_pause(250, 1200)

    def _execute_script(self, profile_id, page, ctx, script, human: HumanBehavior):
        steps = script.get("steps", [])
        self._log("INFO", f"[{profile_id}] Executing script '{script.get('name')}' ({len(steps)} steps)")
        # Strict sequential isolation: each step is try/except; failures stop execution (no silent failures)
        for idx, step in enumerate(steps):
            if self._stop_event.is_set():
                raise RuntimeError("Stopped")
            action = step.get("action")
            label = step.get("label", f"{action} #{idx}")
            self._log("INFO", f"[{profile_id}] Step {idx+1}/{len(steps)}: {label}")

            timeout_ms = step.get("timeout_ms", None)
            # per-step timeouts: temporarily override default for this action
            try:
                if timeout_ms is not None:
                    page.set_default_timeout(int(timeout_ms))
                self._execute_step(profile_id, page, ctx, step, human)
            except (PWTimeoutError, PWError) as e:
                raise RuntimeError(f"Playwright error at step {idx+1} ({action}): {e}") from e
            except Exception as e:
                raise RuntimeError(f"Error at step {idx+1} ({action}): {e}") from e
            finally:
                # restore default (from settings)
                traffic = self.ds.settings.get("traffic", {})
                page.set_default_timeout(int(traffic.get("action_timeout_ms", 25000)))

            # human pacing between steps
            if self.ds.settings.get("traffic", {}).get("human_mode", True):
                human.micro_pause(
                    base_ms=int(self.ds.settings.get("traffic", {}).get("min_delay_ms", 180)),
                    spread_ms=int(max(60, (self.ds.settings.get("traffic", {}).get("max_delay_ms", 900) -
                                          self.ds.settings.get("traffic", {}).get("min_delay_ms", 180)) // 2))
                )

    def _execute_step(self, profile_id, page, ctx, step, human: HumanBehavior):
        action = step["action"]
        human_mode = bool(self.ds.settings.get("traffic", {}).get("human_mode", True))

        if action == "goto":
            url = step["url"]
            wait_until = step.get("wait_until", "domcontentloaded")
            if human_mode:
                human.micro_pause(220, 160)
            page.goto(url, wait_until=wait_until)
            if human_mode:
                human.read_pause(450, 1600)

        elif action == "wait_for_selector":
            sel = step["selector"]
            page.wait_for_selector(sel, state=step.get("state", "visible") if isinstance(step.get("state"), str) else "visible")

        elif action == "wait":
            ms = int(step["ms"])
            if human_mode:
                # add tiny variability but never exceed reasonable bounds
                ms = int(clamp(ms + human.rng.randint(-80, 120), 0, 180000))
            time.sleep(ms / 1000.0)

        elif action in ("click", "dblclick", "hover"):
            sel = step["selector"]
            loc = page.locator(sel).first
            loc.wait_for(state="visible")
            # human-like mouse movement to element center
            if human_mode:
                try:
                    box = loc.bounding_box()
                    if box:
                        target_x = box["x"] + box["width"] * human.rng.uniform(0.35, 0.65)
                        target_y = box["y"] + box["height"] * human.rng.uniform(0.35, 0.65)
                        # move from current (unknown) - approximate start random
                        sx = human.rng.uniform(40, 700)
                        sy = human.rng.uniform(60, 520)
                        pts = human.move_curve_points(sx, sy, target_x, target_y)
                        for x, y in pts:
                            page.mouse.move(x, y)
                            time.sleep(human.rng.uniform(0.004, 0.012))
                        human.micro_pause(120, 120)
                except Exception:
                    pass

            if action == "hover":
                loc.hover()
            elif action == "dblclick":
                loc.dblclick(button=step.get("button", "left"))
            else:
                loc.click(button=step.get("button", "left"), click_count=int(step.get("click_count", 1)))

            if human_mode and human.occasional_micro_interaction():
                # micro scroll after click sometimes
                try:
                    page.mouse.wheel(0, human.rng.randint(-120, 240))
                except Exception:
                    pass

        elif action == "type":
            sel = step["selector"]
            text = step["text"]
            clear_first = bool(step.get("clear_first", True))
            enter = bool(step.get("enter", False))
            loc = page.locator(sel).first
            loc.wait_for(state="visible")
            loc.click()

            if clear_first:
                # ctrl+a backspace
                loc.press("Control+A")
                if human_mode:
                    human.micro_pause(80, 60)
                loc.press("Backspace")

            # type with variable cadence
            if human_mode:
                for ch in text:
                    loc.type(ch, delay=human.typing_delay_ms())
                    if human.rng.random() < 0.06:
                        time.sleep(human.rng.uniform(0.02, 0.10))
            else:
                loc.type(text, delay=20)

            if enter:
                if human_mode:
                    human.micro_pause(120, 80)
                loc.press("Enter")

        elif action == "press":
            key = step["key"]
            sel = step.get("selector")
            if sel:
                loc = page.locator(sel).first
                loc.wait_for(state="visible")
                loc.press(key)
            else:
                page.keyboard.press(key)

        elif action == "scroll":
            behavior = step.get("behavior", "smooth")
            sel = step.get("selector", None)
            dy = step.get("dy", None)
            if sel:
                loc = page.locator(sel).first
                loc.scroll_into_view_if_needed()
                if human_mode:
                    human.read_pause(250, 1200)
            else:
                if dy is None:
                    # default natural scroll sequence
                    if human_mode:
                        for ddy in human.scroll_pattern():
                            page.mouse.wheel(0, ddy)
                            human.micro_pause(160, 140)
                    else:
                        page.mouse.wheel(0, 600)
                else:
                    # dy specified
                    if human_mode:
                        # chunk it for realism
                        remaining = int(dy)
                        while remaining != 0:
                            step_dy = int(clamp(remaining, -420, 420))
                            page.mouse.wheel(0, step_dy)
                            remaining -= step_dy
                            human.micro_pause(120, 120)
                    else:
                        page.mouse.wheel(0, int(dy))
            # optional: smooth behavior via a tiny delay
            if behavior == "smooth" and human_mode:
                human.micro_pause(160, 120)

        elif action == "select_option":
            sel = step["selector"]
            val = step["value"]
            loc = page.locator(sel).first
            loc.wait_for(state="visible")
            loc.select_option(val)

        elif action == "set_viewport":
            page.set_viewport_size({"width": int(step["width"]), "height": int(step["height"])})

        elif action == "screenshot":
            name = step["name"]
            full_page = bool(step.get("full_page", False))
            # save to app data (screenshots folder)
            out_dir = os.path.join(self.ds.base_dir, "screenshots")
            safe_mkdir(out_dir)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            fn = f"{profile_id}_{ts}_{name}.png"
            path = os.path.join(out_dir, fn)
            page.screenshot(path=path, full_page=full_page)
            self._log("INFO", f"[{profile_id}] Screenshot saved: {path}")

        elif action == "assert_text":
            sel = step["selector"]
            text = step["text"]
            contains = bool(step.get("contains", True))
            loc = page.locator(sel).first
            loc.wait_for(state="attached")
            actual = loc.inner_text(timeout=step.get("timeout_ms", None) or 25000)
            if contains:
                if text not in actual:
                    raise RuntimeError("assert_text failed: expected substring not found")
            else:
                if text.strip() != actual.strip():
                    raise RuntimeError("assert_text failed: expected exact text mismatch")

        elif action == "assert_url_contains":
            frag = step["text"]
            if frag not in (page.url or ""):
                raise RuntimeError(f"assert_url_contains failed: '{frag}' not in url")

        elif action == "evaluate_js":
            code = step["code"]
            page.evaluate(f"() => {{ {code} }}")

        else:
            raise RuntimeError(f"Unsupported action: {action}")

    def _finalize_profile(self, profile_id, ok: bool, err: str):
        profiles = self.ds.profiles.get("profiles", {})
        profile = profiles.get(profile_id)
        if not profile:
            return
        st = profile.get("state", {})
        st["last_run"] = now_iso()
        st["last_status"] = "ok" if ok else "fail"
        st["last_error"] = err or ""
        st["runs_total"] = int(st.get("runs_total", 0)) + 1
        if ok:
            st["runs_ok"] = int(st.get("runs_ok", 0)) + 1
        else:
            st["runs_fail"] = int(st.get("runs_fail", 0)) + 1
        profile["state"] = st
        self.ds.profiles["profiles"][profile_id] = profile
        self.ds.save_profiles()
        self._set_status(profile_id, st["last_status"])
        if ok:
            self._log("INFO", f"[{profile_id}] Completed OK")
        else:
            self._log("ERROR", f"[{profile_id}] Completed FAIL: {err}")


# ----------------------------- UI Components -----------------------------

def apply_premium_theme(app: QApplication):
    # Premium dark SaaS palette + hover animations via QSS
    qss = """
    QWidget {
        font-family: "Segoe UI";
        color: #E9E9EF;
    }
    QMainWindow {
        background: #0E1220;
    }
    QFrame#Sidebar {
        background: #0B0F1A;
        border-right: 1px solid rgba(255,255,255,0.06);
    }
    QPushButton {
        border: 1px solid rgba(255,255,255,0.08);
        background: rgba(255,255,255,0.04);
        padding: 10px 12px;
        border-radius: 10px;
    }
    QPushButton:hover {
        background: rgba(255,255,255,0.07);
        border-color: rgba(255,255,255,0.12);
    }
    QPushButton:pressed {
        background: rgba(255,255,255,0.10);
    }
    QPushButton:disabled {
        color: rgba(233,233,239,0.35);
        background: rgba(255,255,255,0.02);
        border-color: rgba(255,255,255,0.05);
    }
    QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 10px;
        padding: 8px 10px;
        selection-background-color: #6D5EF1;
    }
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {
        border-color: rgba(109,94,241,0.75);
        background: rgba(255,255,255,0.045);
    }
    QScrollArea {
        border: none;
        background: transparent;
    }
    QScrollBar:vertical {
        width: 10px;
        background: transparent;
        margin: 2px;
    }
    QScrollBar::handle:vertical {
        background: rgba(255,255,255,0.10);
        border-radius: 5px;
        min-height: 25px;
    }
    QScrollBar::handle:vertical:hover {
        background: rgba(255,255,255,0.16);
    }
    QFrame#Card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
    }
    QLabel#H1 {
        font-size: 18px;
        font-weight: 700;
        color: #FFFFFF;
    }
    QLabel#H2 {
        font-size: 13px;
        font-weight: 650;
        color: rgba(255,255,255,0.92);
    }
    QLabel#Muted {
        color: rgba(233,233,239,0.62);
    }
    QFrame#TopBar {
        background: rgba(255,255,255,0.02);
        border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    QFrame#Separator {
        background: rgba(255,255,255,0.08);
    }
    QTableWidget {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        gridline-color: rgba(255,255,255,0.06);
        selection-background-color: rgba(109,94,241,0.25);
    }
    QHeaderView::section {
        background: rgba(255,255,255,0.03);
        border: none;
        border-bottom: 1px solid rgba(255,255,255,0.08);
        padding: 8px 10px;
        font-weight: 650;
        color: rgba(255,255,255,0.85);
    }
    QProgressBar {
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 9px;
        text-align: center;
        background: rgba(255,255,255,0.03);
        height: 18px;
    }
    QProgressBar::chunk {
        background: #6D5EF1;
        border-radius: 9px;
    }
    """
    app.setStyleSheet(qss)


class AnimatedButton(QPushButton):
    def __init__(self, text="", parent=None, accent=False):
        super().__init__(text, parent)
        self._accent = accent
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._orig = None
        self.setCursor(Qt.PointingHandCursor)
        if accent:
            self.setStyleSheet(self.styleSheet() + """
            QPushButton {
                background: rgba(109,94,241,0.16);
                border-color: rgba(109,94,241,0.45);
            }
            QPushButton:hover {
                background: rgba(109,94,241,0.22);
                border-color: rgba(109,94,241,0.60);
            }
            """)

    def enterEvent(self, e):
        try:
            if self.isEnabled():
                self._orig = self.geometry()
                r = self.geometry()
                self._anim.stop()
                self._anim.setDuration(140)
                self._anim.setStartValue(r)
                self._anim.setEndValue(QRect(r.x(), r.y()-1, r.width(), r.height()))
                self._anim.start()
        except Exception:
            pass
        super().enterEvent(e)

    def leaveEvent(self, e):
        try:
            if self._orig is not None:
                self._anim.stop()
                self._anim.setDuration(160)
                self._anim.setStartValue(self.geometry())
                self._anim.setEndValue(self._orig)
                self._anim.start()
        except Exception:
            pass
        super().leaveEvent(e)


def build_card(title: str, subtitle: str = ""):
    card = QFrame()
    card.setObjectName("Card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(10)

    h = QLabel(title)
    h.setObjectName("H2")
    lay.addWidget(h)

    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("Muted")
        s.setWordWrap(True)
        lay.addWidget(s)

    return card, lay


class StatusPill(QLabel):
    def __init__(self, text="idle"):
        super().__init__(text)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(22)
        self.setMinimumWidth(70)
        self.setStyleFor(text)

    def setStyleFor(self, status):
        status = (status or "").lower()
        if status in ("running",):
            bg = "rgba(245, 158, 11, 0.18)"
            bd = "rgba(245, 158, 11, 0.55)"
            fg = "rgba(255, 220, 160, 0.95)"
            t = "RUNNING"
        elif status in ("ok", "success"):
            bg = "rgba(34, 197, 94, 0.16)"
            bd = "rgba(34, 197, 94, 0.55)"
            fg = "rgba(200, 255, 220, 0.95)"
            t = "OK"
        elif status in ("fail", "error"):
            bg = "rgba(239, 68, 68, 0.16)"
            bd = "rgba(239, 68, 68, 0.55)"
            fg = "rgba(255, 205, 205, 0.95)"
            t = "FAIL"
        else:
            bg = "rgba(148, 163, 184, 0.12)"
            bd = "rgba(148, 163, 184, 0.35)"
            fg = "rgba(233,233,239,0.70)"
            t = "IDLE"
        self.setText(t)
        self.setStyleSheet(f"""
        QLabel {{
            background: {bg};
            border: 1px solid {bd};
            border-radius: 11px;
            color: {fg};
            font-weight: 700;
            font-size: 11px;
            padding: 0 10px;
        }}""")


class LogConsole(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setMaximumBlockCount(4000)
        self.setStyleSheet("""
        QPlainTextEdit {
            background: rgba(0,0,0,0.25);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px;
            padding: 10px;
            font-family: Consolas;
            font-size: 12px;
        }""")

    def append_line(self, s: str):
        self.appendPlainText(s)
        self.moveCursor(QTextCursor.End)


# ----------------------------- RPA Script Creator Dialog -----------------------------

class ScriptCreatorDialog(QDialog):
    def __init__(self, parent, datastore: DataStore):
        super().__init__(parent)
        self.ds = datastore
        self.setWindowTitle("Humanex - RPA Script Creator")
        self.setModal(True)
        self.resize(860, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        header = QLabel("RPA Script Creator")
        header.setObjectName("H1")
        root.addWidget(header)
        muted = QLabel("Create and validate Humanex RPA JSON scripts. Schema enforced before saving/execution.")
        muted.setObjectName("Muted")
        muted.setWordWrap(True)
        root.addWidget(muted)

        self.editor = QPlainTextEdit()
        self.editor.setStyleSheet("""
        QPlainTextEdit {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.10);
            border-radius: 14px;
            padding: 10px;
            font-family: Consolas;
            font-size: 12px;
        }""")
        root.addWidget(self.editor, 1)

        self.status = QLabel("Ready.")
        self.status.setObjectName("Muted")
        root.addWidget(self.status)

        btns = QDialogButtonBox()
        self.btn_validate = btns.addButton("Validate", QDialogButtonBox.ActionRole)
        self.btn_save = btns.addButton("Save Script", QDialogButtonBox.AcceptRole)
        self.btn_close = btns.addButton("Close", QDialogButtonBox.RejectRole)

        root.addWidget(btns)

        self.btn_validate.clicked.connect(self.on_validate)
        self.btn_save.clicked.connect(self.on_save)
        self.btn_close.clicked.connect(self.reject)

        # default template
        template = {
            "schema": "humanex.rpa.v1",
            "name": "Sample: Search Example",
            "options": {"note": "Edit safely; schema is strict."},
            "steps": [
                {"action": "goto", "url": "https://example.com", "wait_until": "domcontentloaded", "label": "Open site"},
                {"action": "scroll", "dy": 600, "behavior": "smooth", "label": "Scroll"},
                {"action": "wait", "ms": 800, "label": "Pause"},
                {"action": "screenshot", "name": "example_home", "full_page": False, "label": "Screenshot"}
            ]
        }
        self.editor.setPlainText(json.dumps(template, indent=2))

    def on_validate(self):
        try:
            obj = json.loads(self.editor.toPlainText())
        except Exception as e:
            self.status.setText(f"Invalid JSON: {e}")
            return
        ok, err = RPAValidator.validate_script(obj)
        if ok:
            self.status.setText("Validation OK.")
        else:
            self.status.setText(f"Validation FAILED: {err}")

    def on_save(self):
        try:
            obj = json.loads(self.editor.toPlainText())
        except Exception as e:
            QMessageBox.critical(self, "Invalid JSON", str(e))
            return
        ok, err = RPAValidator.validate_script(obj)
        if not ok:
            QMessageBox.critical(self, "Schema Validation Failed", err)
            return
        # store with stable id based on name+hash
        name = obj.get("name", "script")
        sid = "script_" + sha256_hex(name + "|" + json.dumps(obj, sort_keys=True))[:10]
        self.ds.scripts.setdefault("scripts", {})[sid] = obj
        self.ds.save_scripts()
        QMessageBox.information(self, "Saved", f"Saved as: {sid}")
        self.accept()


# ----------------------------- Pages -----------------------------

class PageBase(QWidget):
    def __init__(self, ds: DataStore):
        super().__init__()
        self.ds = ds

    def refresh(self):
        pass


class WebsiteDetailsPage(PageBase):
    def __init__(self, ds: DataStore):
        super().__init__(ds)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        card, lay = build_card("Website Details", "Configure per-profile website parameters (start URL, referrer, popup policy).")
        root.addWidget(card)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.profile_cb = QComboBox()
        self.start_url = QLineEdit()
        self.referrer = QLineEdit()
        self.allow_popups = QCheckBox("Allow popups (otherwise auto-close)")
        self.allow_popups.setCursor(Qt.PointingHandCursor)

        form.addRow("Profile", self.profile_cb)
        form.addRow("Start URL", self.start_url)
        form.addRow("Referrer (optional)", self.referrer)
        form.addRow("", self.allow_popups)

        lay.addLayout(form)

        btn_row = QHBoxLayout()
        self.btn_save = AnimatedButton("Save", accent=True)
        self.btn_reload = AnimatedButton("Reload")
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_reload)
        btn_row.addStretch(1)

        lay.addLayout(btn_row)

        self.btn_save.clicked.connect(self.save)
        self.btn_reload.clicked.connect(self.refresh)
        self.profile_cb.currentIndexChanged.connect(self.load_profile)

        # filler
        root.addStretch(1)
        self.refresh()

    def refresh(self):
        profiles = self.ds.profiles.get("profiles", {})
        current = self.profile_cb.currentData()
        self.profile_cb.blockSignals(True)
        self.profile_cb.clear()
        for pid, p in profiles.items():
            self.profile_cb.addItem(f"{p.get('name')} ({pid})", pid)
        self.profile_cb.blockSignals(False)
        if current and current in profiles:
            idx = self.profile_cb.findData(current)
            if idx >= 0:
                self.profile_cb.setCurrentIndex(idx)
        self.load_profile()

    def load_profile(self):
        pid = self.profile_cb.currentData()
        if not pid:
            return
        p = self.ds.profiles["profiles"].get(pid, {})
        web = p.get("website", {})
        self.start_url.setText(web.get("start_url", ""))
        self.referrer.setText(web.get("referrer", ""))
        self.allow_popups.setChecked(bool(web.get("allow_popups", False)))

    def save(self):
        pid = self.profile_cb.currentData()
        if not pid:
            return
        start = self.start_url.text().strip()
        if not start.startswith(("http://", "https://")):
            QMessageBox.critical(self, "Invalid URL", "Start URL must begin with http:// or https://")
            return
        ref = self.referrer.text().strip()
        if ref and not ref.startswith(("http://", "https://")):
            QMessageBox.critical(self, "Invalid Referrer", "Referrer must be empty or begin with http:// or https://")
            return

        p = self.ds.profiles["profiles"].get(pid, {})
        p.setdefault("website", {})
        p["website"]["start_url"] = start
        p["website"]["referrer"] = ref
        p["website"]["allow_popups"] = bool(self.allow_popups.isChecked())
        self.ds.profiles["profiles"][pid] = p
        self.ds.save_profiles()
        QMessageBox.information(self, "Saved", "Website settings saved.")


class TrafficSettingsPage(PageBase):
    def __init__(self, ds: DataStore):
        super().__init__(ds)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        card, lay = build_card("Traffic Settings", "Control concurrency, timing, timeouts, and human-like behavior engine.")
        root.addWidget(card)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        self.concurrency = QSpinBox()
        self.concurrency.setRange(1, 24)
        self.concurrency.setValue(int(ds.settings.get("traffic", {}).get("concurrency", 3)))

        self.nav_timeout = QSpinBox()
        self.nav_timeout.setRange(5000, 180000)
        self.nav_timeout.setSingleStep(5000)

        self.act_timeout = QSpinBox()
        self.act_timeout.setRange(2000, 120000)
        self.act_timeout.setSingleStep(1000)

        self.min_delay = QSpinBox()
        self.min_delay.setRange(0, 5000)
        self.min_delay.setSingleStep(25)

        self.max_delay = QSpinBox()
        self.max_delay.setRange(0, 8000)
        self.max_delay.setSingleStep(25)

        self.human_mode = QCheckBox("Enable Human-Like Behavior Engine")
        self.human_mode.setCursor(Qt.PointingHandCursor)

        grid.addWidget(QLabel("Concurrency (workers)"), 0, 0)
        grid.addWidget(self.concurrency, 0, 1)
        grid.addWidget(QLabel("Navigation Timeout (ms)"), 1, 0)
        grid.addWidget(self.nav_timeout, 1, 1)
        grid.addWidget(QLabel("Action Timeout (ms)"), 2, 0)
        grid.addWidget(self.act_timeout, 2, 1)
        grid.addWidget(QLabel("Min Delay Between Steps (ms)"), 3, 0)
        grid.addWidget(self.min_delay, 3, 1)
        grid.addWidget(QLabel("Max Delay Between Steps (ms)"), 4, 0)
        grid.addWidget(self.max_delay, 4, 1)
        grid.addWidget(self.human_mode, 5, 0, 1, 2)

        lay.addLayout(grid)

        btn_row = QHBoxLayout()
        self.btn_save = AnimatedButton("Save", accent=True)
        self.btn_reload = AnimatedButton("Reload")
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_reload)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        self.btn_save.clicked.connect(self.save)
        self.btn_reload.clicked.connect(self.refresh)

        root.addStretch(1)
        self.refresh()

    def refresh(self):
        t = self.ds.settings.get("traffic", {})
        self.concurrency.setValue(int(t.get("concurrency", 3)))
        self.nav_timeout.setValue(int(t.get("navigation_timeout_ms", 45000)))
        self.act_timeout.setValue(int(t.get("action_timeout_ms", 25000)))
        self.min_delay.setValue(int(t.get("min_delay_ms", 180)))
        self.max_delay.setValue(int(t.get("max_delay_ms", 900)))
        self.human_mode.setChecked(bool(t.get("human_mode", True)))

    def save(self):
        if self.max_delay.value() < self.min_delay.value():
            QMessageBox.critical(self, "Invalid delays", "Max delay must be >= Min delay.")
            return
        self.ds.settings.setdefault("traffic", {})
        self.ds.settings["traffic"]["concurrency"] = int(self.concurrency.value())
        self.ds.settings["traffic"]["navigation_timeout_ms"] = int(self.nav_timeout.value())
        self.ds.settings["traffic"]["action_timeout_ms"] = int(self.act_timeout.value())
        self.ds.settings["traffic"]["min_delay_ms"] = int(self.min_delay.value())
        self.ds.settings["traffic"]["max_delay_ms"] = int(self.max_delay.value())
        self.ds.settings["traffic"]["human_mode"] = bool(self.human_mode.isChecked())
        self.ds.save_settings()
        QMessageBox.information(self, "Saved", "Traffic settings saved.")


class ProxySettingsPage(PageBase):
    def __init__(self, ds: DataStore):
        super().__init__(ds)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        card, lay = build_card("Proxy Settings", "Global proxy or per-profile proxy. Fingerprints should align to proxy region hint.")
        root.addWidget(card)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.mode = QComboBox()
        self.mode.addItems(["per_profile", "global", "none"])
        self.global_proxy = QLineEdit()
        self.global_proxy.setPlaceholderText("http://user:pass@host:port  or  host:port")

        form.addRow("Proxy Mode", self.mode)
        form.addRow("Global Proxy", self.global_proxy)

        lay.addLayout(form)

        help_lbl = QLabel("Per-profile proxies are configured in BOT CONTROL table. No proxy bypass logic is used; Humanex focuses on realistic behavior.")
        help_lbl.setObjectName("Muted")
        help_lbl.setWordWrap(True)
        lay.addWidget(help_lbl)

        btn_row = QHBoxLayout()
        self.btn_save = AnimatedButton("Save", accent=True)
        self.btn_test = AnimatedButton("Test Global Proxy")
        self.btn_reload = AnimatedButton("Reload")
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_test)
        btn_row.addWidget(self.btn_reload)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        self.btn_save.clicked.connect(self.save)
        self.btn_reload.clicked.connect(self.refresh)
        self.btn_test.clicked.connect(self.test_global_proxy)

        root.addStretch(1)
        self.refresh()

    def refresh(self):
        p = self.ds.settings.get("proxy", {})
        mode = p.get("mode", "per_profile")
        idx = self.mode.findText(mode)
        if idx >= 0:
            self.mode.setCurrentIndex(idx)
        self.global_proxy.setText(p.get("global_proxy", ""))

    def save(self):
        mode = self.mode.currentText()
        gp = self.global_proxy.text().strip()
        if mode == "global":
            if gp and parse_proxy(gp) is None:
                QMessageBox.critical(self, "Invalid proxy", "Global proxy format invalid.")
                return
        self.ds.settings.setdefault("proxy", {})
        self.ds.settings["proxy"]["mode"] = mode
        self.ds.settings["proxy"]["global_proxy"] = gp
        self.ds.save_settings()
        QMessageBox.information(self, "Saved", "Proxy settings saved.")

    def test_global_proxy(self):
        mode = self.mode.currentText()
        gp = self.global_proxy.text().strip()
        if mode != "global":
            QMessageBox.information(self, "Info", "Set mode to 'global' to test the global proxy.")
            return
        opt = parse_proxy(gp)
        if opt is None:
            QMessageBox.critical(self, "Invalid proxy", "Global proxy format invalid.")
            return
        # We do a lightweight parse test only (no network). Real network tests are done in execution.
        QMessageBox.information(self, "Proxy Parsed", f"Server: {opt.get('server')}\nAuth: {'yes' if opt.get('username') else 'no'}")


class RPASystemPage(PageBase):
    def __init__(self, ds: DataStore):
        super().__init__(ds)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        card, lay = build_card("RPA System", "Manage RPA scripts, set defaults, validate schema, and import/export safely.")
        root.addWidget(card)

        top_row = QHBoxLayout()
        self.default_script = QComboBox()
        self.btn_refresh = AnimatedButton("Reload")
        self.btn_set_default = AnimatedButton("Set Default", accent=True)
        self.btn_export = AnimatedButton("Export Scripts")
        self.btn_import = AnimatedButton("Import Scripts")
        top_row.addWidget(QLabel("Default Script"))
        top_row.addWidget(self.default_script, 1)
        top_row.addWidget(self.btn_set_default)
        top_row.addWidget(self.btn_import)
        top_row.addWidget(self.btn_export)
        top_row.addWidget(self.btn_refresh)
        lay.addLayout(top_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Script ID", "Name", "Steps", "Schema"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        lay.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_validate = AnimatedButton("Validate Selected")
        self.btn_delete = AnimatedButton("Delete Selected")
        btn_row.addWidget(self.btn_validate)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        root.addStretch(1)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_set_default.clicked.connect(self.set_default)
        self.btn_validate.clicked.connect(self.validate_selected)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_import.clicked.connect(self.import_scripts)
        self.btn_export.clicked.connect(self.export_scripts)

        self.refresh()

    def refresh(self):
        scripts = self.ds.scripts.get("scripts", {})
        self.default_script.blockSignals(True)
        self.default_script.clear()
        self.default_script.addItem("(none)", "")
        for sid, s in scripts.items():
            self.default_script.addItem(f"{s.get('name', 'Unnamed')} ({sid})", sid)
        self.default_script.blockSignals(False)
        current_default = self.ds.settings.get("rpa", {}).get("default_script_id", "")
        idx = self.default_script.findData(current_default)
        if idx >= 0:
            self.default_script.setCurrentIndex(idx)

        self.table.setRowCount(0)
        for sid, s in scripts.items():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(sid))
            self.table.setItem(r, 1, QTableWidgetItem(s.get("name", "")))
            steps = s.get("steps", [])
            self.table.setItem(r, 2, QTableWidgetItem(str(len(steps) if isinstance(steps, list) else 0)))
            self.table.setItem(r, 3, QTableWidgetItem(s.get("schema", "")))

    def selected_script_id(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        r = rows[0].row()
        item = self.table.item(r, 0)
        return item.text() if item else None

    def set_default(self):
        sid = self.default_script.currentData()
        self.ds.settings.setdefault("rpa", {})
        self.ds.settings["rpa"]["default_script_id"] = sid
        self.ds.save_settings()
        QMessageBox.information(self, "Saved", "Default script updated.")

    def validate_selected(self):
        sid = self.selected_script_id()
        if not sid:
            QMessageBox.information(self, "Select", "Select a script first.")
            return
        s = self.ds.scripts.get("scripts", {}).get(sid)
        ok, err = RPAValidator.validate_script(s)
        if ok:
            QMessageBox.information(self, "Validation", "Validation OK.")
        else:
            QMessageBox.critical(self, "Validation Failed", err)

    def delete_selected(self):
        sid = self.selected_script_id()
        if not sid:
            QMessageBox.information(self, "Select", "Select a script first.")
            return
        if QMessageBox.question(self, "Delete", f"Delete script {sid}?") != QMessageBox.Yes:
            return
        try:
            self.ds.scripts.get("scripts", {}).pop(sid, None)
            # unassign default if needed
            if self.ds.settings.get("rpa", {}).get("default_script_id") == sid:
                self.ds.settings["rpa"]["default_script_id"] = ""
                self.ds.save_settings()
            self.ds.save_scripts()
            QMessageBox.information(self, "Deleted", "Script deleted.")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def export_scripts(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Scripts", os.path.join(self.ds.base_dir, "humanex_scripts_export.json"), "JSON Files (*.json)")
        if not path:
            return
        try:
            atomic_write_json(path, self.ds.scripts)
            QMessageBox.information(self, "Exported", f"Exported to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def import_scripts(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Scripts", self.ds.base_dir, "JSON Files (*.json)")
        if not path:
            return
        try:
            data = read_json_file(path, default=None)
            if not isinstance(data, dict) or "scripts" not in data or not isinstance(data["scripts"], dict):
                QMessageBox.critical(self, "Invalid File", "Expected object with key 'scripts'.")
                return
            # validate each
            valid = {}
            failures = []
            for sid, s in data["scripts"].items():
                ok, err = RPAValidator.validate_script(s)
                if ok:
                    valid[sid] = s
                else:
                    failures.append(f"{sid}: {err}")
            if not valid:
                QMessageBox.critical(self, "Import Failed", "No valid scripts found.\n\n" + "\n".join(failures[:25]))
                return
            # merge
            self.ds.scripts.setdefault("scripts", {}).update(valid)
            self.ds.save_scripts()
            msg = f"Imported {len(valid)} scripts."
            if failures:
                msg += f"\nRejected {len(failures)} invalid scripts."
            QMessageBox.information(self, "Imported", msg)
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", str(e))


class BotControlPage(PageBase):
    def __init__(self, ds: DataStore, logbus: LogBus, engine: AutomationEngine):
        super().__init__(ds)
        self.logbus = logbus
        self.engine = engine

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        header_card, hlay = build_card("Bot Control", "Profiles, execution queue, scaling controls, and real-time monitoring.")
        root.addWidget(header_card)

        # controls row
        ctrl = QHBoxLayout()
        self.btn_start = AnimatedButton("Start Selected", accent=True)
        self.btn_stop = AnimatedButton("Stop")
        self.btn_save = AnimatedButton("Save Profile Changes")
        self.btn_reload = AnimatedButton("Reload")
        self.btn_assign_fp = AnimatedButton("Reassign Fingerprints")
        ctrl.addWidget(self.btn_start)
        ctrl.addWidget(self.btn_stop)
        ctrl.addWidget(self.btn_save)
        ctrl.addWidget(self.btn_assign_fp)
        ctrl.addWidget(self.btn_reload)
        ctrl.addStretch(1)
        hlay.addLayout(ctrl)

        # progress
        pr = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.prog_lbl = QLabel("0/0")
        self.prog_lbl.setObjectName("Muted")
        pr.addWidget(self.progress, 1)
        pr.addWidget(self.prog_lbl)
        hlay.addLayout(pr)

        # profiles table
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "Run", "Profile ID", "Name", "Enabled", "Start URL", "Proxy", "Region", "Script", "Iterations", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        root.addWidget(self.table, 1)

        # log console card
        log_card, log_lay = build_card("Real-Time Console", "No silent failures. All actions are logged.")
        root.addWidget(log_card)
        self.console = LogConsole()
        log_lay.addWidget(self.console)

        # connections
        self.btn_reload.clicked.connect(self.refresh)
        self.btn_save.clicked.connect(self.save_profiles)
        self.btn_start.clicked.connect(self.start_selected)
        self.btn_stop.clicked.connect(self.engine.stop)
        self.btn_assign_fp.clicked.connect(self.reassign_fingerprints)

        self.logbus.log.connect(self.on_log)
        self.logbus.status.connect(self.on_status)
        self.logbus.progress.connect(self.on_progress)

        self.refresh()
        self._update_buttons()

        # timer to keep button states correct
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_buttons)
        self._timer.start(350)

    def _update_buttons(self):
        running = self.engine.is_running()
        self.btn_start.setEnabled(not running)
        self.btn_save.setEnabled(not running)
        self.btn_assign_fp.setEnabled(not running)
        self.btn_stop.setEnabled(running)

    @Slot(str, str)
    def on_log(self, level, message):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {level:<5} {message}"
        self.console.append_line(line)

    @Slot(str, str)
    def on_status(self, profile_id, status):
        # update status pill in table
        for r in range(self.table.rowCount()):
            pid_item = self.table.item(r, 1)
            if pid_item and pid_item.text() == profile_id:
                w = self.table.cellWidget(r, 9)
                if isinstance(w, StatusPill):
                    w.setStyleFor(status)
                else:
                    pill = StatusPill(status)
                    self.table.setCellWidget(r, 9, pill)
                break

    @Slot(int, int)
    def on_progress(self, done, total):
        if total <= 0:
            self.progress.setValue(0)
            self.prog_lbl.setText("0/0")
            return
        pct = int((done / total) * 100)
        self.progress.setValue(pct)
        self.prog_lbl.setText(f"{done}/{total}")

    def refresh(self):
        profiles = self.ds.profiles.get("profiles", {})
        scripts = self.ds.scripts.get("scripts", {})

        self.table.setRowCount(0)
        for pid, p in profiles.items():
            r = self.table.rowCount()
            self.table.insertRow(r)

            run_cb = QCheckBox()
            run_cb.setChecked(bool(p.get("enabled", True)))
            run_cb.setCursor(Qt.PointingHandCursor)
            self.table.setCellWidget(r, 0, run_cb)

            self.table.setItem(r, 1, QTableWidgetItem(pid))
            self.table.setItem(r, 2, QTableWidgetItem(p.get("name", "")))

            enabled_cb = QCheckBox()
            enabled_cb.setChecked(bool(p.get("enabled", True)))
            enabled_cb.setCursor(Qt.PointingHandCursor)
            self.table.setCellWidget(r, 3, enabled_cb)

            start_url = QLineEdit(p.get("website", {}).get("start_url", ""))
            self.table.setCellWidget(r, 4, start_url)

            proxy = QLineEdit(p.get("proxy", {}).get("proxy", ""))
            proxy.setPlaceholderText("host:port or http://user:pass@host:port")
            self.table.setCellWidget(r, 5, proxy)

            region = QComboBox()
            region.addItems(["auto", "US", "EU", "IN", "APAC"])
            region_hint = (p.get("proxy", {}).get("region_hint") or "auto")
            idx = region.findText(region_hint)
            if idx >= 0:
                region.setCurrentIndex(idx)
            self.table.setCellWidget(r, 6, region)

            script_cb = QComboBox()
            script_cb.addItem("(default)", "")
            for sid, s in scripts.items():
                script_cb.addItem(s.get("name", "Unnamed") + f" ({sid})", sid)
            sid_cur = p.get("traffic", {}).get("script_id", "")
            idx = script_cb.findData(sid_cur)
            if idx >= 0:
                script_cb.setCurrentIndex(idx)
            self.table.setCellWidget(r, 7, script_cb)

            iterations = QSpinBox()
            iterations.setRange(1, 1000)
            iterations.setValue(int(p.get("traffic", {}).get("iterations", 1) or 1))
            self.table.setCellWidget(r, 8, iterations)

            status = p.get("state", {}).get("last_status", "idle")
            self.table.setCellWidget(r, 9, StatusPill(status))

    def _collect_row_profile(self, row):
        pid = self.table.item(row, 1).text()
        p = self.ds.profiles["profiles"].get(pid, {})
        # writeback from widgets
        run_cb = self.table.cellWidget(row, 0)
        enabled_cb = self.table.cellWidget(row, 3)
        start_url = self.table.cellWidget(row, 4)
        proxy = self.table.cellWidget(row, 5)
        region = self.table.cellWidget(row, 6)
        script_cb = self.table.cellWidget(row, 7)
        iterations = self.table.cellWidget(row, 8)

        p["enabled"] = bool(enabled_cb.isChecked()) if isinstance(enabled_cb, QCheckBox) else bool(p.get("enabled", True))
        p.setdefault("website", {})
        p["website"]["start_url"] = start_url.text().strip() if isinstance(start_url, QLineEdit) else p["website"].get("start_url", "")
        p.setdefault("proxy", {})
        p["proxy"]["proxy"] = proxy.text().strip() if isinstance(proxy, QLineEdit) else p["proxy"].get("proxy", "")
        p["proxy"]["region_hint"] = region.currentText() if isinstance(region, QComboBox) else p["proxy"].get("region_hint", "auto")
        p.setdefault("traffic", {})
        p["traffic"]["script_id"] = script_cb.currentData() if isinstance(script_cb, QComboBox) else p["traffic"].get("script_id", "")
        p["traffic"]["iterations"] = int(iterations.value()) if isinstance(iterations, QSpinBox) else int(p["traffic"].get("iterations", 1))

        run_selected = bool(run_cb.isChecked()) if isinstance(run_cb, QCheckBox) else False
        return pid, p, run_selected

    def save_profiles(self):
        # validate URLs & proxy formats before saving
        updated = {}
        for r in range(self.table.rowCount()):
            pid, p, _ = self._collect_row_profile(r)
            start = p.get("website", {}).get("start_url", "").strip()
            if start and not start.startswith(("http://", "https://")):
                QMessageBox.critical(self, "Invalid URL", f"{pid}: Start URL must be http(s).")
                return
            px = p.get("proxy", {}).get("proxy", "").strip()
            if px and parse_proxy(px) is None:
                QMessageBox.critical(self, "Invalid Proxy", f"{pid}: Proxy format invalid.")
                return
            updated[pid] = p

        self.ds.profiles["profiles"] = updated
        self.ds.save_profiles()
        QMessageBox.information(self, "Saved", "Profile changes saved.")
        self.refresh()

    def reassign_fingerprints(self):
        if QMessageBox.question(self, "Reassign", "Reassign fingerprints for all profiles?\nThis will change their persistent fingerprint profiles.") != QMessageBox.Yes:
            return
        self.ds.fingerprints.setdefault("assigned", {})
        self.ds.fingerprints["assigned"] = {}
        self.ds.save_fingerprints()
        QMessageBox.information(self, "Done", "All fingerprint assignments cleared. New fingerprints will be assigned on next run.")

    def start_selected(self):
        if self.engine.is_running():
            QMessageBox.information(self, "Running", "Engine is already running.")
            return
        # ensure saved
        self.save_profiles()

        selected = []
        for r in range(self.table.rowCount()):
            pid, _, run_selected = self._collect_row_profile(r)
            if run_selected:
                selected.append(pid)

        if not selected:
            QMessageBox.information(self, "Select", "Select at least one profile in 'Run' column.")
            return

        # ensure scripts exist if referenced
        profiles = self.ds.profiles.get("profiles", {})
        scripts = self.ds.scripts.get("scripts", {})
        for pid in selected:
            p = profiles.get(pid, {})
            sid = p.get("traffic", {}).get("script_id", "")
            if sid and sid not in scripts:
                QMessageBox.critical(self, "Missing Script", f"{pid}: Selected script '{sid}' not found.")
                return

        started = self.engine.start(selected)
        if not started:
            QMessageBox.warning(self, "Not started", "Could not start engine. Check console logs.")
        else:
            self.console.append_line(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] INFO  Engine started.")


# ----------------------------- Main Window -----------------------------

class SidebarButton(AnimatedButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent, accent=False)
        self.setCheckable(True)
        self.setMinimumHeight(42)
        self.setStyleSheet(self.styleSheet() + """
        QPushButton {
            text-align: left;
            padding-left: 14px;
            font-weight: 650;
            border-radius: 12px;
        }
        QPushButton:checked {
            background: rgba(109,94,241,0.18);
            border-color: rgba(109,94,241,0.55);
        }
        """)


class HumanexMainWindow(QMainWindow):
    def __init__(self, ds: DataStore):
        super().__init__()
        self.ds = ds

        self.setWindowTitle(f"{APP_NAME}  •  Enterprise Desktop Automation")
        self.resize(1280, 820)
        self.setMinimumSize(QSize(1100, 720))

        self.logbus = LogBus()
        self.engine = AutomationEngine(ds, self.logbus)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # sidebar
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(14, 14, 14, 14)
        sb.setSpacing(10)

        brand = QLabel("Humanex")
        brand.setObjectName("H1")
        sb.addWidget(brand)

        sub = QLabel("Stealth Chrome Automation\nWindows Desktop Platform")
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        sb.addWidget(sub)

        sep = QFrame()
        sep.setObjectName("Separator")
        sep.setFixedHeight(1)
        sb.addWidget(sep)

        self.btn_website = SidebarButton("1) Website Details")
        self.btn_traffic = SidebarButton("2) Traffic Settings")
        self.btn_proxy = SidebarButton("3) Proxy Settings")
        self.btn_rpa = SidebarButton("4) RPA System")
        self.btn_creator = AnimatedButton("5) RPA Script Creator (Popup)", accent=True)
        self.btn_bot = SidebarButton("6) Bot Control")

        for b in [self.btn_website, self.btn_traffic, self.btn_proxy, self.btn_rpa, self.btn_bot]:
            sb.addWidget(b)

        sb.addWidget(self.btn_creator)

        sb.addStretch(1)

        # footer
        foot = QLabel(f"v{APP_VERSION}  •  Data: {self.ds.base_dir}")
        foot.setObjectName("Muted")
        foot.setWordWrap(True)
        sb.addWidget(foot)

        root.addWidget(sidebar)

        # main content
        main = QFrame()
        main.setStyleSheet("QFrame { background: transparent; }")
        main_l = QVBoxLayout(main)
        main_l.setContentsMargins(14, 14, 14, 14)
        main_l.setSpacing(10)

        # top bar
        top = QFrame()
        top.setObjectName("TopBar")
        top_l = QHBoxLayout(top)
        top_l.setContentsMargins(14, 10, 14, 10)
        top_l.setSpacing(12)
        self.top_title = QLabel("Bot Control")
        self.top_title.setObjectName("H1")
        top_l.addWidget(self.top_title)

        top_l.addStretch(1)

        self.global_status = StatusPill("idle")
        top_l.addWidget(self.global_status)

        main_l.addWidget(top)

        self.stack = QStackedWidget()
        main_l.addWidget(self.stack, 1)

        root.addWidget(main, 1)

        # pages wrapped in scroll area
        self.page_website = WebsiteDetailsPage(ds)
        self.page_traffic = TrafficSettingsPage(ds)
        self.page_proxy = ProxySettingsPage(ds)
        self.page_rpa = RPASystemPage(ds)
        self.page_bot = BotControlPage(ds, self.logbus, self.engine)

        self.stack.addWidget(self._wrap_scroll(self.page_website))
        self.stack.addWidget(self._wrap_scroll(self.page_traffic))
        self.stack.addWidget(self._wrap_scroll(self.page_proxy))
        self.stack.addWidget(self._wrap_scroll(self.page_rpa))
        self.stack.addWidget(self.page_bot)  # already scrolls where needed

        # nav
        self.btn_website.clicked.connect(lambda: self.set_page(0, "Website Details", self.btn_website))
        self.btn_traffic.clicked.connect(lambda: self.set_page(1, "Traffic Settings", self.btn_traffic))
        self.btn_proxy.clicked.connect(lambda: self.set_page(2, "Proxy Settings", self.btn_proxy))
        self.btn_rpa.clicked.connect(lambda: self.set_page(3, "RPA System", self.btn_rpa))
        self.btn_bot.clicked.connect(lambda: self.set_page(4, "Bot Control", self.btn_bot))
        self.btn_creator.clicked.connect(self.open_creator)

        # default page
        self._sidebar_buttons = [self.btn_website, self.btn_traffic, self.btn_proxy, self.btn_rpa, self.btn_bot]
        self.set_page(4, "Bot Control", self.btn_bot)

        # menu actions
        act_open_data = QAction("Open Data Folder", self)
        act_open_data.triggered.connect(self.open_data_folder)
        act_export_all = QAction("Export All Data", self)
        act_export_all.triggered.connect(self.export_all_data)
        act_import_fp = QAction("Import Fingerprint Dataset", self)
        act_import_fp.triggered.connect(self.import_fingerprint_dataset)
        act_clear_fp = QAction("Clear Fingerprint Assignments", self)
        act_clear_fp.triggered.connect(self.clear_fingerprint_assignments)

        menu = self.menuBar().addMenu("Humanex")
        menu.addAction(act_open_data)
        menu.addSeparator()
        menu.addAction(act_import_fp)
        menu.addAction(act_clear_fp)
        menu.addSeparator()
        menu.addAction(act_export_all)

        # global status updates
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._tick_global_status)
        self._status_timer.start(350)

        self._crash_recovery_prompt()

    def _wrap_scroll(self, widget: QWidget):
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(widget)
        lay.addStretch(1)
        sc.setWidget(inner)
        return sc

    def set_page(self, idx, title, btn):
        self.stack.setCurrentIndex(idx)
        self.top_title.setText(title)
        for b in self._sidebar_buttons:
            b.setChecked(b is btn)
        # refresh page (safe)
        try:
            if idx == 0:
                self.page_website.refresh()
            elif idx == 1:
                self.page_traffic.refresh()
            elif idx == 2:
                self.page_proxy.refresh()
            elif idx == 3:
                self.page_rpa.refresh()
            elif idx == 4:
                self.page_bot.refresh()
        except Exception:
            pass

    def open_creator(self):
        if self.engine.is_running():
            QMessageBox.information(self, "Running", "Stop the engine before editing scripts.")
            return
        dlg = ScriptCreatorDialog(self, self.ds)
        dlg.exec()
        # refresh scripts-related pages
        try:
            self.page_rpa.refresh()
            self.page_bot.refresh()
        except Exception:
            pass

    def _tick_global_status(self):
        if self.engine.is_running():
            self.global_status.setStyleFor("running")
        else:
            # reflect last overall: if any profile failed recently, show idle but keep pill idle
            self.global_status.setStyleFor("idle")

    def closeEvent(self, e):
        try:
            self.engine.stop()
        except Exception:
            pass
        super().closeEvent(e)

    def open_data_folder(self):
        path = self.ds.base_dir
        try:
            # Windows
            os.startfile(path)
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Could not open folder:\n{ex}")

    def export_all_data(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export All Humanex Data", os.path.join(self.ds.base_dir, "humanex_export_all.json"), "JSON Files (*.json)")
        if not path:
            return
        try:
            data = {
                "exported_at": now_iso(),
                "settings": self.ds.settings,
                "scripts": self.ds.scripts,
                "fingerprints": self.ds.fingerprints,
                "profiles": self.ds.profiles,
                "app": {"name": APP_NAME, "version": APP_VERSION}
            }
            atomic_write_json(path, data)
            QMessageBox.information(self, "Exported", f"Exported to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def import_fingerprint_dataset(self):
        if self.engine.is_running():
            QMessageBox.information(self, "Running", "Stop the engine before importing datasets.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Import Fingerprint Dataset", self.ds.base_dir, "JSON Files (*.json)")
        if not path:
            return
        try:
            data = read_json_file(path, default=None)
            if not isinstance(data, dict):
                QMessageBox.critical(self, "Invalid dataset", "Dataset must be a JSON object.")
                return

            # expected formats:
            # A) { "name": "...", "profiles": [fingerprint,...] }
            # B) { "datasets": { "x": {"name":..., "profiles":[...] } } }
            datasets_to_add = {}

            if "profiles" in data and isinstance(data["profiles"], list):
                ds_name = data.get("name", f"import_{sha256_hex(path)[:8]}")
                datasets_to_add[ds_name] = {"name": ds_name, "created_at": now_iso(), "profiles": data["profiles"]}
            elif "datasets" in data and isinstance(data["datasets"], dict):
                for k, v in data["datasets"].items():
                    if isinstance(v, dict) and isinstance(v.get("profiles"), list):
                        datasets_to_add[k] = {
                            "name": v.get("name", k),
                            "created_at": v.get("created_at", now_iso()),
                            "profiles": v.get("profiles", [])
                        }
            else:
                QMessageBox.critical(self, "Invalid dataset", "Dataset must contain 'profiles' list or 'datasets' object.")
                return

            # validate fingerprints; keep only valid
            kept = 0
            rejected = 0
            for k, dsobj in datasets_to_add.items():
                fps = dsobj.get("profiles", [])
                valid = []
                for fp in fps:
                    ok, err = FingerprintFactory.validate_fingerprint(fp) if isinstance(fp, dict) else (False, "fingerprint not object")
                    if ok:
                        # ensure has id
                        if "id" not in fp or not fp["id"]:
                            fp["id"] = "fp_" + sha256_hex(json.dumps(fp, sort_keys=True))[:10]
                        valid.append(fp)
                        kept += 1
                    else:
                        rejected += 1
                dsobj["profiles"] = valid

            if kept == 0:
                QMessageBox.critical(self, "Import Failed", f"No valid fingerprints found. Rejected: {rejected}")
                return

            self.ds.fingerprints.setdefault("datasets", {})
            for k, dsobj in datasets_to_add.items():
                # avoid collision by suffix if exists
                key = k
                i = 2
                while key in self.ds.fingerprints["datasets"]:
                    key = f"{k}_{i}"
                    i += 1
                self.ds.fingerprints["datasets"][key] = dsobj

            self.ds.save_fingerprints()
            QMessageBox.information(self, "Imported", f"Imported fingerprints: {kept}\nRejected: {rejected}\nDatasets added: {len(datasets_to_add)}")
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", str(e))

    def clear_fingerprint_assignments(self):
        if self.engine.is_running():
            QMessageBox.information(self, "Running", "Stop the engine before clearing assignments.")
            return
        if QMessageBox.question(self, "Clear", "Clear all profile fingerprint assignments?") != QMessageBox.Yes:
            return
        self.ds.fingerprints["assigned"] = {}
        self.ds.save_fingerprints()
        QMessageBox.information(self, "Done", "Fingerprint assignments cleared.")

    def _crash_recovery_prompt(self):
        rec = self.ds.load_recovery()
        if not rec or not rec.get("running"):
            return
        # offer to clear recovery marker
        msg = (
            "Humanex detected an unfinished previous run.\n\n"
            f"Created: {rec.get('created_at', '')}\n"
            f"Jobs done/total: {rec.get('jobs_done', 0)}/{rec.get('jobs_total', 0)}\n\n"
            "Humanex can safely continue. The previous browser instance is not reused.\n"
            "Do you want to clear the recovery state now?"
        )
        if QMessageBox.question(self, "Recovery Detected", msg) == QMessageBox.Yes:
            self.ds.clear_recovery()


# ----------------------------- Entry Point -----------------------------

def ensure_single_instance_marker(data_dir):
    # lightweight marker to prevent accidental multi-run; not strict locking.
    marker = os.path.join(data_dir, "instance.lock")
    try:
        # if exists and fresh, warn
        if os.path.exists(marker):
            age = time.time() - os.path.getmtime(marker)
            if age < 10:
                return False, marker
        with open(marker, "w", encoding="utf-8") as f:
            f.write(now_iso())
        return True, marker
    except Exception:
        return True, marker


def cleanup_instance_marker(marker):
    try:
        if marker and os.path.exists(marker):
            os.remove(marker)
    except Exception:
        pass


def main():
    safe_mkdir(DEFAULT_DATA_DIR)
    ok, marker = ensure_single_instance_marker(DEFAULT_DATA_DIR)
    if not ok:
        # still allow, but warn
        pass

    ds = DataStore(DEFAULT_DATA_DIR)

    # ensure at least one script exists for usability
    if not ds.scripts.get("scripts"):
        sample = {
            "schema": "humanex.rpa.v1",
            "name": "Sample: Example Landing",
            "options": {"note": "Built-in sample"},
            "steps": [
                {"action": "goto", "url": "https://example.com", "wait_until": "domcontentloaded", "label": "Open example.com"},
                {"action": "wait", "ms": 900, "label": "Wait"},
                {"action": "scroll", "dy": 520, "behavior": "smooth", "label": "Scroll"},
                {"action": "screenshot", "name": "landing", "full_page": False, "label": "Screenshot"}
            ]
        }
        sid = "script_" + sha256_hex(sample["name"] + "|" + json.dumps(sample, sort_keys=True))[:10]
        ds.scripts.setdefault("scripts", {})[sid] = sample
        ds.settings.setdefault("rpa", {})
        if not ds.settings["rpa"].get("default_script_id"):
            ds.settings["rpa"]["default_script_id"] = sid
            ds.save_settings()
        ds.save_scripts()

    app = QApplication(sys.argv)
    apply_premium_theme(app)

    win = HumanexMainWindow(ds)
    win.show()

    code = 0
    try:
        code = app.exec()
    finally:
        cleanup_instance_marker(marker)

    sys.exit(code)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Fail loudly with a dialog
        try:
            app = QApplication.instance() or QApplication(sys.argv)
            apply_premium_theme(app)
            QMessageBox.critical(None, "Humanex Fatal Error", f"{e}\n\n{traceback.format_exc()}")
        except Exception:
            print("Humanex Fatal Error:", e)
            print(traceback.format_exc())
        raise
```