import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine


def _database_url() -> str:
    postgres_url = os.getenv('DATABASE_URL', '').strip()
    if postgres_url:
        if postgres_url.startswith('postgres://'):
            return f"postgresql+psycopg://{postgres_url.removeprefix('postgres://')}"
        if postgres_url.startswith('postgresql://'):
            return f"postgresql+psycopg://{postgres_url.removeprefix('postgresql://')}"
        return postgres_url

    sqlite_path = os.getenv('USERS_DB_PATH', '/tmp/users.db')
    resolved_path = Path(sqlite_path).expanduser().resolve()
    return f'sqlite:///{resolved_path}'


def _engine() -> Engine:
    return create_engine(_database_url(), future=True, pool_pre_ping=True)


ENGINE = _engine()


def init_users_table() -> None:
    with ENGINE.begin() as connection:
        connection.execute(
            text(
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
        )
        connection.execute(
            text(
                '''
                CREATE TABLE IF NOT EXISTS user_vacancies (
                    hh_id TEXT NOT NULL,
                    vacancy_id TEXT NOT NULL,
                    vacancy_name TEXT NOT NULL,
                    vacancy_status TEXT NOT NULL,
                    responses_count INTEGER NOT NULL DEFAULT 0,
                    cached_at TEXT NOT NULL,
                    PRIMARY KEY (hh_id, vacancy_id)
                )
                '''
            )
        )
        connection.execute(
            text(
                '''
                CREATE TABLE IF NOT EXISTS vacancy_responses_cache (
                    hh_id TEXT NOT NULL,
                    vacancy_id TEXT NOT NULL,
                    response_id TEXT NOT NULL,
                    candidate_name TEXT,
                    specialization TEXT,
                    experience TEXT,
                    matched_skills_count INTEGER NOT NULL DEFAULT 0,
                    score_points INTEGER NOT NULL DEFAULT 0,
                    cached_at TEXT NOT NULL,
                    PRIMARY KEY (hh_id, vacancy_id, response_id)
                )
                '''
            )
        )
        _ensure_column(connection, 'users', 'company_name', 'TEXT')
        _ensure_column(connection, 'users', 'vacancies_count', 'INTEGER NOT NULL DEFAULT 0')
        _ensure_column(connection, 'users', 'responses_count', 'INTEGER NOT NULL DEFAULT 0')
        _ensure_column(connection, 'users', 'subscription_status', 'TEXT')
        _ensure_column(connection, 'users', 'subscription_expires_at', 'TEXT')
        _ensure_column(connection, 'users', 'selected_interface', 'TEXT')
        _ensure_column(connection, 'users', 'access_token', 'TEXT')
        _ensure_column(connection, 'users', 'metrics_updated_at', 'TEXT')


def _ensure_column(connection: Connection, table: str, column: str, definition: str) -> None:
    if ENGINE.dialect.name == 'sqlite':
        rows = connection.execute(text(f'PRAGMA table_info({table})')).fetchall()
        names = {row[1] for row in rows}
        if column not in names:
            connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {definition}'))
        return

    connection.execute(text(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}'))

    connection.execute(text(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}'))

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

    with ENGINE.begin() as connection:
        connection.execute(
            text(
                '''
                INSERT INTO users (
                    hh_id, name, email, company_name, vacancies_count, responses_count, subscription_status,
                    subscription_expires_at, selected_interface, access_token, metrics_updated_at, created_at, last_login
                )
                VALUES (
                    :hh_id, :name, :email, :company_name, :vacancies_count, :responses_count, :subscription_status,
                    :subscription_expires_at, :selected_interface, :access_token, :metrics_updated_at, :created_at, :last_login
                )
                ON CONFLICT(hh_id) DO UPDATE SET
                    name = excluded.name,
                    email = excluded.email,
                    company_name = excluded.company_name,
                    vacancies_count = excluded.vacancies_count,
                    responses_count = excluded.responses_count,
                    subscription_status = excluded.subscription_status,
                    subscription_expires_at = excluded.subscription_expires_at,
                    selected_interface = excluded.selected_interface,
                    access_token = excluded.access_token,
                    metrics_updated_at = excluded.metrics_updated_at,
                    last_login = excluded.last_login
                '''
            ),
            {
                'hh_id': hh_id,
                'name': name,
                'email': email,
                'company_name': company_name,
                'vacancies_count': vacancies_count,
                'responses_count': responses_count,
                'subscription_status': subscription_status,
                'subscription_expires_at': subscription_expires_at,
                'selected_interface': selected_interface,
                'access_token': access_token,
                'metrics_updated_at': metrics_updated_at,
                'created_at': timestamp,
                'last_login': timestamp,
            },
        )


def get_all_users() -> list[dict[str, str | int | None]]:
    with ENGINE.connect() as connection:
        rows = connection.execute(
            text(
                '''
                SELECT
                    hh_id, name, email, company_name, vacancies_count, responses_count,
                    subscription_status, subscription_expires_at, selected_interface,
                    created_at, last_login
                FROM users
                ORDER BY last_login DESC
                '''
            )
        ).mappings()

        return [dict(row) for row in rows]


def get_users_with_tokens() -> list[dict[str, str | int | None]]:
    with ENGINE.connect() as connection:
        rows = connection.execute(text('SELECT hh_id, access_token, metrics_updated_at FROM users')).mappings()
        return [dict(row) for row in rows]


def update_user_metrics(*, hh_id: str, company_name: str | None, vacancies_count: int, responses_count: int) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    with ENGINE.begin() as connection:
        connection.execute(
            text(
                '''
                UPDATE users
                SET company_name = :company_name, vacancies_count = :vacancies_count,
                    responses_count = :responses_count, metrics_updated_at = :metrics_updated_at
                WHERE hh_id = :hh_id
                '''
            ),
            {
                'company_name': company_name,
                'vacancies_count': vacancies_count,
                'responses_count': responses_count,
                'metrics_updated_at': timestamp,
                'hh_id': hh_id,
            },
        )


def get_user_access_token(hh_id: str) -> str | None:
    with ENGINE.connect() as connection:
        row = connection.execute(text('SELECT access_token FROM users WHERE hh_id = :hh_id'), {'hh_id': hh_id}).first()
    if row is None:
        return None
    token = row[0]
    return token if isinstance(token, str) and token else None


def get_user_subscription(hh_id: str) -> tuple[str | None, str | None]:
    with ENGINE.connect() as connection:
        row = connection.execute(
            text('SELECT subscription_status, subscription_expires_at FROM users WHERE hh_id = :hh_id'),
            {'hh_id': hh_id},
        ).first()

    if row is None:
        return None, None

    status_raw = row[0]
    expires_raw = row[1]
    status_value = status_raw if isinstance(status_raw, str) and status_raw else None
    expires_value = expires_raw if isinstance(expires_raw, str) and expires_raw else None
    return status_value, expires_value


def get_cached_user_vacancies(hh_id: str) -> tuple[str | None, list[dict[str, str | int]]]:
    with ENGINE.connect() as connection:
        cached_at_row = connection.execute(
            text(
                '''
                SELECT MAX(cached_at) AS cached_at
                FROM user_vacancies
                WHERE hh_id = :hh_id
                '''
            ),
            {'hh_id': hh_id},
        ).first()
        cached_at = cached_at_row[0] if cached_at_row and isinstance(cached_at_row[0], str) else None

        rows = connection.execute(
            text(
                '''
                SELECT vacancy_id, vacancy_name, vacancy_status, responses_count
                FROM user_vacancies
                WHERE hh_id = :hh_id
                ORDER BY vacancy_status DESC, vacancy_name ASC
                '''
            ),
            {'hh_id': hh_id},
        ).mappings()

        items = [
            {
                'id': row['vacancy_id'],
                'name': row['vacancy_name'],
                'status': row['vacancy_status'],
                'responses_count': row['responses_count'],
            }
            for row in rows
        ]
        return cached_at, items


def replace_user_vacancies(hh_id: str, vacancies: list[dict[str, str | int]], cached_at: str) -> None:
    with ENGINE.begin() as connection:
        connection.execute(text('DELETE FROM user_vacancies WHERE hh_id = :hh_id'), {'hh_id': hh_id})
        for vacancy in vacancies:
            connection.execute(
                text(
                    '''
                    INSERT INTO user_vacancies (hh_id, vacancy_id, vacancy_name, vacancy_status, responses_count, cached_at)
                    VALUES (:hh_id, :vacancy_id, :vacancy_name, :vacancy_status, :responses_count, :cached_at)
                    '''
                ),
                {
                    'hh_id': hh_id,
                    'vacancy_id': str(vacancy.get('id', '')),
                    'vacancy_name': str(vacancy.get('name', 'Без названия')),
                    'vacancy_status': str(vacancy.get('status', 'active')),
                    'responses_count': int(vacancy.get('responses_count', 0)),
                    'cached_at': cached_at,
                },
            )


def get_cached_vacancy_responses(hh_id: str, vacancy_id: str) -> tuple[str | None, list[dict[str, str | int]]]:
    with ENGINE.connect() as connection:
        cached_at_query = text(
            '''
            SELECT MAX(cached_at) AS cached_at
            FROM vacancy_responses_cache
            WHERE hh_id = :hh_id AND vacancy_id = :vacancy_id
            '''
        )
        cached_at_row = connection.execute(cached_at_query, {'hh_id': hh_id, 'vacancy_id': vacancy_id}).first()
        cached_at = cached_at_row[0] if cached_at_row and isinstance(cached_at_row[0], str) else None

        rows_query = text(
            '''
            SELECT response_id, candidate_name, specialization, experience, matched_skills_count, score_points
            FROM vacancy_responses_cache
            WHERE hh_id = :hh_id AND vacancy_id = :vacancy_id
            ORDER BY score_points DESC, candidate_name ASC
            '''
        )
        rows = connection.execute(rows_query, {'hh_id': hh_id, 'vacancy_id': vacancy_id}).mappings()

        items = [
            {
                'response_id': row['response_id'],
                'name': row['candidate_name'],
                'specialization': row['specialization'],
                'experience': row['experience'],
                'matched_skills_count': row['matched_skills_count'],
                'score_points': row['score_points'],
            }
            for row in rows
        ]
        return cached_at, items


def replace_vacancy_responses(
    hh_id: str, vacancy_id: str, responses: list[dict[str, str | int]], cached_at: str
) -> None:
    with ENGINE.begin() as connection:
        connection.execute(
            text('DELETE FROM vacancy_responses_cache WHERE hh_id = :hh_id AND vacancy_id = :vacancy_id'),
            {'hh_id': hh_id, 'vacancy_id': vacancy_id},
        )
        for row in responses:
            connection.execute(
                text(
                    '''
                    INSERT INTO vacancy_responses_cache (
                        hh_id, vacancy_id, response_id, candidate_name, specialization, experience,
                        matched_skills_count, score_points, cached_at
                    )
                    VALUES (
                        :hh_id, :vacancy_id, :response_id, :candidate_name, :specialization, :experience,
                        :matched_skills_count, :score_points, :cached_at
                    )
                    '''
                ),
                {
                    'hh_id': hh_id,
                    'vacancy_id': vacancy_id,
                    'response_id': str(row.get('response_id', '')),
                    'candidate_name': str(row.get('name', '')),
                    'specialization': str(row.get('specialization', '')),
                    'experience': str(row.get('experience', '')),
                    'matched_skills_count': int(row.get('matched_skills_count', 0)),
                    'score_points': int(row.get('score_points', 0)),
                    'cached_at': cached_at,
                },
            )
