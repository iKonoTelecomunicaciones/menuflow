from asyncpg import Connection

from mautrix.util.async_db import UpgradeTable

upgrade_table = UpgradeTable()


@upgrade_table.register(description="Initial revision")
async def upgrade_v1(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE "user" (
        id          SERIAL PRIMARY KEY,
        user_id     TEXT,
        variables   JSON,
        context     TEXT,
        state       TEXT
        )"""
    )
