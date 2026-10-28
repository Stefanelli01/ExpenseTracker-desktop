
import sqlite3
from contextlib import closing
from config import DEFAULT_BUDGET, DEFAULT_CURRENCY, DEFAULT_THEME

DB_NAME = "expense_tracker.db"


def get_connection():
    connection = sqlite3.connect(DB_NAME, timeout=10)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def init_db():
    with closing(get_connection()) as conn:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL CHECK (type IN ('Income', 'Expense')),
                    amount REAL NOT NULL CHECK (amount > 0),
                    category TEXT NOT NULL,
                    date TEXT NOT NULL,
                    note TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    monthly_budget REAL NOT NULL DEFAULT 0,
                    currency_symbol TEXT NOT NULL DEFAULT 'Rs.',
                    theme_mode TEXT NOT NULL DEFAULT 'dark'
                )
            """)

            columns = {
                column[1]
                for column in conn.execute("PRAGMA table_info(settings)")
            }

            if "theme_mode" not in columns:
                conn.execute(
                    "ALTER TABLE settings ADD COLUMN theme_mode TEXT DEFAULT 'dark'"
                )

            conn.execute("""
                INSERT OR IGNORE INTO settings (
                    id,
                    monthly_budget,
                    currency_symbol,
                    theme_mode
                )
                VALUES (?, ?, ?, ?)
            """, (1, DEFAULT_BUDGET, DEFAULT_CURRENCY, DEFAULT_THEME))

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_date
                ON transactions(date)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_type
                ON transactions(type)
            """)


def add_transaction(txn_type, amount, category, date, note):
    if txn_type not in ("Income", "Expense"):
        raise ValueError("Invalid transaction type.")

    amount = float(amount)

    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")

    if not category or not category.strip():
        raise ValueError("Category cannot be empty.")

    if not date or not date.strip():
        raise ValueError("Date cannot be empty.")

    if note is not None and len(note) > 500:
        raise ValueError("Note cannot exceed 500 characters.")

    with closing(get_connection()) as conn:
        with conn:
            cursor = conn.execute("""
                INSERT INTO transactions (
                    type,
                    amount,
                    category,
                    date,
                    note
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                txn_type,
                amount,
                category.strip(),
                date.strip(),
                note.strip() if note else None
            ))

            return cursor.lastrowid


def get_all_transactions():
    with closing(get_connection()) as conn:
        return conn.execute("""
            SELECT id, type, amount, category, date, note
            FROM transactions
            ORDER BY id DESC
        """).fetchall()


def delete_transaction(transaction_id):
    with closing(get_connection()) as conn:
        with conn:
            cursor = conn.execute(
                "DELETE FROM transactions WHERE id = ?",
                (transaction_id,)
            )
            return cursor.rowcount > 0


def get_summary():
    with closing(get_connection()) as conn:
        row = conn.execute("""
            SELECT
                COALESCE(SUM(CASE
                    WHEN type = 'Income' THEN amount
                    ELSE 0
                END), 0),
                COALESCE(SUM(CASE
                    WHEN type = 'Expense' THEN amount
                    ELSE 0
                END), 0),
                COALESCE(SUM(CASE
                    WHEN type = 'Expense'
                    AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
                    THEN amount
                    ELSE 0
                END), 0)
            FROM transactions
        """).fetchone()

    total_income, total_expense, this_month_expense = row

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": total_income - total_expense,
        "this_month_expense": this_month_expense
    }


def get_recent_transactions(limit=5):
    limit = max(1, int(limit))

    with closing(get_connection()) as conn:
        return conn.execute("""
            SELECT id, type, amount, category, date, note
            FROM transactions
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()


def get_settings():
    with closing(get_connection()) as conn:
        row = conn.execute("""
            SELECT monthly_budget, currency_symbol, theme_mode
            FROM settings
            WHERE id = 1
        """).fetchone()

    if row is None:
        return {
            "monthly_budget": DEFAULT_BUDGET,
            "currency_symbol": DEFAULT_CURRENCY,
            "theme_mode": DEFAULT_THEME
        }

    return {
        "monthly_budget": row[0],
        "currency_symbol": row[1],
        "theme_mode": row[2]
    }


def save_settings(monthly_budget, currency_symbol, theme_mode):
    monthly_budget = float(monthly_budget)
    currency_symbol = currency_symbol.strip()

    if monthly_budget < 0:
        raise ValueError("Budget cannot be negative.")

    if not currency_symbol or len(currency_symbol) > 8:
        raise ValueError("Currency symbol must contain between 1 and 8 characters.")

    if theme_mode not in ("dark", "light", "system"):
        raise ValueError("Invalid theme mode.")

    with closing(get_connection()) as conn:
        with conn:
            conn.execute("""
                INSERT INTO settings (
                    id,
                    monthly_budget,
                    currency_symbol,
                    theme_mode
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    monthly_budget = excluded.monthly_budget,
                    currency_symbol = excluded.currency_symbol,
                    theme_mode = excluded.theme_mode
            """, (
                1,
                monthly_budget,
                currency_symbol,
                theme_mode
            ))
