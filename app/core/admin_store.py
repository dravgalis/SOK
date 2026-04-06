import os
import sqlite3
from datetime import datetime, timezone


def _db_path() -> str:
    return os.getenv('USERS_DB_PATH', '/tmp/users.db')


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(_db_path())
    connection.row_factory = sqlite3.Row
    return connection


def init_users_table() -> None:
    with _connect() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS users (
                hh_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                created_at TEXT NOT NULL,
                last_login TEXT NOT NULL
            )
            '''
        )
        connection.commit()


def upsert_hh_user(*, hh_id: str, name: str, email: str | None) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()

    with _connect() as connection:
        existing = connection.execute('SELECT hh_id FROM users WHERE hh_id = ?', (hh_id,)).fetchone()

        if existing is None:
            connection.execute(
                '''
                INSERT INTO users (hh_id, name, email, created_at, last_login)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (hh_id, name, email, timestamp, timestamp),
            )
        else:
            connection.execute(
                'UPDATE users SET name = ?, email = ?, last_login = ? WHERE hh_id = ?',
                (name, email, timestamp, hh_id),
            )

        connection.commit()


def get_all_users() -> list[dict[str, str | None]]:
    with _connect() as connection:
        rows = connection.execute(
            'SELECT hh_id, name, email, created_at, last_login FROM users ORDER BY datetime(last_login) DESC'
        ).fetchall()

    return [
        {
            'hh_id': row['hh_id'],
            'name': row['name'],
            'email': row['email'],
            'created_at': row['created_at'],
            'last_login': row['last_login'],
        }
        for row in rows
    ]
