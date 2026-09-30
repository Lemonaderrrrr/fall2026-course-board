"""Fetch the Canvas calendar feed and write data/canvas.json for the course board.

The feed URL is private, so it's read from the CANVAS_FEED_URL env var
(a GitHub Actions secret) and never written to the repo.
Standard library only.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

LA = ZoneInfo("America/Los_Angeles")
TERM_START, TERM_END = date(2026, 9, 24), date(2026, 12, 11)
OUT = Path(__file__).resolve().parent.parent / "data" / "canvas.json"

# Checked in order: 105LA before 105A, 7LC before 7C.
COURSES = [
    (r"SWE\s*43", "swe", None),
    (r"140A", "140", None),
    (r"121A", "121", None),
    (r"105LA", "105", "105LA"),
    (r"105A", "105", None),
    (r"7LC", "7c", "7LC"),
    (r"7C", "7c", None),
]


def unfold(text):
    return text.replace("\r\n", "\n").replace("\n ", "").replace("\n\t", "")


def unescape(v):
    return v.replace("\\n", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()


def parse_events(ics):
    for block in unfold(ics).split("BEGIN:VEVENT")[1:]:
        block = block.split("END:VEVENT")[0]
        ev = {}
        for line in block.split("\n"):
            if ":" not in line:
                continue
            head, value = line.split(":", 1)
            name, *params = head.split(";")
            ev[name] = (params, value)
        yield ev


def parse_start(params, value):
    """Return (local date, 'HH:MM' or None)."""
    if "T" not in value:
        return datetime.strptime(value[:8], "%Y%m%d").date(), None
    if value.endswith("Z"):
        dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(LA)
    else:
        tzid = next((p.split("=", 1)[1] for p in params if p.startswith("TZID=")), None)
        dt = datetime.strptime(value[:15], "%Y%m%dT%H%M%S").replace(tzinfo=ZoneInfo(tzid) if tzid else LA)
        dt = dt.astimezone(LA)
    return dt.date(), dt.strftime("%H:%M")


def classify(summary, desc=""):
    m = re.match(r"^(.*?)\s*\[([^\]]*)\]\s*$", summary)
    title, ctx = (m.group(1), m.group(2)) if m else (summary, "")
    title = re.sub(r"\s*\((?:PHYSICS|MATH|SWE)\b.*$", "", title, flags=re.I)
    ctx_u = ctx.upper()
    for pat, code, lab in COURSES:
        if re.search(pat, ctx_u):
            break
    else:
        return None
    t = title.lower()
    if lab:
        kind = "lab"
        title = f"{lab} {title}"
    elif "midterm" in t:
        kind = "mid"
    elif re.search(r"\bfinal\b", t):
        kind = "final"
    elif "quiz" in t:
        kind = "quiz"
    elif re.search(r"homework|\bhw\s*\d", t):
        kind = "hw"
    elif re.search(r"read|article|\.pdf|chapter|sec\.", t + " " + desc.lower()):
        kind = "read"
    else:
        kind = "other"
    n = None
    if kind in ("hw", "quiz"):
        mn = re.search(r"(?:homework|hw|quiz)\s*#?\s*(\d+)", t)
        n = int(mn.group(1)) if mn else None
    return {"c": code, "k": kind, "n": n, "title": title.strip()}


def main():
    url = os.environ.get("CANVAS_FEED_URL")
    if not url:
        sys.exit("CANVAS_FEED_URL is not set")
    req = urllib.request.Request(url, headers={"User-Agent": "course-board-sync"})
    with urllib.request.urlopen(req, timeout=30) as r:
        ics = r.read().decode("utf-8", "replace")
    if "BEGIN:VCALENDAR" not in ics:
        sys.exit("Response is not an iCalendar feed")

    events = []
    for ev in parse_events(ics):
        if "DTSTART" not in ev or "SUMMARY" not in ev:
            continue
        d, t = parse_start(*ev["DTSTART"])
        if not (TERM_START <= d <= TERM_END):
            continue
        info = classify(unescape(ev["SUMMARY"][1]), unescape(ev.get("DESCRIPTION", ([], ""))[1]))
        if not info:
            continue
        events.append({"uid": ev.get("UID", ([], ""))[1], "d": d.isoformat(), "t": t, **info})

    events.sort(key=lambda e: (e["d"], e["t"] or "23:59", e["c"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "fetched_at": datetime.now(LA).isoformat(timespec="minutes"),
        "events": events,
    }, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {len(events)} events to {OUT}")


if __name__ == "__main__":
    main()
