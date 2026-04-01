"""
ChatGPT 批量自动注册工具 (并发版) - Mailu 邮箱版
依赖: pip install curl_cffi
功能: 使用自建 Mailu 邮箱服务器，并发自动注册 ChatGPT 账号，自动获取 OTP 验证码
"""

import os
import re
import uuid
import json
import random
import string
import time
import sys
import shutil
import subprocess
import threading
import traceback
import secrets
import hashlib
import base64
import imaplib
import email
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs, urlencode

from curl_cffi import requests as curl_requests

# ================= 加载配置 =================
def _load_config():
    """从 config.json 加载配置，环境变量优先级更高"""
    config = {
        "total_accounts": 5,
        "max_workers": 1,
        "mailu_base_url": "https://mail.oracle.311200.xyz",
        "mailu_api_token": "",
        "mail_domain": "oracle.311200.xyz",
        "mailbox_quota_bytes": 1073741824,
        "imap_host": "mail.oracle.311200.xyz",
        "imap_port": 993,
        "imap_ssl": True,
        "imap_folder": "INBOX",
        "imap_timeout": 20,
        "proxy": "",
        "output_file": "registered_accounts.txt",
        "enable_oauth": True,
        "oauth_required": True,
        "oauth_issuer": "https://auth.openai.com",
        "oauth_client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
        "oauth_redirect_uri": "http://localhost:1455/auth/callback",
        "ak_file": "ak.txt",
        "rk_file": "rk.txt",
        "token_json_dir": "codex_tokens",
        "upload_api_url": "",
        "upload_api_token": "",
        "log_file": "logs/register.log",
        "openclaw_bin": "/usr/bin/openclaw",
        "tg_channel": "telegram",
        "tg_target": "1014334465",
        "tg_account": "botClaw",
        "tg_bot_token": "",
        "tg_chat_id": "",
        "tg_proxy_url": "",
        "tg_notify": True,
        "tg_include_account": True,
        "openai_proxy": "",
        "openai_proxy_mode": "inherit",
    }

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception as e:
            print(f"⚠️ 加载 config.json 失败: {e}")

    # 环境变量优先级更高
    config["mailu_base_url"] = os.environ.get("MAILU_BASE_URL", config["mailu_base_url"])
    config["mailu_api_token"] = os.environ.get("MAILU_API_TOKEN", config["mailu_api_token"])
    config["mail_domain"] = os.environ.get("MAIL_DOMAIN", config["mail_domain"])
    config["mailbox_quota_bytes"] = int(os.environ.get("MAILBOX_QUOTA_BYTES", config["mailbox_quota_bytes"]))
    config["imap_host"] = os.environ.get("IMAP_HOST", config["imap_host"])
    config["imap_port"] = int(os.environ.get("IMAP_PORT", config["imap_port"]))
    config["imap_ssl"] = os.environ.get("IMAP_SSL", config["imap_ssl"])
    config["imap_folder"] = os.environ.get("IMAP_FOLDER", config["imap_folder"])
    config["imap_timeout"] = int(os.environ.get("IMAP_TIMEOUT", config["imap_timeout"]))
    config["proxy"] = os.environ.get("PROXY", config["proxy"])
    config["total_accounts"] = int(os.environ.get("TOTAL_ACCOUNTS", config["total_accounts"]))
    config["max_workers"] = int(os.environ.get("MAX_WORKERS", config["max_workers"]))
    config["enable_oauth"] = os.environ.get("ENABLE_OAUTH", config["enable_oauth"])
    config["oauth_required"] = os.environ.get("OAUTH_REQUIRED", config["oauth_required"])
    config["oauth_issuer"] = os.environ.get("OAUTH_ISSUER", config["oauth_issuer"])
    config["oauth_client_id"] = os.environ.get("OAUTH_CLIENT_ID", config["oauth_client_id"])
    config["oauth_redirect_uri"] = os.environ.get("OAUTH_REDIRECT_URI", config["oauth_redirect_uri"])
    config["ak_file"] = os.environ.get("AK_FILE", config["ak_file"])
    config["rk_file"] = os.environ.get("RK_FILE", config["rk_file"])
    config["token_json_dir"] = os.environ.get("TOKEN_JSON_DIR", config["token_json_dir"])
    config["upload_api_url"] = os.environ.get("UPLOAD_API_URL", config["upload_api_url"])
    config["upload_api_token"] = os.environ.get("UPLOAD_API_TOKEN", config["upload_api_token"])
    config["log_file"] = os.environ.get("REGISTER_LOG_FILE", config["log_file"])
    config["openclaw_bin"] = os.environ.get("OPENCLAW_BIN", config["openclaw_bin"])
    config["tg_channel"] = os.environ.get("TG_CHANNEL", config["tg_channel"])
    config["tg_target"] = os.environ.get("TG_TARGET", config["tg_target"])
    config["tg_account"] = os.environ.get("TG_ACCOUNT", config["tg_account"])
    config["tg_bot_token"] = os.environ.get("TELEGRAM_BOT_TOKEN", config["tg_bot_token"])
    config["tg_chat_id"] = os.environ.get("TELEGRAM_CHAT_ID", config["tg_chat_id"])
    config["tg_proxy_url"] = os.environ.get("TELEGRAM_PROXY_URL", config["tg_proxy_url"])
    config["tg_notify"] = os.environ.get("TG_NOTIFY", config["tg_notify"])
    config["tg_include_account"] = os.environ.get("TG_INCLUDE_ACCOUNT", config["tg_include_account"])
    config["openai_proxy"] = os.environ.get("OPENAI_PROXY", config["openai_proxy"])
    config["openai_proxy_mode"] = os.environ.get("OPENAI_PROXY_MODE", config["openai_proxy_mode"])

    return config


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG = _load_config()
MAILU_BASE_URL = _CONFIG["mailu_base_url"].rstrip("/")
MAILU_API_TOKEN = _CONFIG["mailu_api_token"]
MAIL_DOMAIN = _CONFIG["mail_domain"]
MAILBOX_QUOTA_BYTES = int(_CONFIG.get("mailbox_quota_bytes", 1073741824))
IMAP_HOST = _CONFIG["imap_host"]
IMAP_PORT = int(_CONFIG["imap_port"])
IMAP_SSL = _as_bool(_CONFIG.get("imap_ssl", True))
IMAP_FOLDER = _CONFIG.get("imap_folder", "INBOX")
IMAP_TIMEOUT = int(_CONFIG.get("imap_timeout", 20))
DEFAULT_TOTAL_ACCOUNTS = _CONFIG["total_accounts"]
DEFAULT_PROXY = _CONFIG["proxy"]
DEFAULT_MAX_WORKERS = int(_CONFIG.get("max_workers", 1))
DEFAULT_OUTPUT_FILE = _CONFIG["output_file"]
ENABLE_OAUTH = _as_bool(_CONFIG.get("enable_oauth", True))
OAUTH_REQUIRED = _as_bool(_CONFIG.get("oauth_required", True))
OAUTH_ISSUER = _CONFIG["oauth_issuer"].rstrip("/")
OAUTH_CLIENT_ID = _CONFIG["oauth_client_id"]
OAUTH_REDIRECT_URI = _CONFIG["oauth_redirect_uri"]
AK_FILE = _CONFIG["ak_file"]
RK_FILE = _CONFIG["rk_file"]
TOKEN_JSON_DIR = _CONFIG["token_json_dir"]
UPLOAD_API_URL = _CONFIG["upload_api_url"]
UPLOAD_API_TOKEN = _CONFIG["upload_api_token"]
LOG_FILE = (_CONFIG.get("log_file") or "").strip()
if LOG_FILE and not os.path.isabs(LOG_FILE):
    LOG_FILE = os.path.join(BASE_DIR, LOG_FILE)
OPENCLAW_BIN = (_CONFIG.get("openclaw_bin") or "").strip()
TG_CHANNEL = (_CONFIG.get("tg_channel") or "telegram").strip()
TG_TARGET = (_CONFIG.get("tg_target") or "").strip()
TG_ACCOUNT = (_CONFIG.get("tg_account") or "").strip()
TG_BOT_TOKEN = (_CONFIG.get("tg_bot_token") or "").strip()
TG_CHAT_ID = (_CONFIG.get("tg_chat_id") or "").strip()
TG_PROXY_URL = (_CONFIG.get("tg_proxy_url") or "").strip()
TG_NOTIFY = _as_bool(_CONFIG.get("tg_notify", True))
TG_INCLUDE_ACCOUNT = _as_bool(_CONFIG.get("tg_include_account", True))
OPENAI_PROXY = (_CONFIG.get("openai_proxy") or "").strip()
OPENAI_PROXY_MODE = (_CONFIG.get("openai_proxy_mode") or "inherit").strip().lower()

# 代理固定值（仅在环境变量显式开启时使用）
FIXED_PROXY = os.environ.get("FIXED_PROXY", "").strip()
USE_FIXED_PROXY = _as_bool(os.environ.get("USE_FIXED_PROXY", "false"))
ACTIVE_PROXY = None
# OTP 等待轮次（秒）：5 分钟 + 10 分钟
OTP_WAIT_ROUNDS = [300, 600]

# 风控探测配置
RISK_THRESHOLD = int(os.environ.get("RISK_THRESHOLD", "3"))
_DEFAULT_RISK_KEYWORDS = [
    "risk",
    "suspicious",
    "unusual activity",
    "abuse",
    "blocked",
    "forbidden",
    "denied",
    "access denied",
    "too many requests",
    "rate limit",
    "rate_limit",
    "captcha",
    "hcaptcha",
    "arkose",
    "cloudflare",
    "cf-chl",
    "account locked",
    "temporarily locked",
    "account suspended",
    "bot",
    "automated",
    "风控",
    "风险",
    "异常行为",
    "访问被拒绝",
    "请求过多",
    "请求过于频繁",
    "封禁",
    "冻结",
    "限制访问",
    "账号异常",
]
_RISK_KEYWORDS_ENV = os.environ.get("RISK_KEYWORDS", "").strip()
if _RISK_KEYWORDS_ENV:
    RISK_KEYWORDS = [k.strip().lower() for k in _RISK_KEYWORDS_ENV.split(",") if k.strip()]
else:
    RISK_KEYWORDS = [k.lower() for k in _DEFAULT_RISK_KEYWORDS]
_RISK_STATUSES_ENV = os.environ.get("RISK_STATUSES", "403,429").strip()
RISK_STATUSES = set()
for _code in _RISK_STATUSES_ENV.split(","):
    _code = _code.strip()
    if _code.isdigit():
        RISK_STATUSES.add(int(_code))


def _resolve_proxy():
    if USE_FIXED_PROXY and FIXED_PROXY:
        return FIXED_PROXY
    if DEFAULT_PROXY:
        return DEFAULT_PROXY
    for key in ("PROXY", "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        val = os.environ.get(key)
        if val:
            return val
    return ""


def _set_active_proxy(proxy):
    global ACTIVE_PROXY
    ACTIVE_PROXY = proxy or ""


def _get_active_proxy():
    if ACTIVE_PROXY:
        return ACTIVE_PROXY
    return _resolve_proxy()


def _resolve_openai_proxy(base_proxy: str):
    mode = (OPENAI_PROXY_MODE or "inherit").strip().lower()
    if mode in {"direct", "none", "off"}:
        return ""
    if mode in {"proxy", "force"}:
        return (OPENAI_PROXY or base_proxy or "").strip()
    return (OPENAI_PROXY or base_proxy or "").strip()


def _is_local_hostname(hostname: str) -> bool:
    if not hostname:
        return False
    host = hostname.strip().lower()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    return host == "localhost" or host == "::1" or host.startswith("127.")


def _resolve_upload_proxy(upload_url: str) -> str:
    """为上传接口选择代理；本地地址默认直连。"""
    if "UPLOAD_PROXY" in os.environ:
        return os.environ.get("UPLOAD_PROXY", "").strip()
    if "UPLOAD_API_PROXY" in os.environ:
        return os.environ.get("UPLOAD_API_PROXY", "").strip()
    try:
        host = urlparse(upload_url).hostname
    except Exception:
        host = None
    if host and _is_local_hostname(host):
        return ""
    return _get_active_proxy()


def _count_file_lines(path: str) -> int:
    if not path:
        return 0
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def _get_last_new_line(path: str, start_line: int):
    if not path:
        return "", 0
    last_line = ""
    new_count = 0
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, start=1):
                if idx <= start_line:
                    continue
                new_count += 1
                last_line = line.strip()
    except Exception:
        return "", 0
    return last_line, new_count


def _resolve_openclaw_bin() -> str:
    candidate = (OPENCLAW_BIN or "").strip()
    if not candidate:
        return ""
    if os.path.isabs(candidate):
        return candidate if os.path.exists(candidate) else ""
    found = shutil.which(candidate)
    return found or ""


def _send_openclaw_message(message: str) -> bool:
    if not TG_NOTIFY:
        return False
    if not message:
        return False
    target = (TG_TARGET or "").strip()
    if not target:
        return False
    bin_path = _resolve_openclaw_bin()
    if not bin_path:
        return False
    cmd = [bin_path, "message", "send"]
    if TG_ACCOUNT:
        cmd += ["--account", TG_ACCOUNT]
    cmd += ["--channel", TG_CHANNEL or "telegram", "--target", target, "--message", message]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return True
    except Exception:
        return False


def _send_telegram_bot_message(message: str) -> bool:
    if not TG_NOTIFY:
        return False
    if not message:
        return False
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TG_CHAT_ID, "text": message}
    proxies = None
    if TG_PROXY_URL:
        proxies = {"http": TG_PROXY_URL, "https": TG_PROXY_URL}
    try:
        resp = curl_requests.post(url, data=data, proxies=proxies, timeout=30)
    except Exception:
        return False
    if resp.status_code != 200:
        return False
    try:
        payload = resp.json()
    except Exception:
        return False
    return bool(payload.get("ok"))


def _send_notification(message: str) -> bool:
    if not TG_NOTIFY:
        return False
    if TG_BOT_TOKEN and TG_CHAT_ID:
        return _send_telegram_bot_message(message)
    return _send_openclaw_message(message)


def _send_error_notification(index, total, email, error_msg, step_info=None):
    if not TG_NOTIFY:
        return False
    msg = (error_msg or "").strip()
    if len(msg) > 1600:
        msg = msg[:1600] + "..."
    lines = [
        "ChatGPT 注册失败",
        f"时间: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"账号: {index}/{total}",
        f"邮箱: {email or '-'}",
        f"疑似风控: {'是' if _is_risk_error(error_msg or '') else '否'}",
        f"错误: {msg or '-'}",
    ]
    if step_info:
        step = step_info.get("step") or "-"
        status = step_info.get("status")
        method = step_info.get("method") or "-"
        url = step_info.get("url") or "-"
        lines.append(f"Step: {step}")
        if status is not None:
            lines.append(f"Status: {status}")
        lines.append(f"Request: {method} {url}")
        body_preview = (step_info.get("body_preview") or "").strip()
        if body_preview:
            if len(body_preview) > 500:
                body_preview = body_preview[:500] + "..."
            lines.append(f"Response: {body_preview}")
    return _send_notification("\n".join(lines))


def _send_success_notification(index, total, email):
    if not TG_NOTIFY:
        return False
    lines = [
        "ChatGPT 注册成功",
        f"时间: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"账号: {index}/{total}",
        f"邮箱: {email or '-'}",
    ]
    return _send_notification("\n".join(lines))


def _append_log(event: str, message: str, **fields):
    if not LOG_FILE:
        return
    payload = {
        "time": datetime.now().astimezone().isoformat(),
        "event": event,
        "message": message,
    }
    payload.update(fields)
    try:
        log_dir = os.path.dirname(LOG_FILE)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        with _log_lock:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False))
                f.write("\n")
    except Exception:
        # 日志写入失败不应影响主流程
        pass


def _extract_status_code(error_msg: str):
    if not error_msg:
        return None
    m = re.search(r"\((\d{3})\)", error_msg)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    m = re.search(r'"status"\s*:\s*(\d{3})', error_msg)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    m = re.search(r"\bstatus\s*=\s*(\d{3})\b", error_msg)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def _is_risk_error(error_msg: str) -> bool:
    if not error_msg:
        return False
    status = _extract_status_code(error_msg)
    if status in RISK_STATUSES:
        return True
    msg = error_msg.lower()
    for kw in RISK_KEYWORDS:
        if kw and kw in msg:
            return True
    return False


def _iter_log_events(log_path: str):
    if not log_path or not os.path.exists(log_path):
        return
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue
    except Exception:
        return


def _get_last_batch_summary(log_path: str):
    events = list(_iter_log_events(log_path) or [])
    if not events:
        return None
    last_start_idx = None
    for i in range(len(events) - 1, -1, -1):
        if events[i].get("event") == "batch_start":
            last_start_idx = i
            break
    if last_start_idx is None:
        return None
    batch_events = events[last_start_idx:]
    batch_time = None
    for ev in reversed(batch_events):
        ts = ev.get("time")
        if ts:
            try:
                batch_time = datetime.fromisoformat(ts).astimezone()
                break
            except Exception:
                batch_time = None
                break
    risk_count = None
    for ev in reversed(batch_events):
        if ev.get("event") == "batch_end" and "risk" in ev:
            try:
                risk_count = int(ev.get("risk", 0))
            except Exception:
                risk_count = 0
            break
    if risk_count is None:
        risk_count = 0
        for ev in batch_events:
            if ev.get("event") != "register_fail":
                continue
            risk_flag = ev.get("risk")
            if risk_flag is None:
                risk_flag = _is_risk_error(ev.get("error", "") or "")
            if risk_flag:
                risk_count += 1
    return {
        "time": batch_time,
        "risk_count": risk_count,
    }


def _should_skip_today_due_to_risk(log_path: str, threshold: int):
    if not log_path:
        return None
    summary = _get_last_batch_summary(log_path)
    if not summary:
        return None
    batch_time = summary.get("time")
    if not batch_time:
        return None
    today = datetime.now().astimezone().date()
    if batch_time.date() != today:
        return None
    risk_count = int(summary.get("risk_count", 0) or 0)
    if risk_count >= threshold:
        return summary
    return None

if not MAILU_API_TOKEN:
    print("⚠️ 警告: 未设置 MAILU_API_TOKEN，请在 config.json 中设置或设置环境变量")
    print("   文件: config.json -> mailu_api_token")
    print("   环境变量: export MAILU_API_TOKEN='your_api_key_here'")

# 全局线程锁
_print_lock = threading.Lock()
_file_lock = threading.Lock()
_log_lock = threading.Lock()
_risk_lock = threading.Lock()
_risk_count = 0


def _reset_risk_counter():
    global _risk_count
    with _risk_lock:
        _risk_count = 0


def _increment_risk_counter():
    global _risk_count
    with _risk_lock:
        _risk_count += 1


def _get_risk_counter():
    with _risk_lock:
        return _risk_count


# Chrome 指纹配置: impersonate 与 sec-ch-ua 必须匹配真实浏览器
_CHROME_PROFILES = [
    {
        "major": 131, "impersonate": "chrome131",
        "build": 6778, "patch_range": (69, 205),
        "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    },
    {
        "major": 124, "impersonate": "chrome124",
        "build": 6367, "patch_range": (0, 150),
        "sec_ch_ua": '"Google Chrome";v="124", "Chromium";v="124", "Not_A Brand";v="24"',
    },
    {
        "major": 120, "impersonate": "chrome120",
        "build": 6099, "patch_range": (0, 200),
        "sec_ch_ua": '"Google Chrome";v="120", "Chromium";v="120", "Not_A Brand";v="24"',
    },
]


def _random_chrome_version():
    profile = random.choice(_CHROME_PROFILES)
    major = profile["major"]
    build = profile["build"]
    patch = random.randint(*profile["patch_range"])
    full_ver = f"{major}.0.{build}.{patch}"
    ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{full_ver} Safari/537.36"
    return profile["impersonate"], major, full_ver, ua, profile["sec_ch_ua"]


def _random_delay(low=0.3, high=1.0):
    time.sleep(random.uniform(low, high))


def _make_trace_headers():
    trace_id = random.randint(10**17, 10**18 - 1)
    parent_id = random.randint(10**17, 10**18 - 1)
    tp = f"00-{uuid.uuid4().hex}-{format(parent_id, '016x')}-01"
    return {
        "traceparent": tp, "tracestate": "dd=s:1;o:rum",
        "x-datadog-origin": "rum", "x-datadog-sampling-priority": "1",
        "x-datadog-trace-id": str(trace_id), "x-datadog-parent-id": str(parent_id),
    }


def _generate_pkce():
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


class SentinelTokenGenerator:
    """纯 Python 版本 sentinel token 生成器（PoW）"""

    MAX_ATTEMPTS = 500000
    ERROR_PREFIX = "wQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D"

    def __init__(self, device_id=None, user_agent=None):
        self.device_id = device_id or str(uuid.uuid4())
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        )
        self.requirements_seed = str(random.random())
        self.sid = str(uuid.uuid4())

    @staticmethod
    def _fnv1a_32(text: str):
        h = 2166136261
        for ch in text:
            h ^= ord(ch)
            h = (h * 16777619) & 0xFFFFFFFF
        h ^= (h >> 16)
        h = (h * 2246822507) & 0xFFFFFFFF
        h ^= (h >> 13)
        h = (h * 3266489909) & 0xFFFFFFFF
        h ^= (h >> 16)
        h &= 0xFFFFFFFF
        return format(h, "08x")

    def _get_config(self):
        now_str = time.strftime(
            "%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)",
            time.gmtime(),
        )
        perf_now = random.uniform(1000, 50000)
        time_origin = time.time() * 1000 - perf_now
        nav_prop = random.choice([
            "vendorSub", "productSub", "vendor", "maxTouchPoints",
            "scheduling", "userActivation", "doNotTrack", "geolocation",
            "connection", "plugins", "mimeTypes", "pdfViewerEnabled",
            "webkitTemporaryStorage", "webkitPersistentStorage",
            "hardwareConcurrency", "cookieEnabled", "credentials",
            "mediaDevices", "permissions", "locks", "ink",
        ])
        nav_val = f"{nav_prop}-undefined"

        return [
            "1920x1080",
            now_str,
            4294705152,
            random.random(),
            self.user_agent,
            "https://sentinel.openai.com/sentinel/20260124ceb8/sdk.js",
            None,
            None,
            "en-US",
            "en-US,en",
            random.random(),
            nav_val,
            random.choice(["location", "implementation", "URL", "documentURI", "compatMode"]),
            random.choice(["Object", "Function", "Array", "Number", "parseFloat", "undefined"]),
            perf_now,
            self.sid,
            "",
            random.choice([4, 8, 12, 16]),
            time_origin,
        ]

    @staticmethod
    def _base64_encode(data):
        raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return base64.b64encode(raw).decode("ascii")

    def _run_check(self, start_time, seed, difficulty, config, nonce):
        config[3] = nonce
        config[9] = round((time.time() - start_time) * 1000)
        data = self._base64_encode(config)
        hash_hex = self._fnv1a_32(seed + data)
        diff_len = len(difficulty)
        if hash_hex[:diff_len] <= difficulty:
            return data + "~S"
        return None

    def generate_token(self, seed=None, difficulty=None):
        seed = seed if seed is not None else self.requirements_seed
        difficulty = str(difficulty or "0")
        start_time = time.time()
        config = self._get_config()

        for i in range(self.MAX_ATTEMPTS):
            result = self._run_check(start_time, seed, difficulty, config, i)
            if result:
                return "gAAAAAB" + result
        return "gAAAAAB" + self.ERROR_PREFIX + self._base64_encode(str(None))

    def generate_requirements_token(self):
        config = self._get_config()
        config[3] = 1
        config[9] = round(random.uniform(5, 50))
        data = self._base64_encode(config)
        return "gAAAAAC" + data


def fetch_sentinel_challenge(session, device_id, flow="authorize_continue", user_agent=None,
                             sec_ch_ua=None, impersonate=None):
    generator = SentinelTokenGenerator(device_id=device_id, user_agent=user_agent)
    req_body = {
        "p": generator.generate_requirements_token(),
        "id": device_id,
        "flow": flow,
    }
    headers = {
        "Content-Type": "text/plain;charset=UTF-8",
        "Referer": "https://sentinel.openai.com/backend-api/sentinel/frame.html",
        "Origin": "https://sentinel.openai.com",
        "User-Agent": user_agent or "Mozilla/5.0",
        "sec-ch-ua": sec_ch_ua or '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }

    kwargs = {
        "data": json.dumps(req_body),
        "headers": headers,
        "timeout": 20,
    }
    if impersonate:
        kwargs["impersonate"] = impersonate

    try:
        resp = session.post("https://sentinel.openai.com/backend-api/sentinel/req", **kwargs)
    except Exception:
        return None

    if resp.status_code != 200:
        return None

    try:
        return resp.json()
    except Exception:
        return None


def build_sentinel_token(session, device_id, flow="authorize_continue", user_agent=None,
                         sec_ch_ua=None, impersonate=None):
    challenge = fetch_sentinel_challenge(
        session,
        device_id,
        flow=flow,
        user_agent=user_agent,
        sec_ch_ua=sec_ch_ua,
        impersonate=impersonate,
    )
    if not challenge:
        return None

    c_value = challenge.get("token", "")
    if not c_value:
        return None

    pow_data = challenge.get("proofofwork") or {}
    generator = SentinelTokenGenerator(device_id=device_id, user_agent=user_agent)

    if pow_data.get("required") and pow_data.get("seed"):
        p_value = generator.generate_token(
            seed=pow_data.get("seed"),
            difficulty=pow_data.get("difficulty", "0"),
        )
    else:
        p_value = generator.generate_requirements_token()

    return json.dumps({
        "p": p_value,
        "t": "",
        "c": c_value,
        "id": device_id,
        "flow": flow,
    }, separators=(",", ":"))


def _extract_code_from_url(url: str):
    if not url or "code=" not in url:
        return None
    try:
        return parse_qs(urlparse(url).query).get("code", [None])[0]
    except Exception:
        return None


def _decode_jwt_payload(token: str):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return {}


def _save_codex_tokens(email: str, tokens: dict):
    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    id_token = tokens.get("id_token", "")

    if access_token:
        with _file_lock:
            with open(AK_FILE, "a", encoding="utf-8") as f:
                f.write(f"{access_token}\n")

    if refresh_token:
        with _file_lock:
            with open(RK_FILE, "a", encoding="utf-8") as f:
                f.write(f"{refresh_token}\n")

    if not access_token:
        return

    payload = _decode_jwt_payload(access_token)
    auth_info = payload.get("https://api.openai.com/auth", {})
    account_id = auth_info.get("chatgpt_account_id", "")

    exp_timestamp = payload.get("exp")
    expired_str = ""
    if isinstance(exp_timestamp, int) and exp_timestamp > 0:
        from datetime import datetime, timezone, timedelta

        exp_dt = datetime.fromtimestamp(exp_timestamp, tz=timezone(timedelta(hours=8)))
        expired_str = exp_dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")

    from datetime import datetime, timezone, timedelta

    now = datetime.now(tz=timezone(timedelta(hours=8)))
    token_data = {
        "type": "codex",
        "email": email,
        "expired": expired_str,
        "id_token": id_token,
        "account_id": account_id,
        "access_token": access_token,
        "last_refresh": now.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "refresh_token": refresh_token,
    }

    base_dir = os.path.dirname(os.path.abspath(__file__))
    token_dir = TOKEN_JSON_DIR if os.path.isabs(TOKEN_JSON_DIR) else os.path.join(base_dir, TOKEN_JSON_DIR)
    os.makedirs(token_dir, exist_ok=True)

    token_path = os.path.join(token_dir, f"{email}.json")
    with _file_lock:
        with open(token_path, "w", encoding="utf-8") as f:
            json.dump(token_data, f, ensure_ascii=False)
    _append_log(
        "token_saved",
        "token json saved",
        email=email,
        token_path=token_path,
        account_id=account_id,
        expired=expired_str,
    )

    # 上传到 CPA 管理平台
    if UPLOAD_API_URL:
        _upload_token_json(token_path)


def _upload_token_json(filepath):
    """上传 Token JSON 文件到 CPA 管理平台"""
    mp = None
    upload_proxy = _resolve_upload_proxy(UPLOAD_API_URL)
    try:
        _append_log(
            "token_upload_start",
            "uploading token json to CPA",
            file=filepath,
            upload_api_url=UPLOAD_API_URL,
            proxy=upload_proxy,
        )
        from curl_cffi import CurlMime

        filename = os.path.basename(filepath)
        mp = CurlMime()
        mp.addpart(
            name="file",
            content_type="application/json",
            filename=filename,
            local_path=filepath,
        )

        session = curl_requests.Session()
        if upload_proxy:
            session.proxies = {"http": upload_proxy, "https": upload_proxy}

        resp = session.post(
            UPLOAD_API_URL,
            multipart=mp,
            headers={"Authorization": f"Bearer {UPLOAD_API_TOKEN}"},
            verify=False,
            timeout=30,
        )

        if resp.status_code == 200:
            with _print_lock:
                print(f"  [CPA] Token JSON 已上传到 CPA 管理平台")
            _append_log(
                "token_upload_ok",
                "token json uploaded",
                file=filepath,
                status_code=resp.status_code,
            )
        else:
            with _print_lock:
                print(f"  [CPA] 上传失败: {resp.status_code} - {resp.text[:200]}")
            _append_log(
                "token_upload_fail",
                "token json upload failed",
                file=filepath,
                status_code=resp.status_code,
                error=resp.text[:200],
            )
    except Exception as e:
        with _print_lock:
            print(f"  [CPA] 上传异常: {e}")
        _append_log(
            "token_upload_error",
            "token json upload exception",
            file=filepath,
            error=str(e),
        )
    finally:
        if mp:
            mp.close()


def _generate_password(length=14):
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%&*"
    pwd = [random.choice(lower), random.choice(upper),
           random.choice(digits), random.choice(special)]
    all_chars = lower + upper + digits + special
    pwd += [random.choice(all_chars) for _ in range(length - 4)]
    random.shuffle(pwd)
    return "".join(pwd)


# ================= Mailu 邮箱函数 =================

def _create_mailu_session():
    """创建 Mailu API 请求会话"""
    session = curl_requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    return session


def _create_mailbox_mailu(email_addr: str, password: str):
    """通过 Mailu API 创建邮箱账号"""
    if not MAILU_API_TOKEN:
        raise Exception("MAILU_API_TOKEN 未设置，无法创建邮箱")

    headers = {"Authorization": f"Bearer {MAILU_API_TOKEN}"}
    payload = {
        "email": email_addr,
        "raw_password": password,
        "quota_bytes": MAILBOX_QUOTA_BYTES,
        "enabled": True,
        "global_admin": False,
    }

    session = _create_mailu_session()
    res = session.post(
        f"{MAILU_BASE_URL}/api/v1/user",
        json=payload,
        headers=headers,
        timeout=30,
        impersonate="chrome131",
    )

    if res.status_code not in [200, 201]:
        raise Exception(f"创建邮箱失败: {res.status_code} - {res.text[:200]}")


def create_temp_email():
    """创建 Mailu 邮箱，返回 (email, password)"""
    # 生成随机邮箱前缀 8-13 位
    chars = string.ascii_lowercase + string.digits
    length = random.randint(8, 13)
    email_local = "".join(random.choice(chars) for _ in range(length))
    email_addr = f"{email_local}@{MAIL_DOMAIN}"
    password = _generate_password()

    try:
        _create_mailbox_mailu(email_addr, password)
        return email_addr, password
    except Exception as e:
        raise Exception(f"Mailu 创建邮箱失败: {e}")


def _decode_email_part(part):
    payload = part.get_payload(decode=True)
    if payload is None:
        raw = part.get_payload()
        return raw if isinstance(raw, str) else ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except Exception:
        return payload.decode("utf-8", errors="replace")


def _extract_text_from_message(msg):
    texts = []
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "").lower()
            if content_type in ("text/plain", "text/html") and "attachment" not in disp:
                text = _decode_email_part(part)
                if text:
                    texts.append(text)
    else:
        text = _decode_email_part(msg)
        if text:
            texts.append(text)
    return "\n".join(texts)


def _imap_connect():
    if not IMAP_HOST:
        return None
    try:
        if IMAP_SSL:
            try:
                return imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=IMAP_TIMEOUT)
            except TypeError:
                return imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        try:
            return imaplib.IMAP4(IMAP_HOST, IMAP_PORT, timeout=IMAP_TIMEOUT)
        except TypeError:
            return imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
    except Exception:
        return None


def _imap_fetch_latest_texts(email_addr: str, email_password: str, limit: int = 8):
    conn = _imap_connect()
    if not conn:
        return []
    try:
        conn.login(email_addr, email_password)
        conn.select(IMAP_FOLDER)

        typ, data = conn.search(None, "UNSEEN")
        ids = data[0].split() if typ == "OK" else []
        if not ids:
            typ, data = conn.search(None, "ALL")
            ids = data[0].split() if typ == "OK" else []
        if not ids:
            return []

        ids = ids[-limit:]
        texts = []
        for msg_id in reversed(ids):
            typ, msg_data = conn.fetch(msg_id, "(BODY.PEEK[])")
            if typ != "OK":
                continue
            for item in msg_data:
                if isinstance(item, tuple):
                    msg = email.message_from_bytes(item[1])
                    text = _extract_text_from_message(msg)
                    if text:
                        texts.append(text)
        return texts
    except Exception:
        return []
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def _extract_verification_code(email_content: str):
    """从邮件内容提取 6 位验证码"""
    if not email_content:
        return None

    patterns = [
        r"Verification code:?\s*(\d{6})",
        r"code is\s*(\d{6})",
        r"代码为[:：]?\s*(\d{6})",
        r"验证码[:：]?\s*(\d{6})",
        r">\s*(\d{6})\s*<",
        r"(?<![#&])\b(\d{6})\b",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, email_content, re.IGNORECASE)
        for code in matches:
            if code == "177010":  # 已知误判
                continue
            return code
    return None


def wait_for_verification_email(email_addr: str, email_password: str, timeout: int = 120):
    """等待并提取 OpenAI 验证码"""
    start_time = time.time()

    while time.time() - start_time < timeout:
        texts = _imap_fetch_latest_texts(email_addr, email_password, limit=8)
        for content in texts:
            code = _extract_verification_code(content)
            if code:
                return code

        time.sleep(3)

    return None


def _random_name():
    first = random.choice([
        "James", "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia",
        "Lucas", "Mia", "Mason", "Isabella", "Logan", "Charlotte", "Alexander",
        "Amelia", "Benjamin", "Harper", "William", "Evelyn", "Henry", "Abigail",
        "Sebastian", "Emily", "Jack", "Elizabeth",
    ])
    last = random.choice([
        "Smith", "Johnson", "Brown", "Davis", "Wilson", "Moore", "Taylor",
        "Clark", "Hall", "Young", "Anderson", "Thomas", "Jackson", "White",
        "Harris", "Martin", "Thompson", "Garcia", "Robinson", "Lewis",
        "Walker", "Allen", "King", "Wright", "Scott", "Green",
    ])
    return f"{first} {last}"


def _random_birthdate():
    y = random.randint(1985, 2002)
    m = random.randint(1, 12)
    d = random.randint(1, 28)
    return f"{y}-{m:02d}-{d:02d}"


class ChatGPTRegister:
    BASE = "https://chatgpt.com"
    AUTH = "https://auth.openai.com"

    def __init__(self, proxy: str = None, openai_proxy: str = None, tag: str = ""):
        self.tag = tag  # 线程标识，用于日志
        self.last_http_step = None
        self.device_id = str(uuid.uuid4())
        self.auth_session_logging_id = str(uuid.uuid4())
        self.impersonate, self.chrome_major, self.chrome_full, self.ua, self.sec_ch_ua = _random_chrome_version()

        self.session = curl_requests.Session(impersonate=self.impersonate)

        self.proxy = proxy
        self.openai_proxy = openai_proxy if openai_proxy is not None else proxy
        if self.openai_proxy:
            self.session.proxies = {"http": self.openai_proxy, "https": self.openai_proxy}

        self.session.headers.update({
            "User-Agent": self.ua,
            "Accept-Language": random.choice([
                "en-US,en;q=0.9", "en-US,en;q=0.9,zh-CN;q=0.8",
                "en,en-US;q=0.9", "en-US,en;q=0.8",
            ]),
            "sec-ch-ua": self.sec_ch_ua, "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"', "sec-ch-ua-arch": '"x86"',
            "sec-ch-ua-bitness": '"64"',
            "sec-ch-ua-full-version": f'"{self.chrome_full}"',
            "sec-ch-ua-platform-version": f'"{random.randint(10, 15)}.0.0"',
        })

        self.session.cookies.set("oai-did", self.device_id, domain="chatgpt.com")
        self._callback_url = None

    def _log(self, step, method, url, status, body=None):
        prefix = f"[{self.tag}] " if self.tag else ""
        lines = [
            f"\n{'='*60}",
            f"{prefix}[Step] {step}",
            f"{prefix}[{method}] {url}",
            f"{prefix}[Status] {status}",
        ]
        if body:
            try:
                lines.append(f"{prefix}[Response] {json.dumps(body, indent=2, ensure_ascii=False)[:1000]}")
            except Exception:
                lines.append(f"{prefix}[Response] {str(body)[:1000]}")
        lines.append(f"{'='*60}")
        with _print_lock:
            print("\n".join(lines))
        if body is None:
            body_preview = ""
        else:
            try:
                body_preview = json.dumps(body, ensure_ascii=False)[:200]
            except Exception:
                body_preview = str(body)[:200]
        _append_log(
            "http_step",
            "http step finished",
            tag=self.tag,
            step=step,
            method=method,
            url=url,
            status=status,
            body_preview=body_preview,
        )
        self.last_http_step = {
            "step": step,
            "method": method,
            "url": url,
            "status": status,
            "body_preview": body_preview,
        }

    def _print(self, msg):
        prefix = f"[{self.tag}] " if self.tag else ""
        with _print_lock:
            print(f"{prefix}{msg}")

    # ==================== Mailu 邮箱 ====================

    def _create_mailu_session(self):
        """创建 Mailu API 请求会话"""
        session = curl_requests.Session()
        session.headers.update({
            "User-Agent": self.ua,
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        if self.proxy:
            session.proxies = {"http": self.proxy, "https": self.proxy}
        return session

    def create_temp_email(self):
        """创建 Mailu 邮箱，返回 (email, password)"""
        if not MAILU_API_TOKEN:
            raise Exception("MAILU_API_TOKEN 未设置，无法创建邮箱")

        chars = string.ascii_lowercase + string.digits
        length = random.randint(8, 13)
        email_local = "".join(random.choice(chars) for _ in range(length))
        email_addr = f"{email_local}@{MAIL_DOMAIN}"
        password = _generate_password()

        payload = {
            "email": email_addr,
            "raw_password": password,
            "quota_bytes": MAILBOX_QUOTA_BYTES,
            "enabled": True,
            "global_admin": False,
        }
        headers = {"Authorization": f"Bearer {MAILU_API_TOKEN}"}
        session = self._create_mailu_session()

        try:
            res = session.post(
                f"{MAILU_BASE_URL}/api/v1/user",
                json=payload,
                headers=headers,
                timeout=30,
                impersonate=self.impersonate,
            )
            if res.status_code not in [200, 201]:
                raise Exception(f"创建邮箱失败: {res.status_code} - {res.text[:200]}")
            return email_addr, password
        except Exception as e:
            raise Exception(f"Mailu 创建邮箱失败: {e}")

    def _fetch_recent_mail_texts(self, email_addr: str, email_password: str, limit: int = 8):
        return _imap_fetch_latest_texts(email_addr, email_password, limit=limit)

    def _extract_verification_code(self, email_content: str):
        """从邮件内容提取 6 位验证码"""
        if not email_content:
            return None

        patterns = [
            r"Verification code:?\s*(\d{6})",
            r"code is\s*(\d{6})",
            r"代码为[:：]?\s*(\d{6})",
            r"验证码[:：]?\s*(\d{6})",
            r">\s*(\d{6})\s*<",
            r"(?<![#&])\b(\d{6})\b",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, email_content, re.IGNORECASE)
            for code in matches:
                if code == "177010":  # 已知误判
                    continue
                return code
        return None

    def wait_for_verification_email(self, email_addr: str, email_password: str, timeout: int = 120):
        """等待并提取 OpenAI 验证码"""
        self._print(f"[OTP] 等待验证码邮件 (最多 {timeout}s)...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            texts = self._fetch_recent_mail_texts(email_addr, email_password, limit=8)
            for content in texts:
                code = self._extract_verification_code(content)
                if code:
                    self._print(f"[OTP] 验证码: {code}")
                    return code

            elapsed = int(time.time() - start_time)
            self._print(f"[OTP] 等待中... ({elapsed}s/{timeout}s)")
            time.sleep(3)

        self._print(f"[OTP] 超时 ({timeout}s)")
        return None

    def wait_for_otp_rounds(self, email_addr: str, email_password: str, rounds=None):
        """按多轮等待验证码（默认 5 分钟 + 10 分钟）"""
        rounds = rounds or OTP_WAIT_ROUNDS
        for idx, timeout in enumerate(rounds, start=1):
            if idx > 1:
                self._print(f"[OTP] 进入第 {idx} 轮等待 ({timeout}s)...")
            code = self.wait_for_verification_email(email_addr, email_password, timeout=timeout)
            if code:
                return code
        return None

    # ==================== 注册流程 ====================

    def visit_homepage(self):
        url = f"{self.BASE}/"
        r = self.session.get(url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
        }, allow_redirects=True)
        self._log("0. Visit homepage", "GET", url, r.status_code,
                   {"cookies_count": len(self.session.cookies)})

    def get_csrf(self) -> str:
        url = f"{self.BASE}/api/auth/csrf"
        r = self.session.get(url, headers={"Accept": "application/json", "Referer": f"{self.BASE}/"})
        data = r.json()
        token = data.get("csrfToken", "")
        self._log("1. Get CSRF", "GET", url, r.status_code, data)
        if not token:
            raise Exception("Failed to get CSRF token")
        return token

    def signin(self, email: str, csrf: str) -> str:
        url = f"{self.BASE}/api/auth/signin/openai"
        params = {
            "prompt": "login", "ext-oai-did": self.device_id,
            "auth_session_logging_id": self.auth_session_logging_id,
            "screen_hint": "login_or_signup", "login_hint": email,
        }
        form_data = {"callbackUrl": f"{self.BASE}/", "csrfToken": csrf, "json": "true"}
        r = self.session.post(url, params=params, data=form_data, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json", "Referer": f"{self.BASE}/", "Origin": self.BASE,
        })
        data = r.json()
        authorize_url = data.get("url", "")
        self._log("2. Signin", "POST", url, r.status_code, data)
        if not authorize_url:
            raise Exception("Failed to get authorize URL")
        return authorize_url

    def authorize(self, url: str) -> str:
        r = self.session.get(url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{self.BASE}/", "Upgrade-Insecure-Requests": "1",
        }, allow_redirects=True)
        final_url = str(r.url)
        self._log("3. Authorize", "GET", url, r.status_code, {"final_url": final_url})
        return final_url

    def register(self, email: str, password: str):
        url = f"{self.AUTH}/api/accounts/user/register"
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                    "Referer": f"{self.AUTH}/create-account/password", "Origin": self.AUTH}
        headers.update(_make_trace_headers())
        r = self.session.post(url, json={"username": email, "password": password}, headers=headers)
        try: data = r.json()
        except Exception: data = {"text": r.text[:500]}
        self._log("4. Register", "POST", url, r.status_code, data)
        return r.status_code, data

    def send_otp(self):
        url = f"{self.AUTH}/api/accounts/email-otp/send"
        r = self.session.get(url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{self.AUTH}/create-account/password", "Upgrade-Insecure-Requests": "1",
        }, allow_redirects=True)
        try: data = r.json()
        except Exception: data = {"final_url": str(r.url), "status": r.status_code}
        self._log("5. Send OTP", "GET", url, r.status_code, data)
        return r.status_code, data

    def validate_otp(self, code: str):
        url = f"{self.AUTH}/api/accounts/email-otp/validate"
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                    "Referer": f"{self.AUTH}/email-verification", "Origin": self.AUTH}
        headers.update(_make_trace_headers())
        r = self.session.post(url, json={"code": code}, headers=headers)
        try: data = r.json()
        except Exception: data = {"text": r.text[:500]}
        self._log("6. Validate OTP", "POST", url, r.status_code, data)
        return r.status_code, data

    def create_account(self, name: str, birthdate: str):
        url = f"{self.AUTH}/api/accounts/create_account"
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                    "Referer": f"{self.AUTH}/about-you", "Origin": self.AUTH}
        headers.update(_make_trace_headers())
        r = self.session.post(url, json={"name": name, "birthdate": birthdate}, headers=headers)
        try: data = r.json()
        except Exception: data = {"text": r.text[:500]}
        self._log("7. Create Account", "POST", url, r.status_code, data)
        if isinstance(data, dict):
            cb = data.get("continue_url") or data.get("url") or data.get("redirect_url")
            if cb:
                self._callback_url = cb
        return r.status_code, data

    def callback(self, url: str = None):
        if not url:
            url = self._callback_url
        if not url:
            self._print("[!] No callback URL, skipping.")
            return None, None
        r = self.session.get(url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
        }, allow_redirects=True)
        self._log("8. Callback", "GET", url, r.status_code, {"final_url": str(r.url)})
        return r.status_code, {"final_url": str(r.url)}

    # ==================== 自动注册主流程 ====================

    def run_register(self, email, password, name, birthdate, mail_password):
        """使用 Mailu 的注册流程"""
        self.visit_homepage()
        _random_delay(0.3, 0.8)
        csrf = self.get_csrf()
        _random_delay(0.2, 0.5)
        auth_url = self.signin(email, csrf)
        _random_delay(0.3, 0.8)

        final_url = self.authorize(auth_url)
        final_path = urlparse(final_url).path
        _random_delay(0.3, 0.8)

        self._print(f"Authorize → {final_path}")

        need_otp = False

        if "create-account/password" in final_path:
            self._print("全新注册流程")
            _random_delay(0.5, 1.0)
            status, data = self.register(email, password)
            if status != 200:
                raise Exception(f"Register 失败 ({status}): {data}")
            # register 之后可能还需要 send_otp（全新注册流程中 OTP 不一定在 authorize 时发送）
            _random_delay(0.3, 0.8)
            self.send_otp()
            need_otp = True
        elif "email-verification" in final_path or "email-otp" in final_path:
            self._print("跳到 OTP 验证阶段 (authorize 已触发 OTP，不再重复发送)")
            # 不调用 send_otp()，因为 authorize 重定向到 email-verification 时服务器已发送 OTP
            need_otp = True
        elif "about-you" in final_path:
            self._print("跳到填写信息阶段")
            _random_delay(0.5, 1.0)
            self.create_account(name, birthdate)
            _random_delay(0.3, 0.5)
            self.callback()
            return True
        elif "callback" in final_path or "chatgpt.com" in final_url:
            self._print("账号已完成注册")
            return True
        else:
            self._print(f"未知跳转: {final_url}")
            self.register(email, password)
            self.send_otp()
            need_otp = True

        if need_otp:
            # 使用 Mailu 等待验证码
            otp_code = self.wait_for_otp_rounds(email, mail_password)
            if not otp_code:
                raise Exception("未能获取验证码")

            _random_delay(0.3, 0.8)
            status, data = self.validate_otp(otp_code)
            if status != 200:
                self._print("验证码失败，重试...")
                self.send_otp()
                _random_delay(1.0, 2.0)
                otp_code = self.wait_for_otp_rounds(email, mail_password)
                if not otp_code:
                    raise Exception("重试后仍未获取验证码")
                _random_delay(0.3, 0.8)
                status, data = self.validate_otp(otp_code)
                if status != 200:
                    raise Exception(f"验证码失败 ({status}): {data}")

        _random_delay(0.5, 1.5)
        status, data = self.create_account(name, birthdate)
        if status != 200:
            raise Exception(f"Create account 失败 ({status}): {data}")
        _random_delay(0.2, 0.5)
        self.callback()
        return True

    def _decode_oauth_session_cookie(self):
        jar = getattr(self.session.cookies, "jar", None)
        if jar is not None:
            cookie_items = list(jar)
        else:
            cookie_items = []

        for c in cookie_items:
            name = getattr(c, "name", "") or ""
            if "oai-client-auth-session" not in name:
                continue

            raw_val = (getattr(c, "value", "") or "").strip()
            if not raw_val:
                continue

            candidates = [raw_val]
            try:
                from urllib.parse import unquote

                decoded = unquote(raw_val)
                if decoded != raw_val:
                    candidates.append(decoded)
            except Exception:
                pass

            for val in candidates:
                try:
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]

                    part = val.split(".")[0] if "." in val else val
                    pad = 4 - len(part) % 4
                    if pad != 4:
                        part += "=" * pad
                    raw = base64.urlsafe_b64decode(part)
                    data = json.loads(raw.decode("utf-8"))
                    if isinstance(data, dict):
                        return data
                except Exception:
                    continue
        return None

    def _oauth_allow_redirect_extract_code(self, url: str, referer: str = None):
        code = _extract_code_from_url(url)
        if code:
            self._print("[OAuth] allow_redirect 命中初始 URL code")
            return code

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": self.ua,
        }
        if referer:
            headers["Referer"] = referer

        try:
            resp = self.session.get(
                url,
                headers=headers,
                allow_redirects=True,
                timeout=30,
                impersonate=self.impersonate,
            )
            final_url = str(resp.url)
            code = _extract_code_from_url(final_url)
            if code:
                self._print("[OAuth] allow_redirect 命中最终 URL code")
                return code

            for r in getattr(resp, "history", []) or []:
                loc = r.headers.get("Location", "")
                code = _extract_code_from_url(loc)
                if code:
                    self._print("[OAuth] allow_redirect 命中 history Location code")
                    return code
                code = _extract_code_from_url(str(r.url))
                if code:
                    self._print("[OAuth] allow_redirect 命中 history URL code")
                    return code
        except Exception as e:
            maybe_localhost = re.search(r'(https?://localhost[^\s\'\"]+)', str(e))
            if maybe_localhost:
                code = _extract_code_from_url(maybe_localhost.group(1))
                if code:
                    self._print("[OAuth] allow_redirect 从 localhost 异常提取 code")
                    return code
            self._print(f"[OAuth] allow_redirect 异常: {e}")

        return None

    def _oauth_follow_for_code(self, start_url: str, referer: str = None, max_hops: int = 16):
        code = _extract_code_from_url(start_url)
        if code:
            self._print("[OAuth] follow[0] 命中初始 URL code")
            return code, start_url

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": self.ua,
        }
        if referer:
            headers["Referer"] = referer

        current_url = start_url
        last_url = start_url

        for hop in range(max_hops):
            try:
                resp = self.session.get(
                    current_url,
                    headers=headers,
                    allow_redirects=False,
                    timeout=30,
                    impersonate=self.impersonate,
                )
            except Exception as e:
                maybe_localhost = re.search(r'(https?://localhost[^\s\'\"]+)', str(e))
                if maybe_localhost:
                    code = _extract_code_from_url(maybe_localhost.group(1))
                    if code:
                        self._print(f"[OAuth] follow[{hop + 1}] 命中 localhost 回调")
                        return code, maybe_localhost.group(1)
                self._print(f"[OAuth] follow[{hop + 1}] 请求异常: {e}")
                return None, last_url

            last_url = str(resp.url)
            self._print(f"[OAuth] follow[{hop + 1}] {resp.status_code} {last_url[:140]}")
            code = _extract_code_from_url(last_url)
            if code:
                return code, last_url

            if resp.status_code in (301, 302, 303, 307, 308):
                loc = resp.headers.get("Location", "")
                if not loc:
                    return None, last_url
                if loc.startswith("/"):
                    loc = f"{OAUTH_ISSUER}{loc}"
                code = _extract_code_from_url(loc)
                if code:
                    return code, loc
                current_url = loc
                headers["Referer"] = last_url
                continue

            return None, last_url

        return None, last_url

    def _oauth_submit_workspace_and_org(self, consent_url: str):
        session_data = self._decode_oauth_session_cookie()
        if not session_data:
            jar = getattr(self.session.cookies, "jar", None)
            if jar is not None:
                cookie_names = [getattr(c, "name", "") for c in list(jar)]
            else:
                cookie_names = list(self.session.cookies.keys())
            self._print(f"[OAuth] 无法解码 oai-client-auth-session, cookies={cookie_names[:12]}")
            return None

        workspaces = session_data.get("workspaces", [])
        if not workspaces:
            self._print("[OAuth] session 中没有 workspace 信息")
            return None

        workspace_id = (workspaces[0] or {}).get("id")
        if not workspace_id:
            self._print("[OAuth] workspace_id 为空")
            return None

        h = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": OAUTH_ISSUER,
            "Referer": consent_url,
            "User-Agent": self.ua,
            "oai-device-id": self.device_id,
        }
        h.update(_make_trace_headers())

        resp = self.session.post(
            f"{OAUTH_ISSUER}/api/accounts/workspace/select",
            json={"workspace_id": workspace_id},
            headers=h,
            allow_redirects=False,
            timeout=30,
            impersonate=self.impersonate,
        )
        self._print(f"[OAuth] workspace/select -> {resp.status_code}")

        if resp.status_code in (301, 302, 303, 307, 308):
            loc = resp.headers.get("Location", "")
            if loc.startswith("/"):
                loc = f"{OAUTH_ISSUER}{loc}"
            code = _extract_code_from_url(loc)
            if code:
                return code
            code, _ = self._oauth_follow_for_code(loc, referer=consent_url)
            if not code:
                code = self._oauth_allow_redirect_extract_code(loc, referer=consent_url)
            return code

        if resp.status_code != 200:
            self._print(f"[OAuth] workspace/select 失败: {resp.status_code}")
            return None

        try:
            ws_data = resp.json()
        except Exception:
            self._print("[OAuth] workspace/select 响应不是 JSON")
            return None

        ws_next = ws_data.get("continue_url", "")
        orgs = ws_data.get("data", {}).get("orgs", [])
        ws_page = (ws_data.get("page") or {}).get("type", "")
        self._print(f"[OAuth] workspace/select page={ws_page or '-'} next={(ws_next or '-')[:140]}")

        org_id = None
        project_id = None
        if orgs:
            org_id = (orgs[0] or {}).get("id")
            projects = (orgs[0] or {}).get("projects", [])
            if projects:
                project_id = (projects[0] or {}).get("id")

        if org_id:
            org_body = {"org_id": org_id}
            if project_id:
                org_body["project_id"] = project_id

            h_org = dict(h)
            if ws_next:
                h_org["Referer"] = ws_next if ws_next.startswith("http") else f"{OAUTH_ISSUER}{ws_next}"

            resp_org = self.session.post(
                f"{OAUTH_ISSUER}/api/accounts/organization/select",
                json=org_body,
                headers=h_org,
                allow_redirects=False,
                timeout=30,
                impersonate=self.impersonate,
            )
            self._print(f"[OAuth] organization/select -> {resp_org.status_code}")
            if resp_org.status_code in (301, 302, 303, 307, 308):
                loc = resp_org.headers.get("Location", "")
                if loc.startswith("/"):
                    loc = f"{OAUTH_ISSUER}{loc}"
                code = _extract_code_from_url(loc)
                if code:
                    return code
                code, _ = self._oauth_follow_for_code(loc, referer=h_org.get("Referer"))
                if not code:
                    code = self._oauth_allow_redirect_extract_code(loc, referer=h_org.get("Referer"))
                return code

            if resp_org.status_code == 200:
                try:
                    org_data = resp_org.json()
                except Exception:
                    self._print("[OAuth] organization/select 响应不是 JSON")
                    return None

                org_next = org_data.get("continue_url", "")
                org_page = (org_data.get("page") or {}).get("type", "")
                self._print(f"[OAuth] organization/select page={org_page or '-'} next={(org_next or '-')[:140]}")
                if org_next:
                    if org_next.startswith("/"):
                        org_next = f"{OAUTH_ISSUER}{org_next}"
                    code, _ = self._oauth_follow_for_code(org_next, referer=h_org.get("Referer"))
                    if not code:
                        code = self._oauth_allow_redirect_extract_code(org_next, referer=h_org.get("Referer"))
                    return code

        if ws_next:
            if ws_next.startswith("/"):
                ws_next = f"{OAUTH_ISSUER}{ws_next}"
            code, _ = self._oauth_follow_for_code(ws_next, referer=consent_url)
            if not code:
                code = self._oauth_allow_redirect_extract_code(ws_next, referer=consent_url)
            return code

        return None

    def perform_codex_oauth_login_http(self, email: str, password: str, mail_password: str = None):
        self._print("[OAuth] 开始执行 Codex OAuth 纯协议流程...")

        # 兼容两种 domain 形式，确保 auth 域也带 oai-did
        self.session.cookies.set("oai-did", self.device_id, domain=".auth.openai.com")
        self.session.cookies.set("oai-did", self.device_id, domain="auth.openai.com")

        code_verifier, code_challenge = _generate_pkce()
        state = secrets.token_urlsafe(24)

        authorize_params = {
            "response_type": "code",
            "client_id": OAUTH_CLIENT_ID,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "scope": "openid profile email offline_access",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        authorize_url = f"{OAUTH_ISSUER}/oauth/authorize?{urlencode(authorize_params)}"

        def _oauth_json_headers(referer: str):
            h = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": OAUTH_ISSUER,
                "Referer": referer,
                "User-Agent": self.ua,
                "oai-device-id": self.device_id,
            }
            h.update(_make_trace_headers())
            return h

        def _cookie_snapshot(label: str, resp=None):
            try:
                cookies = []
                for c in self.session.cookies:
                    name = getattr(c, "name", "") or ""
                    domain = getattr(c, "domain", "") or ""
                    if name:
                        cookies.append(f"{name}@{domain}")
                cookies = sorted(set(cookies))
                has_login = any(item.startswith("login_session@") or item.startswith("login_session") for item in cookies)
                _append_log(
                    "oauth_cookie_snapshot",
                    "oauth cookie snapshot",
                    label=label,
                    cookie_count=len(cookies),
                    has_login_session=has_login,
                    cookies=cookies[:60],
                )
                if resp is not None:
                    set_cookie = resp.headers.get("set-cookie", "")
                    if set_cookie:
                        _append_log(
                            "oauth_set_cookie",
                            "oauth set-cookie header seen",
                            label=label,
                            header=set_cookie[:400],
                        )
            except Exception:
                pass

        def _bootstrap_oauth_session():
            self._print("[OAuth] 1/7 GET /oauth/authorize")
            try:
                r = self.session.get(
                    authorize_url,
                    headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Referer": f"{self.BASE}/",
                        "Upgrade-Insecure-Requests": "1",
                        "User-Agent": self.ua,
                    },
                    allow_redirects=True,
                    timeout=30,
                    impersonate=self.impersonate,
                )
            except Exception as e:
                self._print(f"[OAuth] /oauth/authorize 异常: {e}")
                return False, ""

            final_url = str(r.url)
            redirects = len(getattr(r, "history", []) or [])
            self._print(f"[OAuth] /oauth/authorize -> {r.status_code}, final={(final_url or '-')[:140]}, redirects={redirects}")
            _cookie_snapshot("after_oauth_authorize", r)

            has_login = any(getattr(c, "name", "") == "login_session" for c in self.session.cookies)
            self._print(f"[OAuth] login_session: {'已获取' if has_login else '未获取'}")

            if not has_login:
                self._print("[OAuth] 未拿到 login_session，尝试访问 oauth2 auth 入口")
                oauth2_url = f"{OAUTH_ISSUER}/api/oauth/oauth2/auth"
                try:
                    r2 = self.session.get(
                        oauth2_url,
                        headers={
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "Referer": authorize_url,
                            "Upgrade-Insecure-Requests": "1",
                            "User-Agent": self.ua,
                        },
                        params=authorize_params,
                        allow_redirects=True,
                        timeout=30,
                        impersonate=self.impersonate,
                    )
                    final_url = str(r2.url)
                    redirects2 = len(getattr(r2, "history", []) or [])
                    self._print(f"[OAuth] /api/oauth/oauth2/auth -> {r2.status_code}, final={(final_url or '-')[:140]}, redirects={redirects2}")
                    _cookie_snapshot("after_oauth2_auth", r2)
                except Exception as e:
                    self._print(f"[OAuth] /api/oauth/oauth2/auth 异常: {e}")

                has_login = any(getattr(c, "name", "") == "login_session" for c in self.session.cookies)
                self._print(f"[OAuth] login_session(重试): {'已获取' if has_login else '未获取'}")

            if not has_login:
                self._print("[OAuth] login_session 仍缺失，尝试 /api/accounts/authorize 引导")
                auth_params = dict(authorize_params)
                auth_params.update({
                    "prompt": "login",
                    "screen_hint": "login",
                    "device_id": self.device_id,
                    "ext-oai-did": self.device_id,
                    "auth_session_logging_id": self.auth_session_logging_id,
                    "audience": "https://api.openai.com/v1",
                })
                try:
                    r3 = self.session.get(
                        f"{OAUTH_ISSUER}/api/accounts/authorize?{urlencode(auth_params)}",
                        headers={
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "Referer": authorize_url,
                            "Upgrade-Insecure-Requests": "1",
                            "User-Agent": self.ua,
                        },
                        allow_redirects=True,
                        timeout=30,
                        impersonate=self.impersonate,
                    )
                    final_url = str(r3.url)
                    redirects3 = len(getattr(r3, "history", []) or [])
                    self._print(f"[OAuth] /api/accounts/authorize -> {r3.status_code}, final={(final_url or '-')[:140]}, redirects={redirects3}")
                    _cookie_snapshot("after_api_accounts_authorize", r3)
                except Exception as e:
                    self._print(f"[OAuth] /api/accounts/authorize 异常: {e}")

                has_login = any(getattr(c, "name", "") == "login_session" for c in self.session.cookies)
                self._print(f"[OAuth] login_session(最终): {'已获取' if has_login else '未获取'}")

            return has_login, final_url

        def _post_authorize_continue(referer_url: str):
            sentinel_authorize = build_sentinel_token(
                self.session,
                self.device_id,
                flow="authorize_continue",
                user_agent=self.ua,
                sec_ch_ua=self.sec_ch_ua,
                impersonate=self.impersonate,
            )
            if not sentinel_authorize:
                self._print("[OAuth] authorize_continue 的 sentinel token 获取失败")
                return None

            headers_continue = _oauth_json_headers(referer_url)
            headers_continue["openai-sentinel-token"] = sentinel_authorize

            try:
                return self.session.post(
                    f"{OAUTH_ISSUER}/api/accounts/authorize/continue",
                    json={"username": {"kind": "email", "value": email}},
                    headers=headers_continue,
                    timeout=30,
                    allow_redirects=False,
                    impersonate=self.impersonate,
                )
            except Exception as e:
                self._print(f"[OAuth] authorize/continue 异常: {e}")
                return None

        has_login_session, authorize_final_url = _bootstrap_oauth_session()
        if not authorize_final_url:
            return None

        continue_referer = authorize_final_url if authorize_final_url.startswith(OAUTH_ISSUER) else f"{OAUTH_ISSUER}/log-in"

        self._print("[OAuth] 2/7 POST /api/accounts/authorize/continue")
        resp_continue = _post_authorize_continue(continue_referer)
        if resp_continue is None:
            return None

        self._print(f"[OAuth] /authorize/continue -> {resp_continue.status_code}")
        if resp_continue.status_code == 400 and "invalid_auth_step" in (resp_continue.text or ""):
            self._print("[OAuth] invalid_auth_step，重新 bootstrap 后重试一次")
            has_login_session, authorize_final_url = _bootstrap_oauth_session()
            if not authorize_final_url:
                return None
            continue_referer = authorize_final_url if authorize_final_url.startswith(OAUTH_ISSUER) else f"{OAUTH_ISSUER}/log-in"
            resp_continue = _post_authorize_continue(continue_referer)
            if resp_continue is None:
                return None
            self._print(f"[OAuth] /authorize/continue(重试) -> {resp_continue.status_code}")

        if resp_continue.status_code != 200:
            self._print(f"[OAuth] 邮箱提交失败: {resp_continue.text[:180]}")
            return None

        try:
            continue_data = resp_continue.json()
        except Exception:
            self._print("[OAuth] authorize/continue 响应解析失败")
            return None

        continue_url = continue_data.get("continue_url", "")
        page_type = (continue_data.get("page") or {}).get("type", "")
        self._print(f"[OAuth] continue page={page_type or '-'} next={(continue_url or '-')[:140]}")

        resp_verify = None
        for attempt in range(1, 3):
            self._print("[OAuth] 3/7 POST /api/accounts/password/verify")
            sentinel_pwd = build_sentinel_token(
                self.session,
                self.device_id,
                flow="password_verify",
                user_agent=self.ua,
                sec_ch_ua=self.sec_ch_ua,
                impersonate=self.impersonate,
            )
            if not sentinel_pwd:
                self._print("[OAuth] password_verify 的 sentinel token 获取失败")
                return None

            headers_verify = _oauth_json_headers(f"{OAUTH_ISSUER}/log-in/password")
            headers_verify["openai-sentinel-token"] = sentinel_pwd

            try:
                resp_verify = self.session.post(
                    f"{OAUTH_ISSUER}/api/accounts/password/verify",
                    json={"password": password},
                    headers=headers_verify,
                    timeout=30,
                    allow_redirects=False,
                    impersonate=self.impersonate,
                )
            except Exception as e:
                self._print(f"[OAuth] password/verify 异常: {e}")
                return None

            self._print(f"[OAuth] /password/verify -> {resp_verify.status_code}")
            if resp_verify.status_code == 200:
                break

            self._print(f"[OAuth] 密码校验失败: {resp_verify.text[:180]}")
            if resp_verify.status_code == 401 and attempt == 1:
                self._print("[OAuth] 401，尝试重新 bootstrap 并重试一次")
                has_login_session, authorize_final_url = _bootstrap_oauth_session()
                if not authorize_final_url:
                    return None
                continue_referer = authorize_final_url if authorize_final_url.startswith(OAUTH_ISSUER) else f"{OAUTH_ISSUER}/log-in"
                resp_continue = _post_authorize_continue(continue_referer)
                if resp_continue is None:
                    return None
                self._print(f"[OAuth] /authorize/continue(重试后) -> {resp_continue.status_code}")
                if resp_continue.status_code != 200:
                    self._print(f"[OAuth] 邮箱提交失败(重试后): {resp_continue.text[:180]}")
                    return None
                try:
                    continue_data = resp_continue.json()
                except Exception:
                    self._print("[OAuth] authorize/continue 响应解析失败(重试后)")
                    return None
                continue_url = continue_data.get("continue_url", "")
                page_type = (continue_data.get("page") or {}).get("type", "")
                self._print(f"[OAuth] continue page(重试)={page_type or '-'} next={(continue_url or '-')[:140]}")
                continue
            return None

        if resp_verify is None or resp_verify.status_code != 200:
            return None

        try:
            verify_data = resp_verify.json()
        except Exception:
            self._print("[OAuth] password/verify 响应解析失败")
            return None

        continue_url = verify_data.get("continue_url", "") or continue_url
        page_type = (verify_data.get("page") or {}).get("type", "") or page_type
        self._print(f"[OAuth] verify page={page_type or '-'} next={(continue_url or '-')[:140]}")

        need_oauth_otp = (
            page_type == "email_otp_verification"
            or "email-verification" in (continue_url or "")
            or "email-otp" in (continue_url or "")
        )

        if need_oauth_otp:
            self._print("[OAuth] 4/7 检测到邮箱 OTP 验证")
            if not mail_password:
                self._print("[OAuth] OAuth 阶段需要邮箱 OTP，但未提供邮箱密码")
                return None

            headers_otp = _oauth_json_headers(f"{OAUTH_ISSUER}/email-verification")
            tried_codes = set()
            otp_success = False
            for round_idx, round_timeout in enumerate(OTP_WAIT_ROUNDS, start=1):
                round_deadline = time.time() + round_timeout
                if round_idx > 1:
                    self._print(f"[OAuth] 进入第 {round_idx} 轮等待 ({round_timeout}s)...")

                while time.time() < round_deadline and not otp_success:
                    candidate_codes = []

                    texts = self._fetch_recent_mail_texts(email, mail_password, limit=12)
                    for content in texts:
                        code = self._extract_verification_code(content)
                        if code and code not in tried_codes:
                            candidate_codes.append(code)

                    if not candidate_codes:
                        elapsed = int(round_timeout - max(0, round_deadline - time.time()))
                        self._print(f"[OAuth] OTP 等待中... ({elapsed}s/{round_timeout}s)")
                        time.sleep(2)
                        continue

                    for otp_code in candidate_codes:
                        tried_codes.add(otp_code)
                        self._print(f"[OAuth] 尝试 OTP: {otp_code}")
                        try:
                            resp_otp = self.session.post(
                                f"{OAUTH_ISSUER}/api/accounts/email-otp/validate",
                                json={"code": otp_code},
                                headers=headers_otp,
                                timeout=30,
                                allow_redirects=False,
                                impersonate=self.impersonate,
                            )
                        except Exception as e:
                            self._print(f"[OAuth] email-otp/validate 异常: {e}")
                            continue

                        self._print(f"[OAuth] /email-otp/validate -> {resp_otp.status_code}")
                        if resp_otp.status_code != 200:
                            self._print(f"[OAuth] OTP 无效，继续尝试下一条: {resp_otp.text[:160]}")
                            continue

                        try:
                            otp_data = resp_otp.json()
                        except Exception:
                            self._print("[OAuth] email-otp/validate 响应解析失败")
                            continue

                        continue_url = otp_data.get("continue_url", "") or continue_url
                        page_type = (otp_data.get("page") or {}).get("type", "") or page_type
                        self._print(f"[OAuth] OTP 验证通过 page={page_type or '-'} next={(continue_url or '-')[:140]}")
                        otp_success = True
                        break

                    if not otp_success:
                        time.sleep(2)

                if otp_success:
                    break

            if not otp_success:
                self._print(f"[OAuth] OAuth 阶段 OTP 验证失败，已尝试 {len(tried_codes)} 个验证码")
                return None

        code = None
        consent_url = continue_url
        if consent_url and consent_url.startswith("/"):
            consent_url = f"{OAUTH_ISSUER}{consent_url}"

        if not consent_url and "consent" in page_type:
            consent_url = f"{OAUTH_ISSUER}/sign-in-with-chatgpt/codex/consent"

        if consent_url:
            code = _extract_code_from_url(consent_url)

        if not code and consent_url:
            self._print("[OAuth] 5/7 跟随 continue_url 提取 code")
            code, _ = self._oauth_follow_for_code(consent_url, referer=f"{OAUTH_ISSUER}/log-in/password")

        consent_hint = (
            ("consent" in (consent_url or ""))
            or ("sign-in-with-chatgpt" in (consent_url or ""))
            or ("workspace" in (consent_url or ""))
            or ("organization" in (consent_url or ""))
            or ("consent" in page_type)
            or ("organization" in page_type)
        )

        if not code and consent_hint:
            if not consent_url:
                consent_url = f"{OAUTH_ISSUER}/sign-in-with-chatgpt/codex/consent"
            self._print("[OAuth] 6/7 执行 workspace/org 选择")
            code = self._oauth_submit_workspace_and_org(consent_url)

        if not code:
            fallback_consent = f"{OAUTH_ISSUER}/sign-in-with-chatgpt/codex/consent"
            self._print("[OAuth] 6/7 回退 consent 路径重试")
            code = self._oauth_submit_workspace_and_org(fallback_consent)
            if not code:
                code, _ = self._oauth_follow_for_code(fallback_consent, referer=f"{OAUTH_ISSUER}/log-in/password")

        if not code:
            self._print("[OAuth] 未获取到 authorization code")
            return None

        self._print("[OAuth] 7/7 POST /oauth/token")
        token_resp = self.session.post(
            f"{OAUTH_ISSUER}/oauth/token",
            headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": self.ua},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": OAUTH_REDIRECT_URI,
                "client_id": OAUTH_CLIENT_ID,
                "code_verifier": code_verifier,
            },
            timeout=60,
            impersonate=self.impersonate,
        )
        self._print(f"[OAuth] /oauth/token -> {token_resp.status_code}")

        if token_resp.status_code != 200:
            self._print(f"[OAuth] token 交换失败: {token_resp.status_code} {token_resp.text[:200]}")
            return None

        try:
            data = token_resp.json()
        except Exception:
            self._print("[OAuth] token 响应解析失败")
            return None

        if not data.get("access_token"):
            self._print("[OAuth] token 响应缺少 access_token")
            return None

        self._print("[OAuth] Codex Token 获取成功")
        return data


# ==================== 并发批量注册 ====================

def _register_one(idx, total, proxy, openai_proxy, output_file):
    """单个注册任务 (在线程中运行) - 使用 Mailu 邮箱"""
    reg = None
    email = None
    email_pwd = None
    try:
        _append_log(
            "register_start",
            "register task started",
            index=idx,
            total=total,
            proxy=proxy,
            openai_proxy=openai_proxy,
            output_file=output_file,
        )
        reg = ChatGPTRegister(proxy=proxy, openai_proxy=openai_proxy, tag=f"{idx}")

        # 1. 创建 Mailu 邮箱
        reg._print("[Mailu] 创建邮箱...")
        email, email_pwd = reg.create_temp_email()
        _append_log(
            "mailu_create_ok",
            "mailbox created",
            index=idx,
            email=email,
        )
        tag = email.split("@")[0]
        reg.tag = tag  # 更新 tag

        chatgpt_password = _generate_password()
        name = _random_name()
        birthdate = _random_birthdate()

        with _print_lock:
            print(f"\n{'='*60}")
            print(f"  [{idx}/{total}] 注册: {email}")
            print(f"  ChatGPT密码: {chatgpt_password}")
            print(f"  邮箱密码: {email_pwd}")
            print(f"  姓名: {name} | 生日: {birthdate}")
            print(f"{'='*60}")

        # 2. 执行注册流程
        reg.run_register(email, chatgpt_password, name, birthdate, email_pwd)
        _append_log(
            "register_flow_ok",
            "registration flow completed",
            index=idx,
            email=email,
        )

        # 3. OAuth（可选）
        oauth_ok = True
        if ENABLE_OAUTH:
            reg._print("[OAuth] 开始获取 Codex Token...")
            tokens = reg.perform_codex_oauth_login_http(email, chatgpt_password, mail_password=email_pwd)
            oauth_ok = bool(tokens and tokens.get("access_token"))
            if oauth_ok:
                _save_codex_tokens(email, tokens)
                reg._print("[OAuth] Token 已保存")
                _append_log(
                    "oauth_token_ok",
                    "oauth token acquired",
                    index=idx,
                    email=email,
                )
            else:
                msg = "OAuth 获取失败"
                if OAUTH_REQUIRED:
                    _append_log(
                        "oauth_token_fail",
                        "oauth token required but failed",
                        index=idx,
                        email=email,
                    )
                    raise Exception(f"{msg}（oauth_required=true）")
                reg._print(f"[OAuth] {msg}（按配置继续）")
                _append_log(
                    "oauth_token_fail",
                    "oauth token failed but continued",
                    index=idx,
                    email=email,
                )

        # 4. 线程安全写入结果
        with _file_lock:
            with open(output_file, "a", encoding="utf-8") as out:
                out.write(f"{email}----{chatgpt_password}----{email_pwd}----oauth={'ok' if oauth_ok else 'fail'}\n")

        with _print_lock:
            print(f"\n[OK] [{tag}] {email} 注册成功!")
        _append_log(
            "register_success",
            "registration succeeded",
            index=idx,
            email=email,
            oauth_ok=oauth_ok,
        )
        _send_success_notification(idx, total, email)
        return True, email, None

    except Exception as e:
        error_msg = str(e)
        risk_flag = _is_risk_error(error_msg)
        if risk_flag:
            _increment_risk_counter()
        with _print_lock:
            print(f"\n[FAIL] [{idx}] 注册失败: {error_msg}")
            traceback.print_exc()
        _append_log(
            "register_fail",
            "registration failed",
            index=idx,
            error=error_msg,
            risk=risk_flag,
        )
        step_info = reg.last_http_step if reg else None
        _send_error_notification(idx, total, email, error_msg, step_info=step_info)
        return False, None, error_msg


def run_batch(total_accounts: int = DEFAULT_TOTAL_ACCOUNTS, output_file="registered_accounts.txt",
              max_workers=1, proxy=None, openai_proxy=None):
    """并发批量注册 - Mailu 邮箱版"""

    if not MAILU_API_TOKEN:
        print("❌ 错误: 未设置 MAILU_API_TOKEN 环境变量")
        print("   请设置: export MAILU_API_TOKEN='your_api_key_here'")
        print("   或: set MAILU_API_TOKEN=your_api_key_here (Windows)")
        _append_log(
            "batch_abort",
            "missing MAILU_API_TOKEN",
            total_accounts=total_accounts,
            max_workers=max_workers,
        )
        return 0, 0

    _set_active_proxy(proxy)
    if openai_proxy is None:
        openai_proxy = _resolve_openai_proxy(proxy)
    _reset_risk_counter()
    output_start_lines = _count_file_lines(output_file)
    _append_log(
        "batch_start",
        "batch registration started",
        total_accounts=total_accounts,
        max_workers=max_workers,
        proxy=_get_active_proxy(),
        openai_proxy=openai_proxy,
        output_file=output_file,
        mailu_base_url=MAILU_BASE_URL,
        mail_domain=MAIL_DOMAIN,
        imap_host=IMAP_HOST,
        imap_port=IMAP_PORT,
        oauth_enabled=ENABLE_OAUTH,
        oauth_required=OAUTH_REQUIRED,
        token_json_dir=TOKEN_JSON_DIR,
        upload_api_url=UPLOAD_API_URL,
    )

    actual_workers = min(max_workers, total_accounts)
    print(f"\n{'#'*60}")
    print(f"  ChatGPT 批量自动注册 (Mailu 邮箱版)")
    print(f"  注册数量: {total_accounts} | 并发数: {actual_workers}")
    print(f"  Mailu API: {MAILU_BASE_URL}")
    print(f"  Mail Domain: {MAIL_DOMAIN}")
    print(f"  IMAP: {IMAP_HOST}:{IMAP_PORT} | SSL: {'是' if IMAP_SSL else '否'}")
    print(f"  OpenAI Proxy: {openai_proxy or '直连'} (mode={OPENAI_PROXY_MODE or 'inherit'})")
    print(f"  OAuth: {'开启' if ENABLE_OAUTH else '关闭'} | required: {'是' if OAUTH_REQUIRED else '否'}")
    if ENABLE_OAUTH:
        print(f"  OAuth Issuer: {OAUTH_ISSUER}")
        print(f"  OAuth Client: {OAUTH_CLIENT_ID}")
        print(f"  Token输出: {TOKEN_JSON_DIR}/, {AK_FILE}, {RK_FILE}")
    print(f"  输出文件: {output_file}")
    print(f"{'#'*60}\n")

    success_count = 0
    fail_count = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=actual_workers) as executor:
        futures = {}
        for idx in range(1, total_accounts + 1):
            future = executor.submit(
                _register_one, idx, total_accounts, proxy, openai_proxy, output_file
            )
            futures[future] = idx

        for future in as_completed(futures):
            idx = futures[future]
            try:
                ok, email, err = future.result()
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
                    print(f"  [账号 {idx}] 失败: {err}")
            except Exception as e:
                fail_count += 1
                with _print_lock:
                    print(f"[FAIL] 账号 {idx} 线程异常: {e}")

    elapsed = time.time() - start_time
    avg = elapsed / total_accounts if total_accounts else 0
    risk_count = _get_risk_counter()
    print(f"\n{'#'*60}")
    print(f"  注册完成! 耗时 {elapsed:.1f} 秒")
    print(f"  总数: {total_accounts} | 成功: {success_count} | 失败: {fail_count}")
    print(f"  疑似风控: {risk_count} | 阈值: {RISK_THRESHOLD}")
    print(f"  平均速度: {avg:.1f} 秒/个")
    if success_count > 0:
        print(f"  结果文件: {output_file}")
    print(f"{'#'*60}")
    _append_log(
        "batch_end",
        "batch registration finished",
        total_accounts=total_accounts,
        success=success_count,
        failed=fail_count,
        risk=risk_count,
        risk_threshold=RISK_THRESHOLD,
        elapsed_seconds=round(elapsed, 2),
        avg_seconds=round(avg, 2),
        output_file=output_file,
    )

    last_line, new_lines = _get_last_new_line(output_file, output_start_lines)
    msg_lines = [
        "ChatGPT 注册任务完成",
        f"时间: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"总数: {total_accounts} | 成功: {success_count} | 失败: {fail_count}",
        f"疑似风控: {risk_count} | 阈值: {RISK_THRESHOLD}",
        f"耗时: {elapsed:.1f} 秒",
        f"退出码: {0 if success_count > 0 else 1}",
    ]
    proxy_used = _get_active_proxy()
    if proxy_used:
        msg_lines.append(f"代理: {proxy_used}")
    if success_count > 0:
        msg_lines.append(f"结果文件: {output_file}")
    if TG_INCLUDE_ACCOUNT and new_lines > 0 and last_line:
        msg_lines.append(f"账号: {last_line}")

    notify_ok = _send_notification("\n".join(msg_lines))
    _append_log(
        "tg_notify_ok" if notify_ok else "tg_notify_skip",
        "telegram message sent" if notify_ok else "telegram message skipped",
        total_accounts=total_accounts,
        success=success_count,
        failed=fail_count,
        target=TG_CHAT_ID or TG_TARGET,
        account=TG_ACCOUNT,
        mode="bot" if (TG_BOT_TOKEN and TG_CHAT_ID) else "openclaw",
    )
    return success_count, fail_count


def main():
    print("=" * 60)
    print("  ChatGPT 批量自动注册工具 (Mailu 邮箱版)")
    print("=" * 60)

    skip_summary = _should_skip_today_due_to_risk(LOG_FILE, RISK_THRESHOLD)
    if skip_summary:
        risk_count = int(skip_summary.get("risk_count", 0) or 0)
        batch_time = skip_summary.get("time")
        batch_time_str = batch_time.strftime("%Y-%m-%d %H:%M:%S %z") if batch_time else "-"
        msg = f"检测到上一次执行疑似风控 {risk_count} >= {RISK_THRESHOLD}，今日停止运行"
        print(f"\n{msg}")
        print(f"上次执行时间: {batch_time_str}")
        _append_log(
            "batch_skip_risk",
            "skipped due to risk threshold",
            risk=risk_count,
            risk_threshold=RISK_THRESHOLD,
            last_batch_time=batch_time_str,
        )
        sys.exit(0)

    # 检查 Mailu 配置
    if not MAILU_API_TOKEN:
        print("\n⚠️  警告: 未设置 MAILU_API_TOKEN")
        print("   请编辑 config.json 设置 mailu_api_token，或设置环境变量:")
        print("   Windows: set MAILU_API_TOKEN=your_api_key_here")
        print("   Linux/Mac: export MAILU_API_TOKEN='your_api_key_here'")
        print("\n   按 Enter 继续尝试运行 (可能会失败)...")
        input()

    proxy = _resolve_proxy()

    if proxy:
        if USE_FIXED_PROXY and FIXED_PROXY and proxy == FIXED_PROXY:
            print(f"[Info] 使用固定代理: {proxy}")
        else:
            print(f"[Info] 使用代理: {proxy}")
    else:
        print("[Info] 未配置代理")

    total_accounts = int(DEFAULT_TOTAL_ACCOUNTS)
    max_workers = int(DEFAULT_MAX_WORKERS) if DEFAULT_MAX_WORKERS else 1
    success_count, _ = run_batch(total_accounts=total_accounts, output_file=DEFAULT_OUTPUT_FILE,
                                 max_workers=max_workers, proxy=proxy)
    sys.exit(0 if success_count > 0 else 1)


if __name__ == "__main__":
    main()
