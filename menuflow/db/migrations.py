from asyncpg import Connection

from mautrix.util.async_db import UpgradeTable

upgrade_table = UpgradeTable()


@upgrade_table.register(description="Initial revision")
async def upgrade_v1(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE "user" (
        id          SERIAL PRIMARY KEY,
        user_id     TEXT,
        context     TEXT,
        state       TEXT
        )"""
    )
    await conn.execute(
        """CREATE TABLE variable (
        pk          SERIAL PRIMARY KEY,
        variable_id TEXT,
        value       TEXT,
        fk_user     INT NOT NULL,
        UNIQUE (variable_id, fk_user)
        )"""
    )
    await conn.execute(
        'ALTER TABLE variable ADD CONSTRAINT FK_user FOREIGN KEY (fk_user) references "user" (id)'
    )
