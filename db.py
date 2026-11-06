"""SQLite helpers (SQL layer)."""
import os
import sqlite3
from datetime import datetime
from flask import g, current_app

ROOT = os.path.dirname(os.path.abspath(__file__))


def now():
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_schema(conn):
    with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
