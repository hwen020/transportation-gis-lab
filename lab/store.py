import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .data import META, fixtures


def samples(path: Path):
    with closing(sqlite3.connect(path)) as database, database:
        database.execute("BEGIN IMMEDIATE")
        if database.execute("PRAGMA user_version").fetchone()[0] < 1:
            database.execute("""CREATE TABLE IF NOT EXISTS sample (
                dataset_version TEXT NOT NULL, fixture TEXT NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY (dataset_version, fixture)
            )""")
            database.execute("PRAGMA user_version = 1")
        for name in ("clean", "dirty"):
            database.execute("INSERT OR IGNORE INTO sample VALUES (?, ?, ?)",
                             (META["dataset_version"], name, json.dumps(fixtures(name == "dirty"))))
        return {name: json.loads(payload) for name, payload in database.execute(
            "SELECT fixture, payload FROM sample WHERE dataset_version = ?", (META["dataset_version"],))}
