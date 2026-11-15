#!/usr/bin/env python3
"""A small, single-user CBT journal server. Requires Python 3.11+, no packages."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data")).expanduser()
DB_PATH = DATA_DIR / "journal.sqlite3"
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
SESSION_TTL = 60 * 60 * 24 * 30
sessions: dict[str, float] = {}
sessions_lock = threading.Lock()


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""CREATE TABLE IF NOT EXISTS entries (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL CHECK(kind IN ('thought', 'activity')),
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS course_progress (
            lesson_id TEXT PRIMARY KEY,
            reflection TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )""")


def password_matches(candidate: str) -> bool:
    # Slow the single-user password check without persisting a plaintext password.
    expected = hashlib.scrypt(APP_PASSWORD.encode(), salt=b"mental-health-local", n=2**14, r=8, p=1)
    actual = hashlib.scrypt(candidate.encode(), salt=b"mental-health-local", n=2**14, r=8, p=1)
    return hmac.compare_digest(expected, actual)


class Handler(BaseHTTPRequestHandler):
    server_version = "CBTJournal/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        # Avoid logging URLs or bodies that might contain personal information.
        print(f"{self.log_date_time_string()} {self.client_address[0]} {fmt % args}")

    def send_json(self, status: int, value: object, extra_headers: dict[str, str] | None = None) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        for key, val in (extra_headers or {}).items():
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 100_000:
                raise ValueError("Request too large")
            value = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(value, dict):
                raise ValueError("Expected an object")
            return value
        except (ValueError, json.JSONDecodeError):
            raise ValueError("Invalid JSON")

    def request_origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urlparse(origin)
        host = self.headers.get("Host", "").lower()
        return parsed.netloc.lower() == host and parsed.scheme in ("http", "https")

    def session_token(self) -> str | None:
        jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        morsel = jar.get("cbt_session")
        token = morsel.value if morsel else None
        if not token:
            return None
        with sessions_lock:
            expiry = sessions.get(token, 0)
            if expiry < time.time():
                sessions.pop(token, None)
                return None
            return token

    def authorized(self) -> bool:
        return self.session_token() is not None

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/session":
            self.send_json(200, {"authenticated": self.authorized()})
            return
        if path.startswith("/api/"):
            if not self.authorized():
                self.send_json(401, {"error": "Sign in to continue."})
                return
            if path == "/api/entries":
                with sqlite3.connect(DB_PATH) as db:
                    db.row_factory = sqlite3.Row
                    rows = db.execute("SELECT id, kind, title, body, created_at FROM entries ORDER BY created_at DESC").fetchall()
                self.send_json(200, [{**dict(row), "body": json.loads(row["body"])} for row in rows])
                return
            if path == "/api/course-progress":
                with sqlite3.connect(DB_PATH) as db:
                    rows = db.execute("SELECT lesson_id, reflection, completed, updated_at FROM course_progress").fetchall()
                self.send_json(200, [{"lesson_id": row[0], "reflection": row[1], "completed": bool(row[2]), "updated_at": row[3]} for row in rows])
                return
            self.send_json(404, {"error": "Not found"})
            return
        if path == "/" or path in ("/index.html", "/app.css", "/app.js", "/content.json", "/CONTENT_LICENSE.md"):
            filename = "index.html" if path == "/" else path.lstrip("/")
            file_path = ROOT / filename
            if file_path.is_file():
                body = file_path.read_bytes()
                content_type = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8", ".md": "text/markdown; charset=utf-8"}.get(file_path.suffix, "application/octet-stream")
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
                self.end_headers()
                self.wfile.write(body)
                return
        self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if not self.request_origin_ok():
            self.send_json(403, {"error": "Request origin was not accepted."})
            return
        if path == "/api/login":
            try:
                data = self.read_json()
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
                return
            password = data.get("password", "")
            if not isinstance(password, str) or not password_matches(password):
                time.sleep(0.5)
                self.send_json(401, {"error": "That password didn’t match."})
                return
            token = secrets.token_urlsafe(32)
            with sessions_lock:
                sessions[token] = time.time() + SESSION_TTL
            secure = "; Secure" if COOKIE_SECURE else ""
            cookie = f"cbt_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL}{secure}"
            self.send_json(200, {"authenticated": True}, {"Set-Cookie": cookie})
            return
        if not self.authorized():
            self.send_json(401, {"error": "Sign in to continue."})
            return
        if path == "/api/logout":
            token = self.session_token()
            if token:
                with sessions_lock:
                    sessions.pop(token, None)
            cookie = "cbt_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0" + ("; Secure" if COOKIE_SECURE else "")
            self.send_json(200, {"authenticated": False}, {"Set-Cookie": cookie})
            return
        if path == "/api/entries":
            try:
                data = self.read_json()
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
                return
            kind = data.get("kind")
            title = data.get("title", "").strip() if isinstance(data.get("title", ""), str) else ""
            body = data.get("body")
            if kind not in ("thought", "activity") or not isinstance(body, dict):
                self.send_json(400, {"error": "Entry is incomplete."})
                return
            if not title:
                title = "Thought record" if kind == "thought" else "Activity plan"
            entry = {"id": secrets.token_urlsafe(12), "kind": kind, "title": title[:120], "body": body, "created_at": datetime.now(timezone.utc).isoformat()}
            with sqlite3.connect(DB_PATH) as db:
                db.execute("INSERT INTO entries(id, kind, title, body, created_at) VALUES(?, ?, ?, ?, ?)", (entry["id"], kind, entry["title"], json.dumps(body, ensure_ascii=False), entry["created_at"]))
            self.send_json(201, entry)
            return
        if path == "/api/entries/clear":
            with sqlite3.connect(DB_PATH) as db:
                db.execute("DELETE FROM entries")
            self.send_json(200, {"cleared": True})
            return
        if path == "/api/course-progress/clear":
            with sqlite3.connect(DB_PATH) as db:
                db.execute("DELETE FROM course_progress")
            self.send_json(200, {"cleared": True})
            return
        self.send_json(404, {"error": "Not found"})

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        if not self.request_origin_ok():
            self.send_json(403, {"error": "Request origin was not accepted."})
            return
        if not self.authorized():
            self.send_json(401, {"error": "Sign in to continue."})
            return
        match = re.fullmatch(r"/api/course-progress/([a-z0-9-]{1,40})", path)
        if not match:
            self.send_json(404, {"error": "Not found"})
            return
        try:
            data = self.read_json()
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
            return
        reflection = data.get("reflection", "")
        completed = data.get("completed", False)
        if not isinstance(reflection, str) or len(reflection) > 4000 or not isinstance(completed, bool):
            self.send_json(400, {"error": "Progress is invalid."})
            return
        updated_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(DB_PATH) as db:
            db.execute("""INSERT INTO course_progress(lesson_id, reflection, completed, updated_at)
                VALUES(?, ?, ?, ?) ON CONFLICT(lesson_id) DO UPDATE SET
                reflection=excluded.reflection, completed=excluded.completed, updated_at=excluded.updated_at""",
                (match.group(1), reflection, int(completed), updated_at))
        self.send_json(200, {"lesson_id": match.group(1), "reflection": reflection, "completed": completed, "updated_at": updated_at})

    def do_DELETE(self) -> None:
        if not self.request_origin_ok():
            self.send_json(403, {"error": "Request origin was not accepted."})
            return
        if not self.authorized():
            self.send_json(401, {"error": "Sign in to continue."})
            return
        entry_id = urlparse(self.path).path.removeprefix("/api/entries/")
        if not entry_id or "/" in entry_id or entry_id == "clear":
            self.send_json(404, {"error": "Not found"})
            return
        with sqlite3.connect(DB_PATH) as db:
            cursor = db.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        self.send_json(200 if cursor.rowcount else 404, {"deleted": bool(cursor.rowcount)})


if __name__ == "__main__":
    if len(APP_PASSWORD) < 12:
        raise SystemExit("Set APP_PASSWORD to a password of at least 12 characters before starting the server.")
    init_db()
    print(f"Personal CBT app listening on http://{HOST}:{PORT}; journal database: {DB_PATH}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
