#!/usr/bin/env python3
"""ZKas Dual Alert — Unofficial Community Tool

A dependency-free monitor for firecash/solo-dual-mode bridge dashboards.
Supports JSON /api/stats (preferred) with Prometheus /metrics fallback.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import signal
import smtplib
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

APP_VERSION = "0.2.2"
DEFAULT_CONFIG = "config.json"
USER_AGENT = f"ZKasDualAlert/{APP_VERSION}"
STOP = False


def log(msg: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def resolve_secret(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("env:"):
        return os.environ.get(value[4:], "")
    return value


def deep_resolve(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: deep_resolve(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_resolve(v) for v in obj]
    return resolve_secret(obj)


def http_request(url: str, method: str = "GET", data: Optional[bytes] = None,
                 headers: Optional[Dict[str, str]] = None, timeout: float = 5.0) -> bytes:
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


@dataclass(frozen=True)
class BlockEvent:
    chain: str
    hash: str = ""
    worker: str = ""
    wallet: str = ""
    payout_wallet: str = ""
    timestamp: str = ""
    nonce: str = ""
    score: str = ""
    reward_sompi: Optional[int] = None
    source: str = ""

    @property
    def key(self) -> str:
        if self.hash:
            return f"{self.chain}:{self.hash}"
        return f"{self.chain}:{self.timestamp}:{self.worker}:{self.nonce}:{self.score}"

    def reward_kas(self) -> Optional[float]:
        if self.reward_sompi is None:
            return None
        return self.reward_sompi / 100_000_000.0


@dataclass
class Snapshot:
    zkas_total: int
    kas_total: int
    zkas_blocks: List[BlockEvent]
    kas_blocks: List[BlockEvent]
    active_workers: Optional[int] = None
    total_shares: Optional[int] = None
    bridge_uptime: Optional[int] = None
    source: str = "unknown"


class BridgeParser:
    """Schema-tolerant parser for bridge stats.

    Current v1.0.7 names are handled exactly; aliases make later additive/renamed
    versions less likely to break the monitor.
    """

    @staticmethod
    def _first(d: Dict[str, Any], names: Iterable[str], default: Any = None) -> Any:
        for name in names:
            if name in d:
                return d[name]
        lowered = {str(k).lower(): v for k, v in d.items()}
        for name in names:
            if name.lower() in lowered:
                return lowered[name.lower()]
        return default

    @staticmethod
    def _as_int(v: Any, default: int = 0) -> int:
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return default

    @classmethod
    def parse_json(cls, data: Dict[str, Any]) -> Snapshot:
        zarr = cls._first(data, ["blocks", "zkasBlocks", "recentZkasBlocks", "recentBlocks", "zkasBlockHistory"], []) or []
        karr = cls._first(data, ["kasBlocks", "recentKasBlocks", "kasBlockHistory", "parentBlocks"], []) or []

        zblocks = [cls._event_from_json("ZKAS", x, "json") for x in zarr if isinstance(x, dict)]
        kblocks = [cls._event_from_json("KAS", x, "json") for x in karr if isinstance(x, dict)]

        ztotal = cls._as_int(cls._first(data, ["totalBlocks", "totalZkasBlocks", "zkasBlocksTotal", "zkasBlockCount"], len(zblocks)), len(zblocks))
        ktotal = cls._as_int(cls._first(data, ["totalKasBlocks", "kasBlocksTotal", "kasBlockCount", "parentBlockCount"], len(kblocks)), len(kblocks))

        return Snapshot(
            zkas_total=max(ztotal, len(zblocks)),
            kas_total=max(ktotal, len(kblocks)),
            zkas_blocks=zblocks,
            kas_blocks=kblocks,
            active_workers=cls._optional_int(cls._first(data, ["activeWorkers", "workersActive"])),
            total_shares=cls._optional_int(cls._first(data, ["totalShares", "sharesTotal"])),
            bridge_uptime=cls._optional_int(cls._first(data, ["bridgeUptime", "uptimeSeconds", "uptime"])),
            source="json",
        )

    @staticmethod
    def _optional_int(v: Any) -> Optional[int]:
        if v is None:
            return None
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _event_from_json(cls, chain: str, x: Dict[str, Any], source: str) -> BlockEvent:
        reward = cls._first(x, ["rewardSompi", "reward_sompi", "reward"])
        reward_int = None
        if reward not in (None, ""):
            try:
                reward_int = int(reward)
            except (TypeError, ValueError):
                reward_int = None
        return BlockEvent(
            chain=chain,
            hash=str(cls._first(x, ["hash", "blockHash", "block_hash"], "") or ""),
            worker=str(cls._first(x, ["worker", "workerName", "worker_name"], "") or ""),
            wallet=str(cls._first(x, ["wallet", "zkasWallet", "zkas_wallet"], "") or ""),
            payout_wallet=str(cls._first(x, ["kasWallet", "kas_wallet", "payoutWallet", "payout_wallet"], "") or ""),
            timestamp=str(cls._first(x, ["timestamp", "time", "timestampUnix", "timestamp_unix"], "") or ""),
            nonce=str(cls._first(x, ["nonce"], "") or ""),
            score=str(cls._first(x, ["bluescore", "blueScore", "daaScore", "daa_score"], "") or ""),
            reward_sompi=reward_int,
            source=source,
        )

    @classmethod
    def parse_metrics(cls, text: str) -> Snapshot:
        zblocks: List[BlockEvent] = []
        kblocks: List[BlockEvent] = []
        zcounter = 0
        kcounter = 0
        shares = 0

        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            name, labels, value = cls._parse_metric_line(line)
            if not name:
                continue
            if name == "ks_mined_blocks_gauge" and value > 0:
                zblocks.append(BlockEvent(
                    chain="ZKAS", hash=labels.get("hash", ""), worker=labels.get("worker", ""),
                    wallet=labels.get("wallet", ""), timestamp=labels.get("timestamp", ""),
                    nonce=labels.get("nonce", ""), score=labels.get("bluescore", ""), source="metrics"))
            elif name == "ks_merged_kas_blocks_gauge" and value > 0:
                reward = labels.get("reward_sompi", "")
                try:
                    reward_int = int(reward) if reward else None
                except ValueError:
                    reward_int = None
                kblocks.append(BlockEvent(
                    chain="KAS", hash=labels.get("hash", ""), worker=labels.get("worker", ""),
                    wallet=labels.get("zkas_wallet", ""), payout_wallet=labels.get("kas_wallet", ""),
                    timestamp=labels.get("timestamp", ""), nonce=labels.get("nonce", ""),
                    score=labels.get("daa_score", ""), reward_sompi=reward_int, source="metrics"))
            elif name == "ks_blocks_mined":
                zcounter += int(value)
            elif name == "ks_merged_kas_blocks_accepted_total":
                kcounter += int(value)
            elif name == "ks_valid_share_counter":
                shares += int(value)

        zunique = cls._dedupe(zblocks)
        kunique = cls._dedupe(kblocks)
        return Snapshot(
            zkas_total=max(zcounter, len(zunique)),
            kas_total=max(kcounter, len(kunique)),
            zkas_blocks=zunique,
            kas_blocks=kunique,
            total_shares=shares,
            source="metrics",
        )

    @staticmethod
    def _dedupe(events: List[BlockEvent]) -> List[BlockEvent]:
        out: List[BlockEvent] = []
        seen = set()
        for e in events:
            if e.key not in seen:
                seen.add(e.key)
                out.append(e)
        return out

    @staticmethod
    def _parse_metric_line(line: str) -> Tuple[str, Dict[str, str], float]:
        m = re.match(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(.*)\})?\s+([-+0-9.eE]+)$', line)
        if not m:
            return "", {}, 0.0
        name, label_text, val = m.groups()
        labels: Dict[str, str] = {}
        if label_text:
            for lm in re.finditer(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:\\.|[^"])*)"', label_text):
                key, raw_val = lm.groups()
                labels[key] = bytes(raw_val, "utf-8").decode("unicode_escape")
        try:
            value = float(val)
        except ValueError:
            value = 0.0
        return name, labels, value


class BridgeSource:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def fetch(self) -> Snapshot:
        errors: List[str] = []
        try:
            raw = http_request(f"{self.base_url}/api/stats", timeout=self.timeout)
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, dict):
                return BridgeParser.parse_json(data)
            errors.append("/api/stats did not return a JSON object")
        except Exception as exc:  # fallback is intentional
            errors.append(f"/api/stats: {exc}")

        try:
            raw = http_request(f"{self.base_url}/metrics", timeout=self.timeout)
            return BridgeParser.parse_metrics(raw.decode("utf-8", errors="replace"))
        except Exception as exc:
            errors.append(f"/metrics: {exc}")
        raise RuntimeError("; ".join(errors))


class Notifier:
    def send(self, subject: str, body: str) -> None:
        raise NotImplementedError


class ConsoleNotifier(Notifier):
    def send(self, subject: str, body: str) -> None:
        log(f"ALERT: {subject}\n{body}")


class SMTPNotifier(Notifier):
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg

    def send(self, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.cfg["from"]
        msg["To"] = self.cfg["to"]
        msg.set_content(body)
        host = self.cfg["host"]
        port = int(self.cfg.get("port", 587))
        mode = str(self.cfg.get("security", "starttls")).lower()
        username = self.cfg.get("username", "")
        password = self.cfg.get("password", "")
        if mode == "ssl":
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=15) as s:
                if username:
                    s.login(username, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as s:
                if mode == "starttls":
                    s.starttls(context=ssl.create_default_context())
                if username:
                    s.login(username, password)
                s.send_message(msg)


class TwilioNotifier(Notifier):
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg

    def send(self, subject: str, body: str) -> None:
        sid = self.cfg["account_sid"]
        token = self.cfg["auth_token"]
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        payload = urllib.parse.urlencode({
            "From": self.cfg["from_number"],
            "To": self.cfg["to_number"],
            "Body": f"{subject}\n{body}"[:1500],
        }).encode()
        auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
        http_request(url, method="POST", data=payload,
                     headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"}, timeout=15)


class NtfyNotifier(Notifier):
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg

    def send(self, subject: str, body: str) -> None:
        headers = {"Title": subject, "Priority": str(self.cfg.get("priority", "high")), "Tags": "pick,computer"}
        token = self.cfg.get("token", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        http_request(self.cfg["url"], method="POST", data=body.encode("utf-8"), headers=headers, timeout=15)


class DiscordNotifier(Notifier):
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg

    def send(self, subject: str, body: str) -> None:
        payload = json.dumps({"content": f"**{subject}**\n{body}"}).encode("utf-8")
        http_request(self.cfg["webhook_url"], method="POST", data=payload,
                     headers={"Content-Type": "application/json"}, timeout=15)


def build_notifiers(cfg: Dict[str, Any]) -> List[Notifier]:
    out: List[Notifier] = []
    nc = cfg.get("notifications", {})
    if nc.get("console", {}).get("enabled", True):
        out.append(ConsoleNotifier())
    for key, klass in [("smtp", SMTPNotifier), ("twilio", TwilioNotifier), ("ntfy", NtfyNotifier), ("discord", DiscordNotifier)]:
        section = nc.get(key, {})
        if section.get("enabled", False):
            out.append(klass(section))
    return out


def notify_all(notifiers: List[Notifier], subject: str, body: str) -> List[Tuple[str, bool, str]]:
    """Send through every configured notifier and return per-channel results."""
    results: List[Tuple[str, bool, str]] = []
    for notifier in notifiers:
        name = notifier.__class__.__name__
        try:
            notifier.send(subject, body)
            results.append((name, True, "sent"))
        except Exception as exc:
            msg = str(exc)
            log(f"Notification failed via {name}: {msg}")
            results.append((name, False, msg))
    return results


def event_body(event: BlockEvent) -> str:
    parts = [f"Chain: {event.chain}"]
    if event.worker:
        parts.append(f"Worker: {event.worker}")
    if event.hash:
        parts.append(f"Block hash: {event.hash}")
    if event.timestamp:
        parts.append(f"Timestamp: {event.timestamp}")
    if event.wallet:
        parts.append(f"ZKAS wallet: {event.wallet}")
    if event.payout_wallet:
        parts.append(f"KAS payout wallet: {event.payout_wallet}")
    if event.score:
        parts.append(f"Score: {event.score}")
    reward = event.reward_kas()
    if reward is not None:
        parts.append(f"Reported KAS reward: {reward:.8f} KAS")
    parts.append(f"Detected via: {event.source}")
    return "\n".join(parts)


def load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"seen": [], "reward_seen": [], "counts": {"ZKAS": 0, "KAS": 0}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"seen": [], "reward_seen": [], "counts": {"ZKAS": 0, "KAS": 0}}


def save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def monitor(config_path: Path, once: bool = False, test_notification: bool = False, stop_event: Any = None) -> int:
    raw_cfg = json.loads(config_path.read_text(encoding="utf-8"))
    cfg = deep_resolve(raw_cfg)
    base_url = cfg.get("bridge", {}).get("base_url", "http://127.0.0.1:3033")
    poll = max(5, int(cfg.get("bridge", {}).get("poll_seconds", 30)))
    timeout = float(cfg.get("bridge", {}).get("timeout_seconds", 5))
    alert_existing = bool(cfg.get("bridge", {}).get("alert_existing_on_first_run", False))
    fail_threshold = max(1, int(cfg.get("bridge", {}).get("down_after_failures", 3)))
    alerts = cfg.get("alerts", {})

    state_path_value = cfg.get("state_file", "state.json")
    state_path = Path(state_path_value)
    if not state_path.is_absolute():
        state_path = config_path.parent / state_path
    state = load_state(state_path)
    seen = set(state.get("seen", []))
    reward_seen = set(state.get("reward_seen", []))
    counts = state.get("counts", {"ZKAS": 0, "KAS": 0})
    first_run = not state_path.exists()

    notifiers = build_notifiers(cfg)
    if test_notification:
        notify_all(notifiers, "ZKas Dual Alert — Unofficial Community Tool test", f"Notifications are working. Bridge: {base_url}")
        return 0

    source = BridgeSource(base_url, timeout)
    failures = 0
    down_alerted = False
    log(f"ZKas Dual Alert — Unofficial Community Tool v{APP_VERSION} monitoring {base_url} every {poll}s")

    global STOP
    while not STOP and not (stop_event is not None and stop_event.is_set()):
        try:
            snap = source.fetch()
            if failures and down_alerted and alerts.get("bridge_recovered", True):
                notify_all(notifiers, "✅ Bridge recovered", f"Bridge is responding again at {base_url} (source: {snap.source}).")
            failures = 0
            down_alerted = False

            current_events = snap.zkas_blocks + snap.kas_blocks
            if first_run and not alert_existing:
                for e in current_events:
                    seen.add(e.key)
                    if e.reward_sompi is not None:
                        reward_seen.add(e.key)
                counts["ZKAS"] = snap.zkas_total
                counts["KAS"] = snap.kas_total
                first_run = False
                log(f"Baseline created: ZKAS={snap.zkas_total}, KAS={snap.kas_total}, source={snap.source}. Existing blocks not alerted.")
            else:
                # Hash/detail based alerts
                for e in current_events:
                    if e.key not in seen:
                        enabled = alerts.get("zkas_block", True) if e.chain == "ZKAS" else alerts.get("kas_block", True)
                        if enabled:
                            notify_all(notifiers, f"🚨 {e.chain} BLOCK FOUND", event_body(e))
                        seen.add(e.key)
                    if e.chain == "KAS" and e.reward_sompi is not None and e.key not in reward_seen:
                        if alerts.get("kas_reward_known", True):
                            notify_all(notifiers, "💰 KAS reward reported", event_body(e))
                        reward_seen.add(e.key)

                # Count-only fallback for versions that expose totals but no history arrays.
                for chain, total in (("ZKAS", snap.zkas_total), ("KAS", snap.kas_total)):
                    old = int(counts.get(chain, 0) or 0)
                    if total > old and not any(e.chain == chain and e.key not in set(state.get("seen", [])) for e in current_events):
                        enabled = alerts.get("zkas_block", True) if chain == "ZKAS" else alerts.get("kas_block", True)
                        if enabled:
                            notify_all(notifiers, f"🚨 {chain} block count increased", f"{chain} block total changed from {old} to {total}.\nBridge: {base_url}\nDetected via: {snap.source}")
                    counts[chain] = max(old, total)
                first_run = False

            state = {"seen": sorted(seen), "reward_seen": sorted(reward_seen), "counts": counts, "last_source": snap.source, "updated": int(time.time())}
            save_state(state_path, state)
            log(f"OK source={snap.source} ZKAS={snap.zkas_total} KAS={snap.kas_total} workers={snap.active_workers if snap.active_workers is not None else '-'} shares={snap.total_shares if snap.total_shares is not None else '-'}")
        except Exception as exc:
            failures += 1
            log(f"Bridge check failed ({failures}/{fail_threshold}): {exc}")
            if failures >= fail_threshold and not down_alerted and alerts.get("bridge_down", True):
                notify_all(notifiers, "⚠️ Bridge unreachable", f"Failed {failures} consecutive checks for {base_url}.\nLast error: {exc}")
                down_alerted = True

        if once:
            break
        for _ in range(poll):
            if STOP or (stop_event is not None and stop_event.is_set()):
                break
            time.sleep(1)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Alerts for ZKas/Kaspa solo-dual-mode block events")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Path to config.json")
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    parser.add_argument("--test-notification", action="store_true", help="Send a test through configured notification channels")
    parser.add_argument("--version", action="version", version=APP_VERSION)
    args = parser.parse_args()
    path = Path(args.config).expanduser().resolve()
    if not path.exists():
        print(f"Config not found: {path}\nCopy config.example.json to config.json and edit it.", file=sys.stderr)
        return 2
    return monitor(path, once=args.once, test_notification=args.test_notification)


def _signal_handler(signum, frame):
    global STOP
    STOP = True
    log("Stopping...")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _signal_handler)
    raise SystemExit(main())
