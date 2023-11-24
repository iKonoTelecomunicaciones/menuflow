import logging
import sqlite3
from sqlite3 import Connection, Cursor

from mautrix.util.logging import TraceLogger

latest_db_version = 0

log: TraceLogger = logging.getLogger("report.storage")


class EventStorage:
    _conn: Connection = None
    _db: Cursor = None

    @classmethod
    def init_sqlite_db(cls):
        if cls._conn and cls._db:
            return

        log.info("Performing initial database setup...")
        try:
            # Initialize a connection to the database
            cls._conn: Connection = sqlite3.connect("/data/events.db")
            cls._conn.row_factory = sqlite3.Row
            cls._db: Cursor = cls._conn.cursor()
        except sqlite3.OperationalError as e:
            log.error(f"Failed to connect to database: {e}")
            return

        cls.run_migrations()

        return cls

    @classmethod
    def run_migrations(cls):
        try:
            cls._db.execute(
                """
                    CREATE TABLE event (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event TEXT,
                        akn BOOLEAN,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
            )
        except sqlite3.OperationalError as e:
            log.info(f"Failed to create table events: {e}")

    @classmethod
    def insert_event(cls, event: str, akn: bool = False):
        cls._db.execute("INSERT INTO event (event, akn) VALUES (?, ?)", (event, akn))
        cls._conn.commit()

    @classmethod
    def update_event(cls, event_id: int, akn: bool):
        cls._db.execute("UPDATE event SET akn = ? WHERE id = ?", (akn, str(event_id)))
        cls._conn.commit()

    @classmethod
    def get_events(cls):
        cls._db.execute("SELECT * FROM event WHERE akn = ? ORDER BY id ASC", (False,))
        rows = cls._db.fetchall()
        return [cls.to_dict(row) for row in rows] if rows else []

    @classmethod
    def delete_event(cls, event_id: int):
        cls._db.execute("DELETE FROM event WHERE id = ?", (str(event_id),))
        cls._conn.commit()

    @classmethod
    def to_dict(cls, row):
        return dict(zip(row.keys(), row))


sqlite_db = EventStorage().init_sqlite_db()
