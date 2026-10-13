import os
import sqlite3
from pathlib import Path


def _connect(database_path=None):
    configured_path = database_path or os.environ.get("INVOICE_HISTORY_DB")
    path = Path(configured_path) if configured_path else Path(__file__).with_name(
        "invoice_history.sqlite3"
    )
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_number TEXT PRIMARY KEY,
            invoice_date TEXT NOT NULL,
            business_name TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            currency TEXT NOT NULL,
            total TEXT NOT NULL,
            csv_content TEXT NOT NULL,
            pdf_content BLOB NOT NULL,
            saved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()
    return connection


def save_invoice_record(
    invoice_number,
    invoice_date,
    business_name,
    customer_name,
    currency,
    total,
    csv_content,
    pdf_content,
    database_path=None,
):
    """Persist an invoice and the exact CSV/PDF files generated for it."""
    connection = _connect(database_path)
    try:
        connection.execute(
            """
            INSERT INTO invoices (
                invoice_number,
                invoice_date,
                business_name,
                customer_name,
                currency,
                total,
                csv_content,
                pdf_content
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(invoice_number) DO UPDATE SET
                invoice_date = excluded.invoice_date,
                business_name = excluded.business_name,
                customer_name = excluded.customer_name,
                currency = excluded.currency,
                total = excluded.total,
                csv_content = excluded.csv_content,
                pdf_content = excluded.pdf_content,
                saved_at = CURRENT_TIMESTAMP
            """,
            (
                invoice_number,
                invoice_date,
                business_name,
                customer_name,
                currency,
                total,
                csv_content,
                sqlite3.Binary(pdf_content),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def list_invoice_history(database_path=None):
    """Return saved invoice summaries, newest first."""
    connection = _connect(database_path)
    try:
        rows = connection.execute(
            """
            SELECT invoice_number, invoice_date, business_name, customer_name,
                   currency, total, saved_at
            FROM invoices
            ORDER BY saved_at DESC, invoice_number DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_invoice_record(invoice_number, database_path=None):
    """Return one saved invoice, including its download contents."""
    connection = _connect(database_path)
    try:
        row = connection.execute(
            "SELECT * FROM invoices WHERE invoice_number = ?",
            (invoice_number,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()