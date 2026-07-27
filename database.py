from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ALLOWED_STATUSES = {"new", "in_progress", "done"}
ALLOWED_PRIORITIES = {"low", "medium", "high"}


class TicketRepository:
    """SQLite repository for employee service requests."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self, seed: bool = True) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    department TEXT NOT NULL,
                    requester TEXT NOT NULL,
                    priority TEXT NOT NULL CHECK(priority IN ('low', 'medium', 'high')),
                    status TEXT NOT NULL CHECK(status IN ('new', 'in_progress', 'done')),
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
            if seed and count == 0:
                now = self._now()
                rows = [
                    ("Настроить доступ к CRM", "Продажи", "Анна К.", "high", "new", "Нужен доступ новому менеджеру", now, now),
                    ("Заменить клавиатуру", "Бухгалтерия", "Игорь П.", "medium", "in_progress", "Несколько клавиш не работают", now, now),
                    ("Создать почту сотруднику", "HR", "Мария С.", "low", "done", "Корпоративная почта для стажёра", now, now),
                ]
                conn.executemany(
                    """
                    INSERT INTO tickets
                    (title, department, requester, priority, status, description, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

    def list_tickets(self, status: str = "", search: str = "") -> list[dict[str, Any]]:
        query = "SELECT * FROM tickets WHERE 1=1"
        params: list[Any] = []
        if status:
            if status not in ALLOWED_STATUSES:
                raise ValueError("Недопустимый статус")
            query += " AND status = ?"
            params.append(status)
        if search:
            query += " AND (title LIKE ? OR department LIKE ? OR requester LIKE ?)"
            value = f"%{search.strip()}%"
            params.extend([value, value, value])
        query += " ORDER BY id DESC"
        with self.connection() as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def create_ticket(self, payload: dict[str, Any]) -> dict[str, Any]:
        required = ("title", "department", "requester", "priority")
        missing = [field for field in required if not str(payload.get(field, "")).strip()]
        if missing:
            raise ValueError(f"Заполните поля: {', '.join(missing)}")

        priority = str(payload["priority"])
        if priority not in ALLOWED_PRIORITIES:
            raise ValueError("Недопустимый приоритет")

        now = self._now()
        values = (
            str(payload["title"]).strip(),
            str(payload["department"]).strip(),
            str(payload["requester"]).strip(),
            priority,
            "new",
            str(payload.get("description", "")).strip(),
            now,
            now,
        )
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tickets
                (title, department, requester, priority, status, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            row = conn.execute("SELECT * FROM tickets WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)

    def update_status(self, ticket_id: int, status: str) -> dict[str, Any]:
        if status not in ALLOWED_STATUSES:
            raise ValueError("Недопустимый статус")
        with self.connection() as conn:
            cursor = conn.execute(
                "UPDATE tickets SET status = ?, updated_at = ? WHERE id = ?",
                (status, self._now(), ticket_id),
            )
            if cursor.rowcount == 0:
                raise KeyError("Заявка не найдена")
            row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            return dict(row)

    def stats(self) -> dict[str, int]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM tickets GROUP BY status"
            ).fetchall()
        result = {"total": 0, "new": 0, "in_progress": 0, "done": 0}
        for row in rows:
            result[row["status"]] = row["count"]
            result["total"] += row["count"]
        return result

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
