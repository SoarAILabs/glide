<<<<<<< HEAD

import re
from collections import defaultdict
from datetime import datetime


LEVELS = ["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"]


def parse_log_line(line):
    """Parse 'YYYY-MM-DD HH:MM:SS [LEVEL] message' using regex."""
    match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[([A-Z]+)\] (.*)$", line.strip())
    if not match:
        return None
    ts_str, level, message = match.groups()
    try:
        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return {"timestamp": ts, "level": level, "message": message}


def aggregate_stats(lines):
    """Count occurrences per level and total lines parsed."""
    counts = {lvl: 0 for lvl in LEVELS}
    total = 0
    for line in lines:
        entry = parse_log_line(line)
        if not entry:
            continue
        total += 1
        if entry["level"] in counts:
            counts[entry["level"]] += 1
    counts["TOTAL"] = total
    return counts


class LogAnalyzer:
    """Compute basic error rate and latest timestamp."""

    def analyze(self, lines):
        stats = aggregate_stats(lines)
        total = stats.get("TOTAL", 0)
        errors = stats.get("ERROR", 0) + stats.get("CRITICAL", 0)
        error_rate = (errors / total) if total else 0.0
        latest_ts = None
        for line in lines:
            entry = parse_log_line(line)
            if entry:
                latest_ts = entry["timestamp"] if latest_ts is None else max(latest_ts, entry["timestamp"])
        return {"stats": stats, "error_rate": error_rate, "latest_ts": latest_ts}
||||||| base
import re


def parse_log_line(line):
    """Very simple parser: split on spaces, level is token 2 like [LEVEL]."""
    parts = line.strip().split(" ", 2)
    if len(parts) < 3:
        return None
    ts_str = " ".join(parts[:2])
    rest = parts[2]
    if not rest.startswith("[") or "]" not in rest:
        return None
    level = rest[1:rest.find("]")]
    message = rest[rest.find("]") + 2 :] if "] " in rest else ""
    return {"timestamp": ts_str, "level": level, "message": message}


def aggregate_stats(lines):
    """Count lines seen and levels found without validation."""
    counts = {"TOTAL": 0}
    for line in lines:
        counts["TOTAL"] += 1
        if "[" in line and "]" in line:
            level = line.split("[", 1)[1].split("]", 1)[0]
            counts[level] = counts.get(level, 0) + 1
    return counts


class LogAnalyzer:
    """Return just the raw counts for simplicity."""

    def analyze(self, lines):
        return {"stats": aggregate_stats(lines)}
=======
import re
import json
from collections import Counter, defaultdict
from datetime import datetime


LEVEL_ORDER = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40, "CRITICAL": 50}


def parse_log_line(line):
    """Parse JSON logs first; fallback to regex 'ts [LEVEL] msg'."""
    s = line.strip()
    if not s:
        return None
    # Try JSON: {"ts":"2025-11-10T12:34:56","level":"INFO","msg":"..."}
    if s.startswith("{") and s.endswith("}"):
        try:
            obj = json.loads(s)
            ts = datetime.fromisoformat(obj["ts"])
            return {"timestamp": ts, "level": obj.get("level", "INFO"), "message": obj.get("msg", "")}
        except Exception:
            pass
    m = re.match(r"^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}) \[([A-Z]+)\] (.*)$", s)
    if not m:
        return None
    ts_str, level, message = m.groups()
    try:
        ts = datetime.fromisoformat(ts_str.replace(" ", "T"))
    except ValueError:
        return None
    return {"timestamp": ts, "level": level, "message": message}


def aggregate_stats(lines):
    """Aggregate per-level counts and per-minute buckets."""
    per_level = Counter()
    per_minute = defaultdict(int)
    total = 0
    for line in lines:
        entry = parse_log_line(line)
        if not entry:
            continue
        total += 1
        per_level[entry["level"]] += 1
        minute_bucket = entry["timestamp"].replace(second=0, microsecond=0)
        per_minute[minute_bucket] += 1
    summary = {"TOTAL": total}
    summary.update(per_level)
    return {"summary": summary, "per_minute": dict(per_minute)}


class LogAnalyzer:
    """Compute error severity score and busiest minute."""

    def analyze(self, lines):
        agg = aggregate_stats(lines)
        summary = agg["summary"]
        score = 0
        for level, count in summary.items():
            if level in LEVEL_ORDER:
                score += LEVEL_ORDER[level] * count
        busiest_minute = None
        if agg["per_minute"]:
            busiest_minute = max(agg["per_minute"].items(), key=lambda kv: kv[1])[0]
        return {"summary": summary, "severity_score": score, "busiest_minute": busiest_minute}
>>>>>>> branch

