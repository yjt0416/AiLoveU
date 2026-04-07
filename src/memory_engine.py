from __future__ import annotations

import json
import math
import re
import sqlite3
import threading
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

from src.memory_schema import MEMORY_TYPE_LABELS, PROFILE_LABELS


@dataclass
class RetrievedMemory:
    memory_id: int
    memory_type: str
    content: str
    importance: float
    score: float


class MemoryManager:
    def __init__(
        self,
        db_path: str,
        short_term_turns: int = 8,
        top_k: int = 4,
        namespace: str = "default",
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.json_path = self.db_path.with_suffix(".json")
        self.short_term_turns = max(2, short_term_turns)
        self.top_k = max(1, top_k)
        self.namespace = namespace or "default"
        self.session_id = self._new_session_id()
        self._lock = threading.RLock()
        self._storage_mode = "sqlite"
        self._conn: sqlite3.Connection | None = None
        self._json_store = self._default_store()
        self._init_storage()
        self._restore_last_session()

    def set_namespace(self, namespace: str, restore_last_session: bool = True) -> None:
        self.namespace = namespace or "default"
        if restore_last_session:
            self._restore_last_session()
        else:
            self.start_new_session()

    def start_new_session(self) -> str:
        self.session_id = self._new_session_id()
        return self.session_id

    def store_turn(self, role: str, content: str) -> None:
        if not content or role not in {"user", "assistant"}:
            return

        record = {
            "namespace": self.namespace,
            "session_id": self.session_id,
            "role": role,
            "content": content.strip(),
            "created_at": self._utc_now(),
        }

        if self._storage_mode == "sqlite":
            self._store_turn_sqlite(record)
            return

        with self._lock:
            self._json_store["conversation_turns"].append(record)
            self._flush_json_store()

    def upsert_structured_memory(self, payload: Dict[str, Any]) -> None:
        profile = payload.get("profile", {})
        memories = payload.get("memories", [])

        for key, value in profile.items():
            self._upsert_profile(key, value)
        for item in memories:
            self._remember(
                memory_type=item["type"],
                content=item["content"],
                importance=float(item["importance"]),
            )

    def get_recent_messages(self) -> List[Dict[str, str]]:
        if self._storage_mode == "sqlite":
            return self._get_recent_messages_sqlite()

        with self._lock:
            turns = [
                turn
                for turn in self._json_store["conversation_turns"]
                if turn["namespace"] == self.namespace and turn["session_id"] == self.session_id
            ]
        turns = turns[-self.short_term_turns :]
        return [{"role": row["role"], "content": row["content"]} for row in turns]

    def get_transcript(self, limit: int = 200) -> List[Dict[str, str]]:
        if self._storage_mode == "sqlite":
            try:
                with self._lock:
                    rows = self._conn.execute(
                        """
                        SELECT role, content, created_at
                        FROM conversation_turns
                        WHERE namespace = ?
                        ORDER BY id ASC
                        LIMIT ?
                        """,
                        (self.namespace, limit),
                    ).fetchall()
                return [dict(row) for row in rows]
            except sqlite3.Error:
                self._fallback_from_sqlite()

        with self._lock:
            rows = [
                {
                    "role": item["role"],
                    "content": item["content"],
                    "created_at": item["created_at"],
                }
                for item in self._json_store["conversation_turns"]
                if item["namespace"] == self.namespace
            ]
        return rows[-limit:]

    def build_rag_context(self, user_input: str) -> str:
        profile = self.get_profile_snapshot()
        memories = self.retrieve_memories(user_input, self.top_k)

        if not profile and not memories:
            return ""

        lines = [
            "Relevant user memory for personalization. Use it only when it helps answer naturally.",
            "If memory conflicts with the user's latest message, trust the latest message.",
        ]

        if profile:
            lines.append("User profile:")
            for key, value in profile.items():
                lines.append(f"- {PROFILE_LABELS.get(key, key)}: {value}")

        if memories:
            lines.append("Relevant long-term memories:")
            for item in memories:
                lines.append(f"- {MEMORY_TYPE_LABELS.get(item.memory_type, item.memory_type)}: {item.content}")

        lines.append("Do not quote this block directly. Just use it to stay consistent and personalized.")
        return "\n".join(lines)

    def get_profile_snapshot(self) -> Dict[str, str]:
        if self._storage_mode == "sqlite":
            try:
                with self._lock:
                    rows = self._conn.execute(
                        """
                        SELECT profile_key, profile_value
                        FROM user_profile
                        WHERE namespace = ?
                        ORDER BY profile_key
                        """,
                        (self.namespace,),
                    ).fetchall()
                return {row["profile_key"]: row["profile_value"] for row in rows}
            except sqlite3.Error:
                self._fallback_from_sqlite()

        with self._lock:
            return dict(self._json_store["user_profile"].get(self.namespace, {}))

    def retrieve_memories(self, query: str, limit: int | None = None) -> List[RetrievedMemory]:
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        rows = self._load_memory_rows()
        retrieved: List[RetrievedMemory] = []
        for row in rows:
            memory_tokens = row["keywords"].split()
            score = self._score_memory(
                query_tokens=query_tokens,
                memory_tokens=memory_tokens,
                importance=float(row["importance"]),
                created_at=row["created_at"],
                access_count=int(row.get("access_count", 0)),
            )
            if score <= 0.12:
                continue
            retrieved.append(
                RetrievedMemory(
                    memory_id=int(row["id"]),
                    memory_type=row["memory_type"],
                    content=row["content"],
                    importance=float(row["importance"]),
                    score=score,
                )
            )

        retrieved.sort(key=lambda item: item.score, reverse=True)
        selected = retrieved[: limit or self.top_k]
        if selected:
            self._mark_memory_accessed([item.memory_id for item in selected])
        return selected

    def get_memory_summary(self) -> Dict[str, Any]:
        profile = self.get_profile_snapshot()
        recent_memories = self._load_memory_rows()[:3]
        return {
            "storage_mode": self._storage_mode,
            "namespace": self.namespace,
            "profile_count": len(profile),
            "memory_count": len(self._load_memory_rows()),
            "session_turn_count": len(self.get_recent_messages()),
            "profile_preview": [f"{PROFILE_LABELS.get(k, k)}: {v}" for k, v in list(profile.items())[:3]],
            "recent_memory_preview": [
                f"{MEMORY_TYPE_LABELS.get(item['memory_type'], item['memory_type'])}: {item['content']}"
                for item in recent_memories
            ],
        }

    def close(self) -> None:
        if self._conn is not None:
            with self._lock:
                self._conn.close()

    def _init_storage(self) -> None:
        try:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    namespace TEXT NOT NULL DEFAULT 'default',
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memory_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    namespace TEXT NOT NULL DEFAULT 'default',
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    keywords TEXT NOT NULL,
                    importance REAL NOT NULL DEFAULT 0.5,
                    source TEXT NOT NULL DEFAULT 'user',
                    created_at TEXT NOT NULL,
                    last_accessed_at TEXT,
                    access_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS user_profile (
                    namespace TEXT NOT NULL DEFAULT 'default',
                    profile_key TEXT NOT NULL,
                    profile_value TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'user',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (namespace, profile_key)
                );
                """
            )
            self._ensure_namespace_columns()
            self._conn.commit()
        except sqlite3.Error:
            self._storage_mode = "json"
            self._conn = None
            self._load_json_store()

    def _default_store(self) -> Dict[str, object]:
        return {
            "conversation_turns": [],
            "memory_items": [],
            "user_profile": {},
            "last_memory_id": 0,
        }

    def _load_json_store(self) -> None:
        if not self.json_path.exists():
            self._flush_json_store()
            return

        with self._lock:
            self._json_store = json.loads(self.json_path.read_text(encoding="utf-8"))

    def _flush_json_store(self) -> None:
        self.json_path.write_text(
            json.dumps(self._json_store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _store_turn_sqlite(self, record: Dict[str, str]) -> None:
        try:
            with self._lock:
                self._conn.execute(
                        """
                    INSERT INTO conversation_turns (namespace, session_id, role, content, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record["namespace"],
                        record["session_id"],
                        record["role"],
                        record["content"],
                        record["created_at"],
                    ),
                )
                self._conn.commit()
        except sqlite3.Error:
            self._fallback_from_sqlite()
            self.store_turn(record["role"], record["content"])

    def _get_recent_messages_sqlite(self) -> List[Dict[str, str]]:
        try:
            with self._lock:
                rows = self._conn.execute(
                    """
                    SELECT role, content
                    FROM conversation_turns
                    WHERE namespace = ? AND session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (self.namespace, self.session_id, self.short_term_turns),
                ).fetchall()
            return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]
        except sqlite3.Error:
            self._fallback_from_sqlite()
            return self.get_recent_messages()

    def _load_memory_rows(self) -> List[Dict[str, Any]]:
        if self._storage_mode == "sqlite":
            try:
                with self._lock:
                    rows = self._conn.execute(
                        """
                        SELECT id, memory_type, content, keywords, importance, created_at, access_count
                        FROM memory_items
                        WHERE namespace = ?
                        ORDER BY id DESC
                        LIMIT 200
                        """,
                        (self.namespace,),
                    ).fetchall()
                return [dict(row) for row in rows]
            except sqlite3.Error:
                self._fallback_from_sqlite()

        with self._lock:
            rows = [
                item for item in self._json_store["memory_items"]
                if item["namespace"] == self.namespace
            ]
            return list(reversed(rows[-200:]))

    def _upsert_profile(self, key: str, value: str) -> None:
        if self._storage_mode == "sqlite":
            try:
                with self._lock:
                    self._conn.execute(
                        """
                        INSERT INTO user_profile (namespace, profile_key, profile_value, source, updated_at)
                        VALUES (?, ?, ?, 'user', ?)
                        ON CONFLICT(namespace, profile_key)
                        DO UPDATE SET
                            profile_value = excluded.profile_value,
                            source = excluded.source,
                            updated_at = excluded.updated_at
                        """,
                        (self.namespace, key, value, self._utc_now()),
                    )
                    self._conn.commit()
                return
            except sqlite3.Error:
                self._fallback_from_sqlite()

        with self._lock:
            self._json_store["user_profile"].setdefault(self.namespace, {})[key] = value
            self._flush_json_store()

    def _remember(self, memory_type: str, content: str, importance: float) -> None:
        normalized = self._normalize_text(content)
        if not normalized:
            return

        rows = self._load_memory_rows()
        for row in rows[:30]:
            if row["memory_type"] == memory_type and self._normalize_text(row["content"]) == normalized:
                return

        record = {
            "namespace": self.namespace,
            "memory_type": memory_type,
            "content": content,
            "keywords": " ".join(self._tokenize(content)),
            "importance": importance,
            "source": "user",
            "created_at": self._utc_now(),
            "access_count": 0,
        }

        if self._storage_mode == "sqlite":
            try:
                with self._lock:
                    self._conn.execute(
                        """
                        INSERT INTO memory_items (namespace, memory_type, content, keywords, importance, source, created_at)
                        VALUES (?, ?, ?, ?, ?, 'user', ?)
                        """,
                        (
                            record["namespace"],
                            record["memory_type"],
                            record["content"],
                            record["keywords"],
                            record["importance"],
                            record["created_at"],
                        ),
                    )
                    self._conn.commit()
                return
            except sqlite3.Error:
                self._fallback_from_sqlite()

        with self._lock:
            self._json_store["last_memory_id"] += 1
            record["id"] = self._json_store["last_memory_id"]
            self._json_store["memory_items"].append(record)
            self._flush_json_store()

    def _mark_memory_accessed(self, memory_ids: Sequence[int]) -> None:
        if not memory_ids:
            return

        if self._storage_mode == "sqlite":
            placeholders = ",".join("?" for _ in memory_ids)
            try:
                with self._lock:
                    self._conn.execute(
                        f"""
                        UPDATE memory_items
                        SET access_count = access_count + 1,
                            last_accessed_at = ?
                        WHERE namespace = ? AND id IN ({placeholders})
                        """,
                        (self._utc_now(), self.namespace, *memory_ids),
                    )
                    self._conn.commit()
                return
            except sqlite3.Error:
                self._fallback_from_sqlite()

        with self._lock:
            lookup = set(memory_ids)
            for item in self._json_store["memory_items"]:
                if item["namespace"] == self.namespace and item["id"] in lookup:
                    item["access_count"] = int(item.get("access_count", 0)) + 1
                    item["last_accessed_at"] = self._utc_now()
            self._flush_json_store()

    def _restore_last_session(self) -> None:
        if self._storage_mode == "sqlite":
            try:
                with self._lock:
                    row = self._conn.execute(
                        """
                        SELECT session_id
                        FROM conversation_turns
                        WHERE namespace = ?
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        (self.namespace,),
                    ).fetchone()
                self.session_id = row["session_id"] if row else self._new_session_id()
                return
            except sqlite3.Error:
                self._fallback_from_sqlite()

        with self._lock:
            turns = [
                item for item in self._json_store["conversation_turns"]
                if item["namespace"] == self.namespace
            ]
        self.session_id = turns[-1]["session_id"] if turns else self._new_session_id()

    def _ensure_namespace_columns(self) -> None:
        self._ensure_column("conversation_turns", "namespace", "TEXT NOT NULL DEFAULT 'default'")
        self._ensure_column("memory_items", "namespace", "TEXT NOT NULL DEFAULT 'default'")
        if not self._user_profile_has_namespace():
            self._migrate_user_profile_namespace()

    def _ensure_column(self, table: str, column: str, ddl: str) -> None:
        cols = [row["name"] for row in self._conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def _user_profile_has_namespace(self) -> bool:
        cols = [row["name"] for row in self._conn.execute("PRAGMA table_info(user_profile)").fetchall()]
        return "namespace" in cols

    def _migrate_user_profile_namespace(self) -> None:
        self._conn.executescript(
            """
            ALTER TABLE user_profile RENAME TO user_profile_old;
            CREATE TABLE user_profile (
                namespace TEXT NOT NULL DEFAULT 'default',
                profile_key TEXT NOT NULL,
                profile_value TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'user',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (namespace, profile_key)
            );
            INSERT INTO user_profile (namespace, profile_key, profile_value, source, updated_at)
            SELECT 'default', profile_key, profile_value, source, updated_at
            FROM user_profile_old;
            DROP TABLE user_profile_old;
            """
        )

    def _fallback_from_sqlite(self) -> None:
        if self._storage_mode == "json":
            return

        self._storage_mode = "json"
        self._json_store = self._default_store()
        self._load_json_store()
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            self._conn = None

    def _score_memory(
        self,
        query_tokens: Sequence[str],
        memory_tokens: Sequence[str],
        importance: float,
        created_at: str,
        access_count: int,
    ) -> float:
        if not memory_tokens:
            return 0.0

        query_counter = Counter(query_tokens)
        memory_counter = Counter(memory_tokens)
        overlap = sum(min(query_counter[token], memory_counter[token]) for token in query_counter)
        lexical_score = overlap / math.sqrt(sum(query_counter.values()) * sum(memory_counter.values()))

        created_dt = datetime.fromisoformat(created_at)
        age_days = max((datetime.now(timezone.utc) - created_dt).total_seconds() / 86400.0, 0.0)
        recency_bonus = max(0.0, 0.18 - min(age_days, 30.0) * 0.006)
        access_bonus = min(access_count, 5) * 0.02
        return lexical_score + importance * 0.18 + recency_bonus + access_bonus

    def _tokenize(self, text: str) -> List[str]:
        text = (text or "").lower().strip()
        if not text:
            return []

        english_tokens = re.findall(r"[a-z0-9_]+", text)
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        chinese_tokens = [chinese_chars[idx] + chinese_chars[idx + 1] for idx in range(len(chinese_chars) - 1)]
        return english_tokens + chinese_tokens

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"[\W_]+", "", (text or "").lower())

    def _new_session_id(self) -> str:
        return uuid.uuid4().hex

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
