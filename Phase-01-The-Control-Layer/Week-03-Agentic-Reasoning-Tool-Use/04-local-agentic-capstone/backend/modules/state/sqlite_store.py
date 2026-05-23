import json
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class UserRecord:
    id: int
    username: str
    email: str


@dataclass
class MemoryRecord:
    id: str
    type: str
    content: Dict[str, Any]
    created_at: str
    last_accessed: str
    importance: float
    tags: List[str]
    token_count: int
    version: int


class SQLiteStateStore:
    def __init__(self, db_path: str, token_budget: int = 4000):
        self.db_path = db_path
        self.token_budget = token_budget
        self._lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT,
                    last_login_at TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_jti TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    revoked INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    token_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    importance REAL NOT NULL,
                    tags_json TEXT NOT NULL,
                    token_count INTEGER NOT NULL DEFAULT 0,
                    version INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS user_roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
                CREATE INDEX IF NOT EXISTS idx_messages_user_created ON messages(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_memories_user_type ON memories(user_id, type);
                CREATE INDEX IF NOT EXISTS idx_interactions_user_event ON interactions(user_id, event_type, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_refresh_user_jti ON refresh_tokens(user_id, token_jti);
                """
            )

    def create_user(self, username: str, email: str, password_hash: str) -> UserRecord:
        now = _now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (username, email, password_hash, now),
            )
            user_id = int(cur.lastrowid)
            return UserRecord(id=user_id, username=username, email=email)

    def assign_role_to_user(self, user_id: int, role: str) -> None:
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO user_roles (user_id, role, created_at) VALUES (?, ?, ?)",
                (user_id, role, now),
            )

    def get_roles_for_user_id(self, user_id: int) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT role FROM user_roles WHERE user_id = ?", (user_id,)).fetchall()
            return [r["role"] for r in rows]

    def get_roles_for_username(self, username: str) -> list[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if not row:
                return []
            user_id = int(row["id"])
            return self.get_roles_for_user_id(user_id)

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, username, email, password_hash, failed_login_attempts, locked_until FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[UserRecord]:
        with self._connect() as conn:
            row = conn.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                return None
            return UserRecord(id=int(row["id"]), username=row["username"], email=row["email"])

    def mark_login_failure(self, username: str, lockout_after: int = 5, lock_minutes: int = 15) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT failed_login_attempts FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            if not row:
                return
            attempts = int(row["failed_login_attempts"]) + 1
            lock_until = None
            if attempts >= lockout_after:
                lock_until = (datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)).isoformat()
                attempts = 0
            conn.execute(
                "UPDATE users SET failed_login_attempts = ?, locked_until = ? WHERE username = ?",
                (attempts, lock_until, username),
            )

    def clear_login_failures(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET failed_login_attempts = 0, locked_until = NULL, last_login_at = ? WHERE id = ?",
                (_now_iso(), user_id),
            )

    def is_user_locked(self, username: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT locked_until FROM users WHERE username = ?", (username,)).fetchone()
            if not row or not row["locked_until"]:
                return False
            try:
                return datetime.fromisoformat(row["locked_until"]) > datetime.now(timezone.utc)
            except Exception:
                return False

    def persist_refresh_token(
        self,
        user_id: int,
        token_jti: str,
        expires_at: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO refresh_tokens (user_id, token_jti, expires_at, created_at, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, token_jti, expires_at, _now_iso(), ip_address, user_agent),
            )

    def is_refresh_token_active(self, user_id: int, token_jti: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT revoked, expires_at FROM refresh_tokens WHERE user_id = ? AND token_jti = ?",
                (user_id, token_jti),
            ).fetchone()
            if not row:
                return False
            if int(row["revoked"]) == 1:
                return False
            try:
                return datetime.fromisoformat(row["expires_at"]) > datetime.now(timezone.utc)
            except Exception:
                return False

    def revoke_refresh_token(self, user_id: int, token_jti: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ? AND token_jti = ?",
                (user_id, token_jti),
            )

    def revoke_all_refresh_tokens(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ?",
                (user_id,),
            )

    def add_message(
        self,
        user_id: int,
        role: str,
        content: str,
        token_count: int,
        session_id: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (user_id, session_id, role, content, token_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, session_id, role, content, int(token_count), _now_iso()),
            )

    def get_recent_messages(self, user_id: int, limit: int = 12) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, token_count, created_at
                FROM messages
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
            return [dict(r) for r in reversed(rows)]

    def list_memories(self, user_id: int, types: Optional[List[str]] = None) -> List[MemoryRecord]:
        with self._connect() as conn:
            if types:
                placeholders = ",".join("?" for _ in types)
                rows = conn.execute(
                    f"SELECT * FROM memories WHERE user_id = ? AND type IN ({placeholders})",
                    [user_id] + types,
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM memories WHERE user_id = ?", (user_id,)).fetchall()

        result: List[MemoryRecord] = []
        for row in rows:
            result.append(
                MemoryRecord(
                    id=row["id"],
                    type=row["type"],
                    content=json.loads(row["content_json"]),
                    created_at=row["created_at"],
                    last_accessed=row["last_accessed"],
                    importance=float(row["importance"]),
                    tags=json.loads(row["tags_json"]),
                    token_count=int(row["token_count"]),
                    version=int(row["version"]),
                )
            )
        return result

    def add_memory(
        self,
        user_id: int,
        mtype: str,
        content: Dict[str, Any],
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        token_count: int = 0,
        memory_id: Optional[str] = None,
    ) -> MemoryRecord:
        mid = memory_id or str(uuid.uuid4())
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memories (id, user_id, type, content_json, created_at, last_accessed, importance, tags_json, token_count, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    mid,
                    user_id,
                    mtype,
                    json.dumps(content, ensure_ascii=False),
                    now,
                    now,
                    float(importance),
                    json.dumps(tags or []),
                    int(token_count),
                ),
            )
        return MemoryRecord(
            id=mid,
            type=mtype,
            content=content,
            created_at=now,
            last_accessed=now,
            importance=float(importance),
            tags=tags or [],
            token_count=int(token_count),
            version=1,
        )

    def upsert_memory_by_id(self, user_id: int, memory_id: str, **kwargs) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM memories WHERE user_id = ? AND id = ?",
                (user_id, memory_id),
            ).fetchone()
            if not row:
                return False

            updates = []
            params: List[Any] = []
            if "content" in kwargs:
                updates.append("content_json = ?")
                params.append(json.dumps(kwargs["content"], ensure_ascii=False))
            if "importance" in kwargs:
                updates.append("importance = ?")
                params.append(float(kwargs["importance"]))
            if "token_count" in kwargs:
                updates.append("token_count = ?")
                params.append(int(kwargs["token_count"]))
            if "tags" in kwargs:
                updates.append("tags_json = ?")
                params.append(json.dumps(kwargs["tags"], ensure_ascii=False))

            updates.append("last_accessed = ?")
            params.append(_now_iso())
            updates.append("version = version + 1")
            params.extend([user_id, memory_id])

            conn.execute(
                f"UPDATE memories SET {', '.join(updates)} WHERE user_id = ? AND id = ?",
                params,
            )
            return True

    def delete_memory(self, user_id: int, memory_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM memories WHERE user_id = ? AND id = ?", (user_id, memory_id))
            return cur.rowcount > 0

    def _recency_score(self, created_at: str) -> float:
        try:
            created = datetime.fromisoformat(created_at)
            age_seconds = (datetime.now(timezone.utc) - created).total_seconds()
            return 1.0 / (1.0 + age_seconds / 3600.0)
        except Exception:
            return 0.0

    def _score(self, mem: MemoryRecord) -> float:
        return 0.6 * float(mem.importance) + 0.4 * self._recency_score(mem.created_at)

    def hydrate_memories(
        self,
        user_id: int,
        types: Optional[List[str]] = None,
        max_tokens: Optional[int] = None,
        top_pct: float = 0.25,
        bottom_pct: float = 0.10,
    ) -> Dict[str, List[MemoryRecord]]:
        if max_tokens is None:
            max_tokens = self.token_budget

        candidates = self.list_memories(user_id=user_id, types=types)
        scored = sorted(candidates, key=lambda m: self._score(m), reverse=True)

        top_tokens = int(max_tokens * float(top_pct))
        bottom_tokens = int(max_tokens * float(bottom_pct))
        middle_tokens = max_tokens - top_tokens - bottom_tokens

        top: List[MemoryRecord] = []
        middle: List[MemoryRecord] = []
        bottom: List[MemoryRecord] = []

        tcur = 0
        for m in scored:
            if tcur < top_tokens and (tcur + m.token_count) <= top_tokens:
                top.append(m)
                tcur += m.token_count

        remaining = [m for m in scored if m not in top]
        bcur = 0
        for m in remaining:
            if bcur < bottom_tokens and (bcur + m.token_count) <= bottom_tokens:
                bottom.append(m)
                bcur += m.token_count

        used = set([m.id for m in top + bottom])
        mcur = 0
        for m in scored:
            if m.id in used:
                continue
            if (mcur + m.token_count) <= middle_tokens:
                middle.append(m)
                mcur += m.token_count

        ordered = top + middle + bottom
        now = _now_iso()
        with self._connect() as conn:
            for mem in ordered:
                conn.execute(
                    "UPDATE memories SET last_accessed = ? WHERE user_id = ? AND id = ?",
                    (now, user_id, mem.id),
                )

        return {"top": top, "middle": middle, "bottom": bottom, "ordered": ordered}

    def apply_patches(self, user_id: int, patches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for patch in patches:
            op = patch.get("op")
            if op == "upsert":
                memory_id = patch.get("id")
                if memory_id:
                    ok = self.upsert_memory_by_id(
                        user_id,
                        memory_id,
                        content=patch.get("content", {}),
                        importance=patch.get("importance", 0.5),
                        token_count=patch.get("token_count", 0),
                        tags=patch.get("tags", []),
                    )
                    results.append({"op": "upsert", "id": memory_id, "ok": ok})
                else:
                    created = self.add_memory(
                        user_id=user_id,
                        mtype=patch.get("type", "preferences"),
                        content=patch.get("content", {}),
                        importance=patch.get("importance", 0.5),
                        tags=patch.get("tags", []),
                        token_count=patch.get("token_count", 0),
                    )
                    results.append({"op": "upsert", "id": created.id, "ok": True})
            elif op == "delete":
                memory_id = patch.get("id")
                ok = False
                if memory_id:
                    ok = self.delete_memory(user_id=user_id, memory_id=memory_id)
                results.append({"op": "delete", "id": memory_id, "ok": ok})
            else:
                results.append({"op": op, "ok": False, "reason": "unsupported"})

        return results

    def record_interaction(
        self,
        event_type: str,
        payload: Dict[str, Any],
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO interactions (user_id, event_type, payload_json, ip_address, user_agent, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    event_type,
                    json.dumps(payload, ensure_ascii=False),
                    ip_address,
                    user_agent,
                    _now_iso(),
                ),
            )

    def search_interactions(
        self,
        user_id: int,
        event_type: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if event_type:
                rows = conn.execute(
                    """
                    SELECT id, event_type, payload_json, ip_address, user_agent, created_at
                    FROM interactions
                    WHERE user_id = ? AND event_type = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (user_id, event_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, event_type, payload_json, ip_address, user_agent, created_at
                    FROM interactions
                    WHERE user_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                ).fetchall()

        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "id": int(row["id"]),
                    "event_type": row["event_type"],
                    "payload": json.loads(row["payload_json"]),
                    "ip_address": row["ip_address"],
                    "user_agent": row["user_agent"],
                    "created_at": row["created_at"],
                }
            )
        return result
