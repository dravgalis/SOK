import os
import uuid
from datetime import datetime, timedelta, timezone
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
                    trial_3d_granted INTEGER NOT NULL DEFAULT 0,
                    plan_code TEXT,
                    billing_amount TEXT,
                    billing_currency TEXT,
                    billing_status TEXT,
                    auto_renew_enabled INTEGER NOT NULL DEFAULT 0,
                    current_period_end TEXT,
                    payment_method_id TEXT,
                    last_payment_id TEXT,
                    last_payment_at TEXT,
                    unlocked_themes TEXT,
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
                    provider_status TEXT,
                    failure_reason TEXT,
                    product_type TEXT NOT NULL DEFAULT 'subscription',
                    theme_code TEXT,
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
        connection.execute(
            text(
                '''
                CREATE TABLE IF NOT EXISTS support_messages (
                    message_id TEXT PRIMARY KEY,
                    hh_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    sender_role TEXT NOT NULL DEFAULT 'user',
                    read_by_admin INTEGER NOT NULL DEFAULT 0,
                    read_by_user INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                '''
            )
        )
        _ensure_column(connection, 'users', 'company_name', 'TEXT')
        _ensure_column(connection, 'users', 'vacancies_count', 'INTEGER NOT NULL DEFAULT 0')
        _ensure_column(connection, 'users', 'responses_count', 'INTEGER NOT NULL DEFAULT 0')
        _ensure_column(connection, 'users', 'subscription_status', 'TEXT')
        _ensure_column(connection, 'users', 'subscription_expires_at', 'TEXT')
        _ensure_column(connection, 'users', 'trial_3d_granted', 'INTEGER NOT NULL DEFAULT 0')
        _ensure_column(connection, 'users', 'plan_code', 'TEXT')
        _ensure_column(connection, 'users', 'billing_amount', 'TEXT')
        _ensure_column(connection, 'users', 'billing_currency', 'TEXT')
        _ensure_column(connection, 'users', 'billing_status', 'TEXT')
        _ensure_column(connection, 'users', 'auto_renew_enabled', 'INTEGER NOT NULL DEFAULT 0')
        _ensure_column(connection, 'users', 'current_period_end', 'TEXT')
        _ensure_column(connection, 'users', 'payment_method_id', 'TEXT')
        _ensure_column(connection, 'users', 'last_payment_id', 'TEXT')
        _ensure_column(connection, 'users', 'last_payment_at', 'TEXT')
        _ensure_column(connection, 'users', 'unlocked_themes', 'TEXT')
        _ensure_column(connection, 'users', 'selected_interface', 'TEXT')
        _ensure_column(connection, 'users', 'access_token', 'TEXT')
        _ensure_column(connection, 'users', 'metrics_updated_at', 'TEXT')
        _ensure_column(connection, 'billing_payments', 'provider_status', 'TEXT')
        _ensure_column(connection, 'billing_payments', 'failure_reason', 'TEXT')
        _ensure_column(connection, 'billing_payments', 'product_type', "TEXT NOT NULL DEFAULT 'subscription'")
        _ensure_column(connection, 'billing_payments', 'theme_code', 'TEXT')
        _ensure_column(connection, 'support_messages', 'sender_role', "TEXT NOT NULL DEFAULT 'user'")
        _ensure_column(connection, 'support_messages', 'read_by_admin', 'INTEGER NOT NULL DEFAULT 0')
        _ensure_column(connection, 'support_messages', 'read_by_user', 'INTEGER NOT NULL DEFAULT 0')
        connection.execute(text('UPDATE users SET auto_renew_enabled = 0 WHERE auto_renew_enabled != 0'))


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
    trial_3d_granted: bool,
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
                    subscription_expires_at, trial_3d_granted, selected_interface, access_token, metrics_updated_at, created_at, last_login
                )
                VALUES (
                    :hh_id, :name, :email, :company_name, :vacancies_count, :responses_count, :subscription_status,
                    :subscription_expires_at, :trial_3d_granted, :selected_interface, :access_token, :metrics_updated_at, :created_at, :last_login
                )
                ON CONFLICT(hh_id) DO UPDATE SET
                    name = excluded.name,
                    email = excluded.email,
                    company_name = excluded.company_name,
                    vacancies_count = excluded.vacancies_count,
                    responses_count = excluded.responses_count,
                    subscription_status = excluded.subscription_status,
                    subscription_expires_at = excluded.subscription_expires_at,
                    trial_3d_granted = excluded.trial_3d_granted,
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
                'trial_3d_granted': 1 if trial_3d_granted else 0,
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
                    subscription_status, subscription_expires_at, trial_3d_granted,
                    plan_code, current_period_end, billing_status, selected_interface,
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


def add_support_message(*, hh_id: str, message: str, sender_role: str = 'user') -> str:
    message_id = str(uuid.uuid4())
    is_admin = sender_role == 'admin'
    with ENGINE.begin() as connection:
        connection.execute(
            text(
                '''
                INSERT INTO support_messages (message_id, hh_id, message, sender_role, read_by_admin, read_by_user, created_at)
                VALUES (:message_id, :hh_id, :message, :sender_role, :read_by_admin, :read_by_user, :created_at)
                '''
            ),
            {
                'message_id': message_id,
                'hh_id': hh_id,
                'message': message,
                'sender_role': 'admin' if is_admin else 'user',
                'read_by_admin': 1 if is_admin else 0,
                'read_by_user': 0 if is_admin else 1,
                'created_at': datetime.now(timezone.utc).isoformat(),
            },
        )
    return message_id


def get_support_messages(limit: int = 200) -> list[dict[str, str]]:
    normalized_limit = max(1, min(limit, 1000))
    with ENGINE.connect() as connection:
        rows = connection.execute(
            text(
                '''
                SELECT message_id, hh_id, message, created_at
                FROM support_messages
                ORDER BY created_at DESC
                LIMIT :limit
                '''
            ),
            {'limit': normalized_limit},
        ).mappings()
        return [dict(row) for row in rows]


def get_support_chats(limit: int = 500) -> list[dict[str, object]]:
    normalized_limit = max(1, min(limit, 2000))
    with ENGINE.connect() as connection:
        rows = connection.execute(
            text(
                '''
                SELECT
                    sm.hh_id,
                    u.company_name,
                    MAX(sm.created_at) AS last_message_at,
                    SUM(CASE WHEN sm.sender_role = 'user' AND sm.read_by_admin = 0 THEN 1 ELSE 0 END) AS unread_by_admin,
                    SUM(CASE WHEN sm.sender_role = 'admin' AND sm.read_by_user = 0 THEN 1 ELSE 0 END) AS unread_by_user
                FROM support_messages sm
                LEFT JOIN users u ON u.hh_id = sm.hh_id
                GROUP BY sm.hh_id, u.company_name
                ORDER BY
                    CASE WHEN SUM(CASE WHEN sm.sender_role = 'user' AND sm.read_by_admin = 0 THEN 1 ELSE 0 END) > 0 THEN 0 ELSE 1 END,
                    MAX(sm.created_at) DESC
                LIMIT :limit
                '''
            ),
            {'limit': normalized_limit},
        ).mappings()
        return [dict(row) for row in rows]


def purge_old_support_chats(days: int = 14) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    cutoff_iso = cutoff.isoformat()
    with ENGINE.begin() as connection:
        result = connection.execute(
            text(
                '''
                DELETE FROM support_messages
                WHERE hh_id IN (
                    SELECT hh_id
                    FROM support_messages
                    GROUP BY hh_id
                    HAVING MAX(created_at) < :cutoff_iso
                )
                '''
            ),
            {'cutoff_iso': cutoff_iso},
        )
        return int(result.rowcount or 0)


def get_support_chat_messages(hh_id: str, limit: int = 300) -> list[dict[str, object]]:
    normalized_limit = max(1, min(limit, 1000))
    with ENGINE.connect() as connection:
        rows = connection.execute(
            text(
                '''
                SELECT message_id, hh_id, message, sender_role, read_by_admin, read_by_user, created_at
                FROM support_messages
                WHERE hh_id = :hh_id
                ORDER BY created_at ASC
                LIMIT :limit
                '''
            ),
            {'hh_id': hh_id, 'limit': normalized_limit},
        ).mappings()
        return [dict(row) for row in rows]


def mark_support_messages_read_by_admin(hh_id: str) -> int:
    with ENGINE.begin() as connection:
        result = connection.execute(
            text(
                '''
                UPDATE support_messages
                SET read_by_admin = 1
                WHERE hh_id = :hh_id AND sender_role = 'user' AND read_by_admin = 0
                '''
            ),
            {'hh_id': hh_id},
        )
        return int(result.rowcount or 0)


def mark_support_messages_read_by_user(hh_id: str) -> int:
    with ENGINE.begin() as connection:
        result = connection.execute(
            text(
                '''
                UPDATE support_messages
                SET read_by_user = 1
                WHERE hh_id = :hh_id AND sender_role = 'admin' AND read_by_user = 0
                '''
            ),
            {'hh_id': hh_id},
        )
        return int(result.rowcount or 0)


def get_user_access_token(hh_id: str) -> str | None:
    with ENGINE.connect() as connection:
        row = connection.execute(text('SELECT access_token FROM users WHERE hh_id = :hh_id'), {'hh_id': hh_id}).first()
    if row is None:
        return None
    token = row[0]
    return token if isinstance(token, str) and token else None


def get_user_selected_interface(hh_id: str) -> str | None:
    with ENGINE.connect() as connection:
        row = connection.execute(text('SELECT selected_interface FROM users WHERE hh_id = :hh_id'), {'hh_id': hh_id}).first()
    if row is None:
        return None
    value = row[0]
    return value if isinstance(value, str) and value else None


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


def get_user_trial_3d_granted(hh_id: str) -> bool | None:
    with ENGINE.connect() as connection:
        row = connection.execute(
            text('SELECT trial_3d_granted FROM users WHERE hh_id = :hh_id'),
            {'hh_id': hh_id},
        ).first()

    if row is None:
        return None

    return bool(row[0])


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
    provider_status: str | None = None,
    product_type: str = 'subscription',
    theme_code: str | None = None,
) -> None:
    with ENGINE.begin() as connection:
        connection.execute(
            text(
                '''
                INSERT INTO billing_payments (
                    payment_id, hh_id, plan_code, amount, currency, status, provider_status, product_type, theme_code, created_at
                )
                VALUES (
                    :payment_id, :hh_id, :plan_code, :amount, :currency, :status, :provider_status, :product_type, :theme_code, :created_at
                )
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
                'provider_status': provider_status,
                'product_type': product_type,
                'theme_code': theme_code,
                'created_at': datetime.now(timezone.utc).isoformat(),
            },
        )


def get_payment(payment_id: str) -> dict[str, str] | None:
    with ENGINE.connect() as connection:
        row = connection.execute(
            text(
                '''
                SELECT
                    payment_id, hh_id, plan_code, amount, currency, status, provider_status, failure_reason,
                    product_type, theme_code, created_at, processed_at
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
        'provider_status': str(row[6]) if row[6] is not None else '',
        'failure_reason': str(row[7]) if row[7] is not None else '',
        'product_type': str(row[8]) if row[8] is not None else 'subscription',
        'theme_code': str(row[9]) if row[9] is not None else '',
        'created_at': str(row[10]) if row[10] is not None else '',
        'processed_at': str(row[11]) if row[11] is not None else '',
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


def mark_payment_failed(payment_id: str, *, reason: str | None, provider_status: str | None) -> bool:
    with ENGINE.begin() as connection:
        result = connection.execute(
            text(
                '''
                UPDATE billing_payments
                SET status = 'failed',
                    failure_reason = :failure_reason,
                    provider_status = :provider_status,
                    processed_at = :processed_at
                WHERE payment_id = :payment_id
                '''
            ),
            {
                'payment_id': payment_id,
                'failure_reason': reason,
                'provider_status': provider_status,
                'processed_at': datetime.now(timezone.utc).isoformat(),
            },
        )
        return result.rowcount > 0


def get_billing_operations(hh_id: str) -> list[dict[str, str]]:
    with ENGINE.connect() as connection:
        rows = connection.execute(
            text(
                '''
                SELECT payment_id, plan_code, amount, currency, status, provider_status, failure_reason, product_type, theme_code, created_at, processed_at
                FROM billing_payments
                WHERE hh_id = :hh_id
                ORDER BY created_at DESC
                '''
            ),
            {'hh_id': hh_id},
        ).mappings()
        return [dict(row) for row in rows]


def get_user_unlocked_themes(hh_id: str) -> set[str]:
    with ENGINE.connect() as connection:
        row = connection.execute(text('SELECT unlocked_themes FROM users WHERE hh_id = :hh_id'), {'hh_id': hh_id}).first()
    if row is None or not isinstance(row[0], str) or not row[0]:
        return set()
    return {item.strip() for item in row[0].split(',') if item.strip()}


def unlock_theme_for_user(hh_id: str, theme_code: str) -> bool:
    themes = get_user_unlocked_themes(hh_id)
    themes.add(theme_code)
    themes_raw = ','.join(sorted(themes))
    with ENGINE.begin() as connection:
        result = connection.execute(
            text('UPDATE users SET unlocked_themes = :themes WHERE hh_id = :hh_id'),
            {'themes': themes_raw, 'hh_id': hh_id},
        )
        return result.rowcount > 0


def update_user_selected_interface(hh_id: str, selected_interface: str) -> bool:
    with ENGINE.begin() as connection:
        result = connection.execute(
            text('UPDATE users SET selected_interface = :selected_interface WHERE hh_id = :hh_id'),
            {'selected_interface': selected_interface, 'hh_id': hh_id},
        )
        return result.rowcount > 0


def get_users_for_recurring(now_iso: str, pending_cutoff_iso: str) -> list[dict[str, str]]:
    with ENGINE.connect() as connection:
        rows = connection.execute(
            text(
                '''
                SELECT hh_id, plan_code, billing_amount, billing_currency, payment_method_id, current_period_end
                FROM users
                WHERE auto_renew_enabled = 1
                  AND payment_method_id IS NOT NULL
                  AND (
                      (current_period_end IS NOT NULL AND current_period_end <= :now_iso)
                      OR billing_status IN ('inactive', 'past_due', 'canceled')
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM billing_payments bp
                      WHERE bp.hh_id = users.hh_id
                        AND bp.product_type = 'subscription'
                        AND bp.status = 'pending'
                        AND bp.created_at >= :pending_cutoff_iso
                  )
                '''
            ),
            {'now_iso': now_iso, 'pending_cutoff_iso': pending_cutoff_iso},
        ).mappings()
        return [dict(row) for row in rows]


def update_user_subscription(
    *,
    hh_id: str,
    subscription_status: str | None,
    subscription_expires_at: str | None,
    trial_3d_granted: bool | None = None,
) -> bool:
    set_parts = ['subscription_status = :subscription_status', 'subscription_expires_at = :subscription_expires_at']
    params: dict[str, object] = {
        'hh_id': hh_id,
        'subscription_status': subscription_status,
        'subscription_expires_at': subscription_expires_at,
    }
    if trial_3d_granted is not None:
        set_parts.append('trial_3d_granted = :trial_3d_granted')
        params['trial_3d_granted'] = 1 if trial_3d_granted else 0

    with ENGINE.begin() as connection:
        result = connection.execute(
            text(f"UPDATE users SET {', '.join(set_parts)} WHERE hh_id = :hh_id"),
            params,
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
