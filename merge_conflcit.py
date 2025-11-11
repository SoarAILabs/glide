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
