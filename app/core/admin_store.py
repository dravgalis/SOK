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
                    plan_code TEXT,
                    billing_amount TEXT,
                    billing_currency TEXT,
                    billing_status TEXT,
                    auto_renew_enabled INTEGER NOT NULL DEFAULT 0,
                    current_period_end TEXT,
                    payment_method_id TEXT,
                    last_payment_id TEXT,
                    last_payment_at TEXT,
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
                CREATE TABLE IF NOT EXISTS billing_payments (
                    payment_id TEXT PRIMARY KEY,
                    hh_id TEXT NOT NULL,
                    plan_code TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    processed_at TEXT
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
        _ensure_column(connection, 'users', 'plan_code', 'TEXT')
        _ensure_column(connection, 'users', 'billing_amount', 'TEXT')
        _ensure_column(connection, 'users', 'billing_currency', 'TEXT')
        _ensure_column(connection, 'users', 'billing_status', 'TEXT')
        _ensure_column(connection, 'users', 'auto_renew_enabled', 'INTEGER NOT NULL DEFAULT 0')
        _ensure_column(connection, 'users', 'current_period_end', 'TEXT')
        _ensure_column(connection, 'users', 'payment_method_id', 'TEXT')
        _ensure_column(connection, 'users', 'last_payment_id', 'TEXT')
        _ensure_column(connection, 'users', 'last_payment_at', 'TEXT')
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
                    subscription_status, subscription_expires_at, plan_code, current_period_end, billing_status, selected_interface,
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


def get_user_billing(hh_id: str) -> dict[str, str | bool | None] | None:
    with ENGINE.connect() as connection:
        row = connection.execute(
            text(
                '''
                SELECT
                    plan_code,
                    billing_amount,
                    billing_currency,
                    billing_status,
                    auto_renew_enabled,
                    current_period_end,
                    payment_method_id,
                    last_payment_id,
                    last_payment_at
                FROM users
                WHERE hh_id = :hh_id
                '''
            ),
            {'hh_id': hh_id},
        ).first()

    if row is None:
        return None

    return {
        'plan_code': row[0] if isinstance(row[0], str) and row[0] else None,
        'amount': row[1] if isinstance(row[1], str) and row[1] else None,
        'currency': row[2] if isinstance(row[2], str) and row[2] else None,
        'status': row[3] if isinstance(row[3], str) and row[3] else 'inactive',
        'auto_renew_enabled': bool(row[4]),
        'current_period_end': row[5] if isinstance(row[5], str) and row[5] else None,
        'payment_method_id': row[6] if isinstance(row[6], str) and row[6] else None,
        'last_payment_id': row[7] if isinstance(row[7], str) and row[7] else None,
        'last_payment_at': row[8] if isinstance(row[8], str) and row[8] else None,
    }


def update_user_billing(
    *,
    hh_id: str,
    plan_code: str | None = None,
    amount: str | None = None,
    currency: str | None = None,
    status: str | None = None,
    auto_renew_enabled: bool | None = None,
    current_period_end: str | None = None,
    payment_method_id: str | None = None,
    last_payment_id: str | None = None,
    last_payment_at: str | None = None,
    sync_legacy_subscription: bool = True,
) -> bool:
    set_parts: list[str] = []
    params: dict[str, object] = {'hh_id': hh_id}

    if plan_code is not None:
        set_parts.append('plan_code = :plan_code')
        params['plan_code'] = plan_code
    if amount is not None:
        set_parts.append('billing_amount = :billing_amount')
        params['billing_amount'] = amount
    if currency is not None:
        set_parts.append('billing_currency = :billing_currency')
        params['billing_currency'] = currency
    if status is not None:
        set_parts.append('billing_status = :billing_status')
        params['billing_status'] = status
    if auto_renew_enabled is not None:
        set_parts.append('auto_renew_enabled = :auto_renew_enabled')
        params['auto_renew_enabled'] = 1 if auto_renew_enabled else 0
    if current_period_end is not None:
        set_parts.append('current_period_end = :current_period_end')
        params['current_period_end'] = current_period_end
    if payment_method_id is not None:
        set_parts.append('payment_method_id = :payment_method_id')
        params['payment_method_id'] = payment_method_id
    if last_payment_id is not None:
        set_parts.append('last_payment_id = :last_payment_id')
        params['last_payment_id'] = last_payment_id
    if last_payment_at is not None:
        set_parts.append('last_payment_at = :last_payment_at')
        params['last_payment_at'] = last_payment_at

    if sync_legacy_subscription and current_period_end is not None:
        set_parts.append('subscription_expires_at = :subscription_expires_at')
        params['subscription_expires_at'] = current_period_end
    if sync_legacy_subscription and plan_code is not None:
        legacy_map = {'1_month': 'paid_1m', '6_months': 'paid_6m', '12_months': 'paid_1y'}
        set_parts.append('subscription_status = :subscription_status')
        params['subscription_status'] = legacy_map.get(plan_code)

    if not set_parts:
        return False

    with ENGINE.begin() as connection:
        result = connection.execute(
            text(f"UPDATE users SET {', '.join(set_parts)} WHERE hh_id = :hh_id"),
            params,
        )
        return result.rowcount > 0


def record_payment(
    *,
    payment_id: str,
    hh_id: str,
    plan_code: str,
    amount: str,
    currency: str,
    status: str = 'pending',
) -> None:
    with ENGINE.begin() as connection:
        connection.execute(
            text(
                '''
                INSERT INTO billing_payments (payment_id, hh_id, plan_code, amount, currency, status, created_at)
                VALUES (:payment_id, :hh_id, :plan_code, :amount, :currency, :status, :created_at)
                ON CONFLICT(payment_id) DO NOTHING
                '''
            ),
            {
                'payment_id': payment_id,
                'hh_id': hh_id,
                'plan_code': plan_code,
                'amount': amount,
                'currency': currency,
                'status': status,
                'created_at': datetime.now(timezone.utc).isoformat(),
            },
        )


def get_payment(payment_id: str) -> dict[str, str] | None:
    with ENGINE.connect() as connection:
        row = connection.execute(
            text(
                '''
                SELECT payment_id, hh_id, plan_code, amount, currency, status
                FROM billing_payments
                WHERE payment_id = :payment_id
                '''
            ),
            {'payment_id': payment_id},
        ).first()
    if row is None:
        return None
    return {
        'payment_id': str(row[0]),
        'hh_id': str(row[1]),
        'plan_code': str(row[2]),
        'amount': str(row[3]),
        'currency': str(row[4]),
        'status': str(row[5]),
    }


def mark_payment_processed(payment_id: str, status: str) -> bool:
    with ENGINE.begin() as connection:
        result = connection.execute(
            text(
                '''
                UPDATE billing_payments
                SET status = :status, processed_at = :processed_at
                WHERE payment_id = :payment_id AND status != 'succeeded'
                '''
            ),
            {'payment_id': payment_id, 'status': status, 'processed_at': datetime.now(timezone.utc).isoformat()},
        )
        return result.rowcount > 0


def get_users_for_recurring(now_iso: str) -> list[dict[str, str]]:
    with ENGINE.connect() as connection:
        rows = connection.execute(
            text(
                '''
                SELECT hh_id, plan_code, billing_amount, billing_currency, payment_method_id, current_period_end
                FROM users
                WHERE auto_renew_enabled = 1
                  AND payment_method_id IS NOT NULL
                  AND current_period_end IS NOT NULL
                  AND current_period_end <= :now_iso
                '''
            ),
            {'now_iso': now_iso},
        ).mappings()
        return [dict(row) for row in rows]


def update_user_subscription(*, hh_id: str, subscription_status: str | None, subscription_expires_at: str | None) -> bool:
    with ENGINE.begin() as connection:
        result = connection.execute(
            text(
                '''
                UPDATE users
                SET subscription_status = :subscription_status,
                    subscription_expires_at = :subscription_expires_at
                WHERE hh_id = :hh_id
                '''
            ),
            {
                'hh_id': hh_id,
                'subscription_status': subscription_status,
                'subscription_expires_at': subscription_expires_at,
            },
        )
        return result.rowcount > 0


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
