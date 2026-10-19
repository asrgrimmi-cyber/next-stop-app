#!/usr/bin/env python3
"""Next Stop - small multi-user server (Python stdlib only).

* Accounts:   data/auth.db  (PBKDF2-SHA256 password hashes, hashed session tokens)
* User data:  data/users/user_<id>.db  - one separate SQLite database per user
* Frontend:   index.html (the only static file served)

Run:      python server.py [--host 0.0.0.0] [--port 8080]
Backups:  data/ is snapshotted to backups/<timestamp>/ at start-up and then daily (last 30 kept).
MCP:      POST /mcp  (Authorization: Bearer <token>)  or  POST /mcp/<token>
          tokens: Settings -> Connect Claude, or  python server.py --make-token <username>
Admin:    python server.py --list-users
          python server.py --backup
          python server.py --reset-password <username>
          python server.py --delete-user <username>
"""
import argparse
import datetime as dt
import getpass
import hashlib
import hmac
import json
import re
import secrets
import shutil
import socket
import sqlite3
import sys
import threading
import time
from contextlib import closing, contextmanager
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
DATA = ROOT / "data"
USERS_DIR = DATA / "users"
AUTH_DB = DATA / "auth.db"
BACKUPS = ROOT / "backups"
BACKUP_EVERY = 86400              # seconds between automatic backups
BACKUP_KEEP = 30                  # newest snapshots kept
BACKUP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")

COOKIE = "ns_session"
SESSION_TTL = 30 * 86400          # 30 days
PBKDF2_ITER = 310_000
MAX_BODY = 4 * 1024 * 1024        # 4 MB per save
MAX_FLIGHTS = 5000
USER_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
LOGIN_WINDOW, LOGIN_MAX_FAILS = 15 * 60, 10

USER_SCHEMA = """
CREATE TABLE IF NOT EXISTS flights(id TEXT PRIMARY KEY, doc TEXT NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS deleted(id TEXT PRIMARY KEY, rev INTEGER NOT NULL);
"""

write_locks: dict[int, threading.Lock] = {}
locks_guard = threading.Lock()
fail_guard = threading.Lock()
failures: dict[str, list] = {}    # ip -> [count, window_start]


class ApiError(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status, self.msg = status, msg


@contextmanager
def db(path):
    c = sqlite3.connect(path, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        with c:
            yield c
    finally:
        c.close()


def init_storage():
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    with db(AUTH_DB) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL UNIQUE COLLATE NOCASE,
          name TEXT NOT NULL DEFAULT '',
          salt BLOB NOT NULL,
          pw_hash BLOB NOT NULL,
          created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(
          token_hash TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL,
          expires_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS api_tokens(
          token_hash TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL,
          label TEXT NOT NULL DEFAULT '',
          created_at REAL NOT NULL,
          last_used REAL);
        """)
        c.execute("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))


def user_db_path(uid):
    return USERS_DIR / f"user_{int(uid)}.db"


def ensure_user_db(uid):
    with db(user_db_path(uid)) as c:
        c.executescript(USER_SCHEMA)
        if "rev" not in [r[1] for r in c.execute("PRAGMA table_info(flights)")]:
            c.execute("ALTER TABLE flights ADD COLUMN rev INTEGER NOT NULL DEFAULT 0")


def get_rev(c):
    row = c.execute("SELECT v FROM meta WHERE k = 'rev'").fetchone()
    return int(row["v"]) if row else 0


def set_rev(c, rev):
    c.execute("INSERT INTO meta(k, v) VALUES('rev', ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v", (str(rev),))


def read_meta(c):
    m = c.execute("SELECT v FROM meta WHERE k = 'meta'").fetchone()
    return json.loads(m["v"]) if m else None


def user_lock(uid):
    with locks_guard:
        return write_locks.setdefault(int(uid), threading.Lock())


def hash_pw(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITER)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_session(uid):
    token = secrets.token_urlsafe(32)
    with db(AUTH_DB) as c:
        c.execute("INSERT INTO sessions(token_hash, user_id, expires_at) VALUES(?,?,?)",
                  (token_hash(token), uid, time.time() + SESSION_TTL))
    return token


def session_cookie(token, max_age=SESSION_TTL):
    return f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}"


def public_user(row):
    return {"id": row["id"], "username": row["username"], "name": row["name"]}


def too_many_failures(ip):
    with fail_guard:
        rec = failures.get(ip)
        if rec and time.time() - rec[1] > LOGIN_WINDOW:
            failures.pop(ip, None)
            return False
        return bool(rec and rec[0] >= LOGIN_MAX_FAILS)


def record_failure(ip):
    with fail_guard:
        rec = failures.get(ip)
        if not rec or time.time() - rec[1] > LOGIN_WINDOW:
            failures[ip] = [1, time.time()]
        else:
            rec[0] += 1


# ---------- API tokens + MCP tools ----------
LINES = {"G": ("Gym", "GY"), "W": ("Work", "WK"), "L": ("Learn", "LN"), "H": ("Home", "HM"), "P": ("Personal", "PS")}
LINE_BY_NAME = {v[0].lower(): k for k, v in LINES.items()}
MCP_PROTOCOLS = ("2025-06-18", "2025-11-25", "2025-03-26", "2024-11-05")


def make_api_token(uid, label):
    token = "ns_" + secrets.token_urlsafe(32)
    with db(AUTH_DB) as c:
        c.execute("INSERT INTO api_tokens(token_hash, user_id, label, created_at) VALUES(?,?,?,?)",
                  (token_hash(token), uid, label, time.time()))
    return token


def user_for_api_token(token):
    if not token or not token.startswith("ns_") or len(token) > 100:
        return None
    with db(AUTH_DB) as c:
        row = c.execute("SELECT user_id FROM api_tokens WHERE token_hash = ?", (token_hash(token),)).fetchone()
        if row:
            c.execute("UPDATE api_tokens SET last_used = ? WHERE token_hash = ?", (time.time(), token_hash(token)))
    return row["user_id"] if row else None


def _uid36(prefix):
    n, digits, out = int(time.time() * 1000), "0123456789abcdefghijklmnopqrstuvwxyz", ""
    while n:
        n, r = divmod(n, 36)
        out = digits[r] + out
    return prefix + out + secrets.token_hex(3)


def _ms(ts):
    return int(ts * 1000)


def parse_when(v, field="time"):
    """ISO date/time -> epoch ms. A time without an offset is taken as this PC's local time (IST)."""
    if v in (None, "", "none", "null"):
        return None
    if isinstance(v, (int, float)):
        return int(v if v > 1e11 else v * 1000)
    txt = str(v).strip().replace("Z", "+00:00")
    try:
        d = dt.datetime.fromisoformat(txt)
    except ValueError:
        raise McpError(f"{field}: use ISO format like 2026-10-16T18:00 or 2026-10-16T18:00+05:30 (got {v!r})")
    if d.tzinfo is None:
        if len(txt) <= 10:   # date only -> 18:00 that day
            d = d.replace(hour=18)
        d = d.astimezone()
    return int(d.timestamp() * 1000)


def fmt_when(ms):
    if not ms:
        return None
    return dt.datetime.fromtimestamp(ms / 1000).astimezone().isoformat(timespec="minutes")


def line_key(v):
    if not v:
        return "W"
    v = str(v).strip()
    if v.upper() in LINES:
        return v.upper()
    k = LINE_BY_NAME.get(v.lower())
    if not k:
        raise McpError("line must be one of Gym, Work, Learn, Home, Personal (or G/W/L/H/P)")
    return k


class McpError(Exception):
    pass


def status_of(f, now_ms):
    if f.get("departedAt"):
        return "DEPARTED"
    open_t = [t for t in f.get("tickets", []) if not t.get("tornAt")]
    if not open_t:
        return "BOARDING"
    due = open_t[0].get("due") or f.get("due")
    if not due:
        return "BOARDED" if f.get("boardedAt") else "STANDBY"
    if now_ms > due:
        return "DELAYED"
    if f.get("boardedAt"):
        return "BOARDED"
    if due - now_ms <= 15 * 60000:
        return "LAST CALL"
    if due - now_ms <= 3600000:
        return "CLOSING"
    return "ON TIME"


def flight_view(f, now_ms, full=False):
    code = LINES.get(f.get("line"), ("", "PS"))[1] + str(f.get("no", ""))
    tickets = f.get("tickets", [])
    v = {"id": f["id"], "flight": code, "name": f.get("name"), "line": LINES.get(f.get("line"), ("Personal",))[0],
         "status": status_of(f, now_ms), "departs": fmt_when(f.get("due")),
         "stops_done": sum(1 for t in tickets if t.get("tornAt")), "stops_total": len(tickets),
         "boarded": fmt_when(f.get("boardedAt")), "departed": fmt_when(f.get("departedAt"))}
    if f.get("express"):
        v["express"] = True
    if full:
        v["stops"] = [{"id": t["id"], "name": t.get("name"), "due": fmt_when(t.get("due")),
                       "done": fmt_when(t.get("tornAt"))} for t in tickets]
        t = f.get("task") or {}
        for out_k, k in (("notes", "notes"), ("done_when", "done"), ("next_step", "hyp"), ("if_yes", "yes"), ("if_no", "no"), ("stopped_at", "stopped")):
            if t.get(k):
                v[out_k] = t[k]
    if f.get("due") and not f.get("departedAt") and f["due"] < now_ms:
        v["overdue_hours"] = round((now_ms - f["due"]) / 3_600_000, 1)
    return v


class UserData:
    """Load a user's flights, change them, and save with a new revision so open browsers pick it up."""
    def __init__(self, uid):
        self.uid = uid

    def __enter__(self):
        ensure_user_db(self.uid)
        self.lock = user_lock(self.uid)
        self.lock.acquire()
        self.c = sqlite3.connect(user_db_path(self.uid), timeout=10)
        self.c.row_factory = sqlite3.Row
        self.flights = {r["id"]: json.loads(r["doc"]) for r in self.c.execute("SELECT id, doc FROM flights ORDER BY rowid")}
        self.meta = read_meta(self.c) or {"v": 1, "seq": 100, "routes": [], "settings": {}}
        self.changed, self.removed = set(), set()
        return self

    def save(self):
        if not (self.changed or self.removed):
            return
        with self.c:
            new = get_rev(self.c) + 1
            now = time.time()
            for i in self.changed:
                self.c.execute("INSERT INTO flights(id, doc, updated_at, rev) VALUES(?,?,?,?) "
                               "ON CONFLICT(id) DO UPDATE SET doc = excluded.doc, updated_at = excluded.updated_at, rev = excluded.rev",
                               (i, json.dumps(self.flights[i]), now, new))
            for i in self.removed:
                self.c.execute("DELETE FROM flights WHERE id = ?", (i,))
                self.c.execute("INSERT INTO deleted(id, rev) VALUES(?, ?) ON CONFLICT(id) DO UPDATE SET rev = excluded.rev", (i, new))
            self.c.execute("INSERT INTO meta(k, v) VALUES('meta', ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v", (json.dumps(self.meta),))
            set_rev(self.c, new)

    def __exit__(self, *exc):
        try:
            if exc[0] is None:
                self.save()
        finally:
            self.c.close()
            self.lock.release()

    def find(self, ref):
        if not ref:
            raise McpError("flight is required (id, flight code like WK104, or part of the name)")
        ref = str(ref).strip()
        if ref in self.flights:
            return self.flights[ref]
        low = ref.lower().replace(" ", "")
        for f in self.flights.values():
            if (LINES.get(f.get("line"), ("", ""))[1] + str(f.get("no"))).lower() == low:
                return f
        hits = [f for f in self.flights.values() if ref.lower() in str(f.get("name", "")).lower()]
        live = [f for f in hits if not f.get("departedAt")] or hits
        if len(live) == 1:
            return live[0]
        if not live:
            raise McpError(f"No flight matches {ref!r}. Call list_flights to see ids.")
        raise McpError(f"{ref!r} matches {len(live)} flights: " + ", ".join(f"{f['id']} ({f['name']})" for f in live[:8]))

    def touch(self, f):
        self.changed.add(f["id"])


def spread(stops, end_ms, now_ms):
    """Give each open stop its own date, evenly from now up to the deadline (same rule as the app)."""
    open_s = [t for t in stops if not t.get("tornAt")]
    if not open_s or not end_ms or end_ms <= now_ms:
        return
    span, e = end_ms - now_ms, dt.datetime.fromtimestamp(end_ms / 1000)
    for i, t in enumerate(open_s):
        ts = now_ms + span * (i + 1) / len(open_s)
        if span >= 2 * 86400000:
            d = dt.datetime.fromtimestamp(ts / 1000).replace(hour=e.hour, minute=e.minute, second=0, microsecond=0)
            ts = d.timestamp() * 1000
            if ts <= now_ms:
                ts += 86400000
        else:
            ts = -(-ts // 300000) * 300000
        t["due"] = int(min(ts, end_ms))


TOOLS = [
    {"name": "list_flights", "description": "List the user's Next Stop flights (tasks). Each flight has stops (sub-steps/tickets), a departure deadline and a status (ON TIME, CLOSING, LAST CALL, BOARDED, DELAYED, BOARDING = all stops done, DEPARTED = finished). Times are ISO in the user's timezone (IST, +05:30).",
     "inputSchema": {"type": "object", "properties": {
         "include": {"type": "string", "enum": ["upcoming", "departed", "all"], "description": "default upcoming"},
         "line": {"type": "string", "description": "filter: Gym, Work, Learn, Home or Personal"}}}},
    {"name": "get_flight", "description": "Full detail for one flight: every stop with its own due date and done time, plus the Work task plan (done when / hypothesis / stopped at).",
     "inputSchema": {"type": "object", "properties": {"flight": {"type": "string", "description": "id, flight code (e.g. WK104) or part of the name"}}, "required": ["flight"]}},
    {"name": "book_flight", "description": "Schedule a new task as a flight. Use stops for sub-steps. For big jobs with a far deadline set spread_stops=true so every stop gets its own date between now and the deadline. Work flights should include done_when.",
     "inputSchema": {"type": "object", "properties": {
         "name": {"type": "string", "description": "the task, e.g. 'Ship landing page'"},
         "line": {"type": "string", "description": "Gym, Work, Learn, Home or Personal (default Work)"},
         "departs": {"type": "string", "description": "deadline, ISO e.g. 2026-10-16T18:00 (IST if no offset). Omit for no deadline."},
         "stops": {"type": "array", "items": {"type": "string"}, "description": "sub-steps in order"},
         "stop_dates": {"type": "array", "items": {"type": "string"}, "description": "optional ISO due date per stop, same order as stops"},
         "spread_stops": {"type": "boolean", "description": "auto-date the stops evenly up to the deadline"},
         "express": {"type": "boolean", "description": "priority flight, boards first"},
         "done_when": {"type": "string", "description": "Work task: what finished looks like"},
         "next_step": {"type": "string", "description": "Work task: hypothesis / next step"},
         "if_yes": {"type": "string"}, "if_no": {"type": "string"},
         "notes": {"type": "string", "description": "free-text description / context for the task (up to 2000 chars). Put background, links and details here, not in next_step."}},
         "required": ["name"]}},
    {"name": "update_flight", "description": "Rename, reschedule or change a flight. Only the fields you pass change. Set departs to 'none' to clear the deadline.",
     "inputSchema": {"type": "object", "properties": {
         "flight": {"type": "string"}, "name": {"type": "string"}, "line": {"type": "string"},
         "departs": {"type": "string"}, "express": {"type": "boolean"}, "spread_stops": {"type": "boolean"},
         "done_when": {"type": "string"}, "next_step": {"type": "string"}, "if_yes": {"type": "string"}, "if_no": {"type": "string"},
         "stopped_at": {"type": "string", "description": "where work stopped, so it can be picked up later"},
         "notes": {"type": "string", "description": "replace the free-text description / context"}},
         "required": ["flight"]}},
    {"name": "add_stops", "description": "Add stops (sub-steps) to the end of an existing flight, optionally with due dates.",
     "inputSchema": {"type": "object", "properties": {
         "flight": {"type": "string"}, "stops": {"type": "array", "items": {"type": "string"}},
         "stop_dates": {"type": "array", "items": {"type": "string"}}}, "required": ["flight", "stops"]}},
    {"name": "set_stop", "description": "Mark a stop done (tear the ticket), undo it, rename it or change its due date.",
     "inputSchema": {"type": "object", "properties": {
         "flight": {"type": "string"}, "stop": {"type": "string", "description": "stop id, its number (1 = first) or part of its name"},
         "done": {"type": "boolean"}, "name": {"type": "string"}, "due": {"type": "string", "description": "ISO or 'none'"}},
         "required": ["flight", "stop"]}},
    {"name": "board_flight", "description": "Mark that the user has started the flight (boarded). Stops last-call reminders for it.",
     "inputSchema": {"type": "object", "properties": {"flight": {"type": "string"}}, "required": ["flight"]}},
    {"name": "depart_flight", "description": "Finish a flight (it moves to the travel log). Set force=true to also mark any open stops done.",
     "inputSchema": {"type": "object", "properties": {"flight": {"type": "string"}, "force": {"type": "boolean"}}, "required": ["flight"]}},
    {"name": "delete_flight", "description": "Permanently delete a flight.",
     "inputSchema": {"type": "object", "properties": {"flight": {"type": "string"}}, "required": ["flight"]}},
    {"name": "agenda", "description": "What is due in the next N days (default 7), stop by stop, sorted by time. Good for planning a day or a week.",
     "inputSchema": {"type": "object", "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 60}}}},
]


def _dates(stops, dates):
    if not dates:
        return [None] * len(stops)
    if len(dates) != len(stops):
        raise McpError("stop_dates must have one entry per stop")
    return [parse_when(d, "stop_dates") for d in dates]


def _task_update(f, a):
    keys = {"done_when": "done", "next_step": "hyp", "if_yes": "yes", "if_no": "no", "stopped_at": "stopped", "notes": "notes"}
    if not any(k in a for k in keys):
        return
    t = dict(f.get("task") or {"done": "", "hyp": "", "yes": "", "no": "", "stopped": "", "stoppedAt": None, "notes": ""})
    for k, tk in keys.items():
        if k in a:
            t[tk] = str(a[k] or "")[:2000 if k == "notes" else 300]
    if "stopped_at" in a:
        t["stoppedAt"] = _ms(time.time()) if t["stopped"] else None
    f["task"] = t if any(t.get(k) for k in ("done", "hyp", "yes", "no", "stopped", "notes")) else None


def run_tool(uid, name, a):
    now = _ms(time.time())
    with UserData(uid) as u:
        if name == "list_flights":
            inc, ln = a.get("include") or "upcoming", a.get("line")
            fl = list(u.flights.values())
            if ln:
                k = line_key(ln)
                fl = [f for f in fl if f.get("line") == k]
            if inc == "upcoming":
                fl = [f for f in fl if not f.get("departedAt")]
            elif inc == "departed":
                fl = [f for f in fl if f.get("departedAt")]
            fl.sort(key=lambda f: (f.get("departedAt") or 0, f.get("due") or 9e15))
            return {"now": fmt_when(now), "count": len(fl), "flights": [flight_view(f, now) for f in fl]}
        if name == "get_flight":
            return flight_view(u.find(a.get("flight")), now, full=True)
        if name == "agenda":
            days = int(a.get("days") or 7)
            end = now + days * 86400000
            items = []
            for f in u.flights.values():
                if f.get("departedAt"):
                    continue
                code = LINES.get(f.get("line"), ("", "PS"))[1] + str(f.get("no"))
                for i, t in enumerate(f.get("tickets", [])):
                    d = t.get("due") or f.get("due")
                    if not t.get("tornAt") and d and d <= end:
                        items.append((d, {"due": fmt_when(d), "flight": code, "task": f["name"], "stop": f"{i + 1}. {t['name']}", "overdue": d < now}))
                if not f.get("tickets") and f.get("due") and f["due"] <= end:
                    items.append((f["due"], {"due": fmt_when(f["due"]), "flight": code, "task": f["name"], "stop": "(departure)", "overdue": f["due"] < now}))
            items.sort(key=lambda x: x[0])
            return {"now": fmt_when(now), "days": days, "items": [x[1] for x in items]}
        if name == "book_flight":
            nm = str(a.get("name") or "").strip()[:80]
            if not nm:
                raise McpError("name is required")
            stops = [str(s).strip()[:120] for s in (a.get("stops") or []) if str(s).strip()][:40]
            dates = _dates(stops, a.get("stop_dates"))
            due = parse_when(a.get("departs"), "departs")
            seq = max([int(u.meta.get("seq") or 100)] + [int(f.get("no") or 0) for f in u.flights.values()]) + 1
            u.meta["seq"] = seq
            f = {"id": _uid36("f"), "no": seq, "name": nm, "line": line_key(a.get("line")), "express": bool(a.get("express")),
                 "due": due, "createdAt": now, "departedAt": None, "boardedAt": None, "sample": False, "task": None,
                 "tickets": [{"id": _uid36("t"), "name": s, "tornAt": None, "due": d} for s, d in zip(stops, dates)]}
            if a.get("spread_stops"):
                if not due:
                    raise McpError("spread_stops needs a departs deadline")
                spread(f["tickets"], due, now)
            _task_update(f, a)
            u.flights[f["id"]] = f
            u.touch(f)
            return {"booked": flight_view(f, now, full=True)}
        f = u.find(a.get("flight"))
        if name == "update_flight":
            if "name" in a and str(a["name"]).strip():
                f["name"] = str(a["name"]).strip()[:80]
            if "line" in a:
                f["line"] = line_key(a["line"])
            if "departs" in a:
                f["due"] = parse_when(a["departs"], "departs")
            if "express" in a:
                f["express"] = bool(a["express"])
            if a.get("spread_stops"):
                if not f.get("due"):
                    raise McpError("spread_stops needs a departs deadline")
                spread(f["tickets"], f["due"], now)
            _task_update(f, a)
            u.touch(f)
            return {"updated": flight_view(f, now, full=True)}
        if name == "add_stops":
            if f.get("departedAt"):
                raise McpError("That flight already departed")
            stops = [str(s).strip()[:120] for s in (a.get("stops") or []) if str(s).strip()]
            if not stops:
                raise McpError("stops is empty")
            for s_, d in zip(stops, _dates(stops, a.get("stop_dates"))):
                f["tickets"].append({"id": _uid36("t"), "name": s_, "tornAt": None, "due": d})
            u.touch(f)
            return {"updated": flight_view(f, now, full=True)}
        if name == "set_stop":
            ref, tk = str(a.get("stop") or "").strip(), None
            ts = f.get("tickets", [])
            if ref.isdigit() and 1 <= int(ref) <= len(ts):
                tk = ts[int(ref) - 1]
            else:
                tk = next((t for t in ts if t["id"] == ref), None) or next((t for t in ts if ref.lower() in t["name"].lower()), None)
            if not tk:
                raise McpError(f"No stop {ref!r} on {f['name']}")
            if "done" in a:
                tk["tornAt"] = now if a["done"] else None
                if a["done"] and not f.get("boardedAt"):
                    f["boardedAt"] = now
                if not a["done"] and f.get("departedAt"):
                    f["departedAt"] = None
            if a.get("name"):
                tk["name"] = str(a["name"]).strip()[:120]
            if "due" in a:
                tk["due"] = parse_when(a["due"], "due")
            u.touch(f)
            return {"updated": flight_view(f, now, full=True)}
        if name == "board_flight":
            if not f.get("boardedAt"):
                f["boardedAt"] = now
                u.touch(f)
            return {"boarded": flight_view(f, now)}
        if name == "depart_flight":
            open_t = [t for t in f["tickets"] if not t.get("tornAt")]
            if open_t and not a.get("force"):
                raise McpError(f"{len(open_t)} stop(s) still open. Mark them done, or pass force=true.")
            for t in open_t:
                t["tornAt"] = now
            f["departedAt"] = f.get("departedAt") or now
            f["boardedAt"] = f.get("boardedAt") or now
            u.touch(f)
            return {"departed": flight_view(f, now)}
        if name == "delete_flight":
            del u.flights[f["id"]]
            u.removed.add(f["id"])
            u.changed.discard(f["id"])
            return {"deleted": f["name"]}
    raise McpError(f"Unknown tool {name}")


def mcp_dispatch(uid, m):
    if not isinstance(m, dict) or m.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
    mid, method, params = m.get("id"), m.get("method"), m.get("params") or {}
    if mid is None:   # notification
        return None
    ok = lambda r: {"jsonrpc": "2.0", "id": mid, "result": r}
    if method == "initialize":
        want = params.get("protocolVersion")
        return ok({"protocolVersion": want if want in MCP_PROTOCOLS else MCP_PROTOCOLS[0],
                   "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": {"name": "next-stop", "title": "Next Stop", "version": "1.0.0"},
                   "instructions": "Next Stop is the user's task planner themed as an airport departures board. "
                                   "A flight = a task with a deadline, stops = its sub-steps, boarding = starting work, departing = done. "
                                   "Times are IST (+05:30). Prefer agenda / list_flights before changing things. "
                                   "Put the task description/context in `notes` (next_step is only the next action or hypothesis). "
                                   "If a name, acronym or customer in the request is unclear or looks like a typo, ask before booking; never silently correct it. "
                                   "Flights with overdue_hours are past their deadline: point them out and offer to reschedule (update_flight departs) or finish (depart_flight) instead of just listing them."})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        try:
            res = run_tool(uid, params.get("name"), params.get("arguments") or {})
            return ok({"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False, indent=1)}], "structuredContent": res, "isError": False})
        except McpError as e:
            return ok({"content": [{"type": "text", "text": str(e)}], "isError": True})
    if method in ("resources/list", "prompts/list"):
        return ok({method.split("/")[0]: []})
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}


class Handler(BaseHTTPRequestHandler):
    server_version = "NextStop/1.0"
    sys_version = ""

    def log_message(self, fmt, *args):
        if self.path.startswith("/api/rev"):
            return
        print(f"{self.address_string()} - {fmt % args}", flush=True)

    # ---------- helpers ----------
    def send_json(self, status, obj, cookie=None):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            raise ApiError(415, "Expected JSON.")
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError(400, "Bad request.")
        if n > MAX_BODY:
            raise ApiError(413, "Too much data to save.")
        raw = self.rfile.read(n) if n > 0 else b"{}"
        try:
            data = json.loads(raw or b"{}")
        except ValueError:
            raise ApiError(400, "Bad JSON.")
        if not isinstance(data, dict):
            raise ApiError(400, "Bad request.")
        return data

    def session_token(self):
        try:
            jar = SimpleCookie(self.headers.get("Cookie") or "")
        except CookieError:
            return None
        m = jar.get(COOKIE)
        return m.value if m else None

    def current_user(self):
        tok = self.session_token()
        if not tok:
            return None
        with db(AUTH_DB) as c:
            row = c.execute(
                "SELECT u.id, u.username, u.name FROM sessions s JOIN users u ON u.id = s.user_id "
                "WHERE s.token_hash = ? AND s.expires_at > ?", (token_hash(tok), time.time())).fetchone()
        return public_user(row) if row else None

    def require_user(self):
        u = self.current_user()
        if not u:
            raise ApiError(401, "Please log in.")
        return u

    def dispatch(self, method):
        path = urlsplit(self.path).path
        try:
            if path == "/mcp" or path.startswith("/mcp/"):
                return self.handle_mcp(method, path)
            route = ROUTES.get((method, path))
            if route is None:
                if method == "GET" and path in ("/playbook", "/playbook/", "/playbook.html"):
                    return self.serve_index(ROOT / "playbook" / "index.html")
                if method == "GET" and path in ("/sprint", "/sprint.html"):
                    return self.serve_index(ROOT / "sprint.html")
                if method == "GET" and path == "/playbook/DESIGN.md":
                    return self.serve_index(ROOT / "playbook" / "DESIGN.md", "text/markdown; charset=utf-8")
                if method == "GET" and path == "/playbook/Next-Stop-template.pptx":
                    return self.serve_index(ROOT / "playbook" / "Next-Stop-template.pptx",
                                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")
                if method == "GET" and path in ("/", "/index.html"):
                    return self.serve_index()
                if method == "GET" and path in ("/debug", "/debug.html"):
                    return self.serve_index(ROOT / "debug.html")
                if method == "GET" and path == "/sw.js":
                    return self.serve_index(ROOT / "sw.js", "text/javascript; charset=utf-8")
                raise ApiError(404, "Not found.")
            route(self)
        except ApiError as e:
            self.send_json(e.status, {"error": e.msg})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {method} {path}: {e!r}", file=sys.stderr, flush=True)
            try:
                self.send_json(500, {"error": "Server error."})
            except Exception:  # noqa: BLE001
                pass

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def serve_index(self, page=INDEX, ctype="text/html; charset=utf-8"):
        body = page.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.end_headers()
        self.wfile.write(body)

    # ---------- API ----------
    def api_me(self):
        self.send_json(200, {"user": self.require_user()})

    def api_signup(self):
        b = self.read_json()
        username = str(b.get("username") or "").strip()
        password = str(b.get("password") or "")
        name = str(b.get("name") or "").strip()[:40]
        if not USER_RE.match(username):
            raise ApiError(400, "Username must be 3-32 characters: letters, numbers, dots, dashes or underscores.")
        if len(password) < 8:
            raise ApiError(400, "Password must be at least 8 characters.")
        if len(password) > 256:
            raise ApiError(400, "Password is too long.")
        salt = secrets.token_bytes(16)
        try:
            with db(AUTH_DB) as c:
                cur = c.execute("INSERT INTO users(username, name, salt, pw_hash, created_at) VALUES(?,?,?,?,?)",
                                (username, name, salt, hash_pw(password, salt), time.time()))
                uid = cur.lastrowid
        except sqlite3.IntegrityError:
            raise ApiError(409, "That username is taken.")
        ensure_user_db(uid)
        token = new_session(uid)
        self.send_json(201, {"user": {"id": uid, "username": username, "name": name}}, session_cookie(token))

    def api_login(self):
        ip = self.client_address[0]
        fwd = (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        if fwd and ip in ("127.0.0.1", "::1"):   # behind Tailscale Funnel: use the real visitor IP
            ip = fwd
        if too_many_failures(ip):
            raise ApiError(429, "Too many failed attempts. Try again in 15 minutes.")
        b = self.read_json()
        username = str(b.get("username") or "").strip()
        password = str(b.get("password") or "")[:256]
        with db(AUTH_DB) as c:
            row = c.execute("SELECT id, username, name, salt, pw_hash FROM users WHERE username = ?",
                            (username,)).fetchone()
        if row:
            ok = hmac.compare_digest(hash_pw(password, row["salt"]), row["pw_hash"])
        else:
            hash_pw(password, b"\0" * 16)   # same work either way
            ok = False
        if not ok:
            record_failure(ip)
            time.sleep(0.4)
            raise ApiError(401, "Wrong username or password.")
        ensure_user_db(row["id"])
        token = new_session(row["id"])
        self.send_json(200, {"user": public_user(row)}, session_cookie(token))

    def api_logout(self):
        tok = self.session_token()
        if tok:
            with db(AUTH_DB) as c:
                c.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(tok),))
        self.send_json(200, {"ok": True}, session_cookie("", 0))

    def api_get_state(self):
        u = self.require_user()
        ensure_user_db(u["id"])
        with db(user_db_path(u["id"])) as c:
            flights = [json.loads(r["doc"]) for r in c.execute("SELECT doc FROM flights ORDER BY rowid")]
            meta, rev = read_meta(c), get_rev(c)
        self.send_json(200, {"flights": flights, "meta": meta, "rev": rev})

    def api_rev(self):
        u = self.require_user()
        ensure_user_db(u["id"])
        with db(user_db_path(u["id"])) as c:
            self.send_json(200, {"rev": get_rev(c)})

    def api_put_state(self):
        u = self.require_user()
        b = self.read_json()
        flights, meta = b.get("flights"), b.get("meta")
        if not isinstance(flights, list) or len(flights) > MAX_FLIGHTS:
            raise ApiError(400, "Bad flights list.")
        if meta is not None and not isinstance(meta, dict):
            raise ApiError(400, "Bad settings.")
        base_rev = b.get("base_rev")
        docs, now = {}, time.time()
        for f in flights:
            if not isinstance(f, dict) or not isinstance(f.get("id"), str) or not 0 < len(f["id"]) <= 100:
                raise ApiError(400, "Bad flight.")
            docs[f["id"]] = json.dumps(f)
        ensure_user_db(u["id"])
        merged = False
        with user_lock(u["id"]), db(user_db_path(u["id"])) as c:
            cur = get_rev(c)
            new = cur + 1
            if isinstance(base_rev, int) and base_rev < cur:
                # Something else (Claude via MCP, another tab) changed flights since this client loaded:
                # keep those newer versions and honour their deletions instead of overwriting them.
                for r in c.execute("SELECT id, doc FROM flights WHERE rev > ?", (base_rev,)):
                    docs[r["id"]] = r["doc"]
                    merged = True
                for r in c.execute("SELECT id FROM deleted WHERE rev > ?", (base_rev,)):
                    if docs.pop(r["id"], None) is not None:
                        merged = True
            before = {r["id"] for r in c.execute("SELECT id FROM flights")}
            for gone in before - set(docs):
                c.execute("INSERT INTO deleted(id, rev) VALUES(?, ?) ON CONFLICT(id) DO UPDATE SET rev = excluded.rev",
                          (gone, new))
            c.execute("DELETE FROM flights")
            c.executemany("INSERT INTO flights(id, doc, updated_at, rev) VALUES(?,?,?,?)",
                          [(i, d, now, new) for i, d in docs.items()])
            if meta is not None:
                old = read_meta(c) or {}
                if isinstance(old.get("seq"), int) and old["seq"] > (meta.get("seq") or 0):
                    meta["seq"] = old["seq"]
                    merged = True
                c.execute("INSERT INTO meta(k, v) VALUES('meta', ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
                          (json.dumps(meta),))
            set_rev(c, new)
        self.send_json(200, {"ok": True, "saved": len(docs), "rev": new, "merged": merged})

    # ---------- API tokens (for the MCP endpoint) ----------
    def public_base(self):
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or "localhost:8080"
        proto = self.headers.get("X-Forwarded-Proto") or ("https" if host.endswith(".ts.net") else "http")
        return f"{proto}://{host}"

    def api_token_new(self):
        u = self.require_user()
        b = self.read_json()
        label = str(b.get("label") or "Claude").strip()[:40] or "Claude"
        token = make_api_token(u["id"], label)
        base = self.public_base()
        self.send_json(201, {"token": token, "label": label, "mcp_url": base + "/mcp", "mcp_url_with_token": base + "/mcp/" + token})

    def api_tokens(self):
        u = self.require_user()
        with db(AUTH_DB) as c:
            rows = c.execute("SELECT token_hash, label, created_at, last_used FROM api_tokens WHERE user_id = ? ORDER BY created_at",
                             (u["id"],)).fetchall()
        self.send_json(200, {"mcp_url": self.public_base() + "/mcp", "tokens": [
            {"id": r["token_hash"][:12], "label": r["label"], "created_at": r["created_at"], "last_used": r["last_used"]} for r in rows]})

    def api_token_revoke(self):
        u = self.require_user()
        tid = str(self.read_json().get("id") or "")
        if not re.fullmatch(r"[0-9a-f]{12}", tid):
            raise ApiError(400, "Bad token id.")
        with db(AUTH_DB) as c:
            n = c.execute("DELETE FROM api_tokens WHERE user_id = ? AND substr(token_hash, 1, 12) = ?", (u["id"], tid)).rowcount
        self.send_json(200, {"ok": True, "revoked": n})

    # ---------- MCP (Streamable HTTP, stateless JSON responses) ----------
    def handle_mcp(self, method, path):
        if method != "POST":
            self.send_response(405)
            self.send_header("Allow", "POST")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        token = path[5:] if path.startswith("/mcp/") else ""
        auth = self.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        uid = user_for_api_token(token)
        if not uid:
            body = json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message":
                   "Missing or invalid Next Stop token. Create one in Next Stop: Settings -> Connect Claude."}}).encode()
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("WWW-Authenticate", 'Bearer realm="next-stop"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n > MAX_BODY:
            raise ApiError(413, "Too large.")
        try:
            msg = json.loads(self.rfile.read(n) or b"null")
        except ValueError:
            return self.send_json(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
        batch = isinstance(msg, list)
        out = [r for r in (mcp_dispatch(uid, m) for m in (msg if batch else [msg])) if r is not None]
        if not out:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_json(200, out if batch else out[0])


ROUTES = {
    ("GET", "/api/me"): Handler.api_me,
    ("GET", "/api/state"): Handler.api_get_state,
    ("PUT", "/api/state"): Handler.api_put_state,
    ("POST", "/api/signup"): Handler.api_signup,
    ("POST", "/api/login"): Handler.api_login,
    ("POST", "/api/logout"): Handler.api_logout,
    ("GET", "/api/rev"): Handler.api_rev,
    ("GET", "/api/tokens"): Handler.api_tokens,
    ("POST", "/api/token"): Handler.api_token_new,
    ("POST", "/api/token/revoke"): Handler.api_token_revoke,
}


# ---------- backups ----------
def backup_all():
    """Consistent copy of every database (SQLite online backup, safe while the server runs)."""
    dest = BACKUPS / time.strftime("%Y-%m-%d_%H%M%S")
    (dest / "users").mkdir(parents=True, exist_ok=True)
    srcs = [AUTH_DB] + sorted(USERS_DIR.glob("user_*.db"))
    for src in srcs:
        with closing(sqlite3.connect(src, timeout=10)) as s, closing(sqlite3.connect(dest / src.relative_to(DATA))) as d:
            s.backup(d)
    snaps = sorted(p for p in BACKUPS.iterdir() if p.is_dir() and BACKUP_RE.match(p.name))
    for old in snaps[:-BACKUP_KEEP]:
        shutil.rmtree(old, ignore_errors=True)
    print(f"Backup: {len(srcs)} database(s) -> {dest}", flush=True)
    return dest


def backup_loop():
    while True:
        try:
            snaps = sorted(p for p in BACKUPS.iterdir() if p.is_dir() and BACKUP_RE.match(p.name)) if BACKUPS.exists() else []
            if not snaps or time.time() - snaps[-1].stat().st_mtime >= BACKUP_EVERY:
                backup_all()
        except Exception as e:  # noqa: BLE001
            print(f"ERROR backup: {e!r}", file=sys.stderr, flush=True)
        time.sleep(3600)


# ---------- admin CLI ----------
def admin(args):
    init_storage()
    if args.backup:
        backup_all()
        return
    if args.make_token:
        with db(AUTH_DB) as c:
            row = c.execute("SELECT id FROM users WHERE username = ?", (args.make_token,)).fetchone()
        if not row:
            sys.exit(f"No user named {args.make_token!r}")
        print(make_api_token(row["id"], args.label or "CLI"))
        return
    with db(AUTH_DB) as c:
        if args.list_users:
            rows = c.execute("SELECT id, username, name, created_at FROM users ORDER BY id").fetchall()
            for r in rows:
                created = time.strftime("%Y-%m-%d %H:%M", time.localtime(r["created_at"]))
                print(f"{r['id']:>4}  {r['username']:<24} {r['name']:<24} {created}  {user_db_path(r['id']).name}")
            print(f"{len(rows)} user(s)")
            return
        name = args.reset_password or args.delete_user
        row = c.execute("SELECT id FROM users WHERE username = ?", (name,)).fetchone()
        if not row:
            sys.exit(f"No user named {name!r}")
        if args.reset_password:
            pw = getpass.getpass("New password (min 8 chars): ")
            if len(pw) < 8:
                sys.exit("Too short.")
            salt = secrets.token_bytes(16)
            c.execute("UPDATE users SET salt = ?, pw_hash = ? WHERE id = ?", (salt, hash_pw(pw, salt), row["id"]))
            c.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],))
            print("Password reset; existing sessions logged out.")
        else:
            c.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],))
            c.execute("DELETE FROM users WHERE id = ?", (row["id"],))
            p = user_db_path(row["id"])
            if p.exists():
                p.rename(p.with_suffix(".deleted.db"))
            print(f"Deleted {name}; their database was renamed to {p.with_suffix('.deleted.db').name}.")


class ExclusiveServer(ThreadingHTTPServer):
    """Refuse to share the port: on Windows SO_REUSEADDR would let a second copy bind it too."""
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def keep_awake():
    """Windows: stop idle sleep while the server runs (screen may still turn off).
    Does not block lid-close or a manual Sleep."""
    if sys.platform != "win32":
        return
    import ctypes
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_AWAYMODE_REQUIRED = 0x80000000, 0x00000001, 0x00000040

    def loop():
        while True:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED)
            time.sleep(60)
    threading.Thread(target=loop, daemon=True).start()
    print("Keep-awake on: PC will not idle-sleep while Next Stop runs.", flush=True)


def main():
    ap = argparse.ArgumentParser(description="Next Stop multi-user server")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--list-users", action="store_true")
    ap.add_argument("--reset-password", metavar="USERNAME")
    ap.add_argument("--delete-user", metavar="USERNAME")
    ap.add_argument("--backup", action="store_true", help="snapshot all databases into backups/ now")
    ap.add_argument("--make-token", metavar="USERNAME", help="print a new MCP/API token for this user")
    ap.add_argument("--label", default="", help="label for --make-token")
    args = ap.parse_args()
    if args.list_users or args.reset_password or args.delete_user or args.backup or args.make_token:
        return admin(args)
    init_storage()
    keep_awake()
    threading.Thread(target=backup_loop, daemon=True).start()
    try:
        srv = ExclusiveServer((args.host, args.port), Handler)
    except OSError as e:
        print(f"Cannot listen on port {args.port}: {e}", file=sys.stderr, flush=True)
        try:   # another copy answering means it is already running (run-next-stop.cmd stops on code 3)
            socket.create_connection(("127.0.0.1", args.port), timeout=2).close()
            sys.exit(3)
        except OSError:
            sys.exit(1)   # port briefly unavailable: the launcher retries
    srv.daemon_threads = True
    print(f"Next Stop running on http://{args.host}:{args.port}  (data in {DATA})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
