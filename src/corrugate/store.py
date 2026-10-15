"""Durable board data. Terminal attachment deliberately lives outside the archive."""

from __future__ import annotations

import re
import sqlite3
import subprocess
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 1
APPLICATION_ID = 0x434F5252
MAX_SOURCE_BYTES = 32 * 1024 * 1024


class BoardError(ValueError):
    pass


def validate_session(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
        raise BoardError("session_id must be 1–128 letters, digits, underscores, dots or hyphens")
    return value


def project_root(cwd: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=3, check=True,
        )
        return Path(result.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        return cwd.resolve()


def board_path(session: str, root: Path, override: Path | None = None) -> Path:
    validate_session(session)
    return (override or root / ".corrugate" / f"{session}.sqlite3").resolve()


@dataclass(frozen=True)
class Item:
    id: str
    ordinal: int
    kind: str
    description: str
    marker: str
    quote: str
    revision: int
    render_status: str
    render_error: str


class Board:
    def __init__(self, path: Path, session: str | None = None, *, create: bool = False):
        self.path = path.resolve()
        if create:
            if session is None:
                raise BoardError("A conversation ID is required to create a board")
            validate_session(session)
            self.path.parent.mkdir(parents=True, exist_ok=True)
        elif not self.path.is_file():
            raise BoardError(f"Board does not exist: {self.path}")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            app_id = db.execute("PRAGMA application_id").fetchone()[0]
            tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if version == 0 and not tables and create:
                db.execute("CREATE TABLE board (session_id TEXT NOT NULL, generation INTEGER NOT NULL)")
                db.execute("INSERT INTO board VALUES (?, 0)", (session,))
                db.execute("""CREATE TABLE items (
                    id TEXT PRIMARY KEY, ordinal INTEGER NOT NULL UNIQUE,
                    kind TEXT NOT NULL, description TEXT NOT NULL,
                    marker TEXT NOT NULL UNIQUE, quote TEXT NOT NULL,
                    source BLOB NOT NULL, mime TEXT NOT NULL,
                    revision INTEGER NOT NULL, preview BLOB,
                    render_status TEXT NOT NULL, render_error TEXT NOT NULL DEFAULT ''
                )""")
                db.execute(f"PRAGMA application_id={APPLICATION_ID}")
                db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            elif version != SCHEMA_VERSION or app_id != APPLICATION_ID:
                raise BoardError(f"Not a supported corrugate board (schema {version})")
            self.session = db.execute("SELECT session_id FROM board").fetchone()[0]
            if session is not None and self.session != session:
                raise BoardError("Board belongs to another conversation")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA busy_timeout=5000")
            with db:
                yield db
        finally:
            db.close()

    def publish(self, payload: dict, cwd: Path) -> Item:
        kind = payload.get("kind")
        if kind not in ("math", "image"):
            raise BoardError("kind must be 'math' or 'image'")
        description = payload.get("description", "")
        quote = payload.get("quote", "")
        if not isinstance(description, str) or not isinstance(quote, str):
            raise BoardError("description and quote must be strings")
        if kind == "math":
            source_text = payload.get("source")
            if not isinstance(source_text, str) or not source_text.strip():
                raise BoardError("Math requires nonempty source containing a LaTeX math body")
            source = source_text.encode("utf-8")
            mime = "text/x-latex"
        else:
            filename = payload.get("path")
            if not isinstance(filename, str) or not filename:
                raise BoardError("Image requires a local path")
            path = (cwd / filename).resolve()
            mime = {
                ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".webp": "image/webp", ".svg": "image/svg+xml",
            }.get(path.suffix.lower())
            if mime is None:
                raise BoardError("Supported image files: PNG, JPEG, WebP, SVG")
            with path.open("rb") as stream:
                source = stream.read(MAX_SOURCE_BYTES + 1)
        if len(source) > MAX_SOURCE_BYTES:
            raise BoardError("Source exceeds the 32 MiB limit")
        item_id = payload.get("item_id")
        if item_id is not None and not isinstance(item_id, str):
            raise BoardError("item_id must be a string")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if item_id is None:
                item_id = uuid.uuid4().hex
                ordinal = db.execute("SELECT coalesce(max(ordinal), 0) + 1 FROM items").fetchone()[0]
                db.execute(
                    "INSERT INTO items VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, NULL, 'pending', '')",
                    (item_id, ordinal, kind, description, f"[CG:{item_id}]", quote, source, mime),
                )
            else:
                result = db.execute(
                    """UPDATE items SET kind=?, description=?, source=?, mime=?,
                    revision=revision+1, preview=NULL, render_status='pending', render_error=''
                    WHERE id=?""", (kind, description, source, mime, item_id),
                )
                if result.rowcount != 1:
                    raise BoardError("Cannot update an unknown item_id")
            db.execute("UPDATE board SET generation=generation+1")
        return self.item(item_id)

    def items(self) -> list[Item]:
        with self.connect() as db:
            rows = db.execute("""SELECT id, ordinal, kind, description, marker, quote, revision,
                render_status, render_error FROM items ORDER BY ordinal""").fetchall()
        return [Item(**dict(row)) for row in rows]

    def item(self, item_id: str) -> Item:
        return next(item for item in self.items() if item.id == item_id)

    def generation(self) -> int:
        with self.connect() as db:
            return db.execute("SELECT generation FROM board").fetchone()[0]

    def source(self, item_id: str) -> tuple[bytes, str, int]:
        with self.connect() as db:
            row = db.execute("SELECT source, mime, revision FROM items WHERE id=?", (item_id,)).fetchone()
        return bytes(row[0]), row[1], row[2]

    def preview(self, item_id: str) -> bytes | None:
        with self.connect() as db:
            return db.execute("SELECT preview FROM items WHERE id=?", (item_id,)).fetchone()[0]

    def finish_render(self, item_id: str, revision: int, png: bytes | None, error: str = "") -> None:
        with self.connect() as db:
            result = db.execute("""UPDATE items SET preview=?, render_status=?, render_error=?
                WHERE id=? AND revision=? AND render_status='pending'""",
                (png, "error" if error else "ready", error[:2000], item_id, revision))
            if result.rowcount:
                db.execute("UPDATE board SET generation=generation+1")
