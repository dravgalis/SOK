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
                company_name TEXT,
                vacancies_count INTEGER NOT NULL DEFAULT 0,
                responses_count INTEGER NOT NULL DEFAULT 0,
                subscription_status TEXT,
                subscription_expires_at TEXT,
                selected_interface TEXT,
                access_token TEXT,
                metrics_updated_at TEXT,
                created_at TEXT NOT NULL,
                last_login TEXT NOT NULL
            )
            '''
        )
        _ensure_column(connection, 'users', 'company_name', 'TEXT')
        _ensure_column(connection, 'users', 'vacancies_count', 'INTEGER NOT NULL DEFAULT 0')
        _ensure_column(connection, 'users', 'responses_count', 'INTEGER NOT NULL DEFAULT 0')
        _ensure_column(connection, 'users', 'subscription_status', 'TEXT')
        _ensure_column(connection, 'users', 'subscription_expires_at', 'TEXT')
        _ensure_column(connection, 'users', 'selected_interface', 'TEXT')
        _ensure_column(connection, 'users', 'access_token', 'TEXT')
        _ensure_column(connection, 'users', 'metrics_updated_at', 'TEXT')
        connection.commit()


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = connection.execute(f'PRAGMA table_info({table})').fetchall()
    names = {column_info[1] for column_info in columns}
    if column not in names:
        connection.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')


def upsert_hh_user(
    *,
    hh_id: str,
    name: str,
    email: str | None,
    company_name: str | None,
    vacancies_count: int,
    responses_count: int,
    subscription_status: str | None,
    subscription_expires_at: str | None,
    selected_interface: str | None,
    access_token: str | None,
    metrics_updated_at: str | None,
) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()

    with _connect() as connection:
        existing = connection.execute('SELECT hh_id FROM users WHERE hh_id = ?', (hh_id,)).fetchone()

        if existing is None:
            connection.execute(
                '''
                INSERT INTO users (
                    hh_id, name, email, company_name, vacancies_count, responses_count, subscription_status,
                    subscription_expires_at, selected_interface, access_token, metrics_updated_at, created_at, last_login
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    hh_id,
                    name,
                    email,
                    company_name,
                    vacancies_count,
                    responses_count,
                    subscription_status,
                    subscription_expires_at,
                    selected_interface,
                    access_token,
                    metrics_updated_at,
                    timestamp,
                    timestamp,
                ),
            )
        else:
            connection.execute(
                '''
                UPDATE users
                SET name = ?, email = ?, company_name = ?, vacancies_count = ?, responses_count = ?,
                    subscription_status = ?, subscription_expires_at = ?, selected_interface = ?,
                    access_token = ?, metrics_updated_at = ?, last_login = ?
                WHERE hh_id = ?
                ''',
                (
                    name,
                    email,
                    company_name,
                    vacancies_count,
                    responses_count,
                    subscription_status,
                    subscription_expires_at,
                    selected_interface,
                    access_token,
                    metrics_updated_at,
                    timestamp,
                    hh_id,
                ),
            )

        connection.commit()


def get_all_users() -> list[dict[str, str | int | None]]:
    with _connect() as connection:
        rows = connection.execute(
            '''
            SELECT
                hh_id, name, email, company_name, vacancies_count, responses_count,
                subscription_status, subscription_expires_at, selected_interface,
                created_at, last_login
            FROM users
            ORDER BY datetime(last_login) DESC
            '''
        ).fetchall()

    return [
        {
            'hh_id': row['hh_id'],
            'name': row['name'],
            'email': row['email'],
            'company_name': row['company_name'],
            'vacancies_count': row['vacancies_count'],
            'responses_count': row['responses_count'],
            'subscription_status': row['subscription_status'],
            'subscription_expires_at': row['subscription_expires_at'],
            'selected_interface': row['selected_interface'],
            'created_at': row['created_at'],
            'last_login': row['last_login'],
        }
        for row in rows
    ]


def get_users_with_tokens() -> list[dict[str, str | int | None]]:
    with _connect() as connection:
        rows = connection.execute(
            '''
            SELECT hh_id, access_token, metrics_updated_at
            FROM users
            '''
        ).fetchall()

    return [
        {
            'hh_id': row['hh_id'],
            'access_token': row['access_token'],
            'metrics_updated_at': row['metrics_updated_at'],
        }
        for row in rows
    ]


def update_user_metrics(*, hh_id: str, company_name: str | None, vacancies_count: int, responses_count: int) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        connection.execute(
            '''
            UPDATE users
            SET company_name = ?, vacancies_count = ?, responses_count = ?, metrics_updated_at = ?
            WHERE hh_id = ?
            ''',
            (company_name, vacancies_count, responses_count, timestamp, hh_id),
        )
        connection.commit()


def get_user_access_token(hh_id: str) -> str | None:
    with _connect() as connection:
        row = connection.execute('SELECT access_token FROM users WHERE hh_id = ?', (hh_id,)).fetchone()
    if row is None:
        return None
    token = row['access_token']
    return token if isinstance(token, str) and token else None
