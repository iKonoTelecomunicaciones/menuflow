from asyncpg import Connection
from mautrix.util.async_db import UpgradeTable

upgrade_table = UpgradeTable()


@upgrade_table.register(description="Initial revision")
async def upgrade_v1(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE room (
            id          SERIAL PRIMARY KEY,
            room_id     TEXT NOT NULL,
            variables   JSON,
            node_id     TEXT,
            state       TEXT
        )"""
    )
    await conn.execute(
        """CREATE TABLE "user" (
            id          SERIAL PRIMARY KEY,
            mxid        TEXT NOT NULL
        )"""
    )
    await conn.execute(
        """CREATE TABLE client (
            id           TEXT    PRIMARY KEY,
            homeserver   TEXT    NOT NULL,
            access_token TEXT    NOT NULL,
            device_id    TEXT    NOT NULL,

            next_batch TEXT NOT NULL,
            filter_id  TEXT NOT NULL,

            autojoin BOOLEAN NOT NULL
        )"""
    )

    await conn.execute("ALTER TABLE room ADD CONSTRAINT idx_unique_room_id UNIQUE (room_id)")


@upgrade_table.register(description="Add new table route")
async def upgrade_v2(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE route (
            id          SERIAL PRIMARY KEY,
            room        INT NOT NULL,
            client      TEXT NOT NULL,
            node_id     TEXT,
            state       TEXT,
            variables   JSON
        )"""
    )
    await conn.execute("CREATE INDEX ind_route_room_client ON route (room, client)")
    await conn.execute(
        "ALTER TABLE route ADD CONSTRAINT FK_room_route FOREIGN KEY (room) references room (id)"
    )
    await conn.execute(
        "ALTER TABLE route ADD CONSTRAINT FK_client_route FOREIGN KEY (client) references client (id)"
    )

    # Drop old columns from room table
    await conn.execute("ALTER TABLE room DROP COLUMN node_id")
    await conn.execute("ALTER TABLE room DROP COLUMN state")


@upgrade_table.register(description="Add stack field to route table")
async def upgrade_v3(conn: Connection) -> None:
    # Add stack column to route table
    await conn.execute("ALTER TABLE route ADD COLUMN stack JSONB NOT NULL DEFAULT '{}'::jsonb")


@upgrade_table.register(description="Add flow table and flow column to client table")
async def upgrade_v4(conn: Connection) -> None:
    # Add flow column to client table
    await conn.execute("ALTER TABLE client ADD COLUMN flow INT")

    # Create flow table
    await conn.execute(
        """CREATE TABLE flow (
            id          SERIAL PRIMARY KEY,
            flow        JSONB DEFAULT '{}'::jsonb
        )"""
    )

    # Add foreign key to client table
    await conn.execute(
        "ALTER TABLE client ADD CONSTRAINT FK_flow_client FOREIGN KEY (flow) references flow (id)"
    )


@upgrade_table.register(description="Add enable column to client table")
async def upgrade_v5(conn: Connection) -> None:
    await conn.execute("ALTER TABLE client ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT TRUE")


@upgrade_table.register(description="Add new table flow_backup")
async def upgrade_v6(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE flow_backup (
            id          SERIAL PRIMARY KEY,
            flow_id     INT NOT NULL,
            flow        JSONB DEFAULT '{}'::jsonb NOT NULL,
            created_at  TIMESTAMP  WITH TIME ZONE DEFAULT now()
        )"""
    )


@upgrade_table.register(description="Add new table webhook")
async def upgrade_v7(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE webhook (
            id          SERIAL PRIMARY KEY,
            room_id     TEXT NOT NULL,
            client      TEXT NOT NULL,
            filter      TEXT NOT NULL,
            subscription_time   BIGINT NOT NULL
        )"""
    )
    await conn.execute("CREATE INDEX ind_webhook_room ON webhook (room_id)")
    await conn.execute("CREATE INDEX ind_webhook_room_client ON webhook (room_id, client)")
    await conn.execute(
        "ALTER TABLE webhook ADD CONSTRAINT FK_room_webhook FOREIGN KEY (room_id) references room (room_id)"
    )
    await conn.execute(
        "ALTER TABLE webhook ADD CONSTRAINT FK_client_webhook FOREIGN KEY (client) references client (id)"
    )


@upgrade_table.register(description="Add flow_vars column to flow table and add new table module")
async def upgrade_v8(conn: Connection) -> None:

    # Add flow_vars column to flow table
    await conn.execute("ALTER TABLE flow ADD COLUMN flow_vars JSONB DEFAULT '{}'::jsonb")

    # Create module table
    await conn.execute(
        """CREATE TABLE module (
           id          SERIAL PRIMARY KEY,
           flow_id     INT NOT NULL,
           name        TEXT NOT NULL,
           nodes       JSONB DEFAULT '[]'::jsonb,
           position    JSONB DEFAULT '{}'::jsonb
       )"""
    )

    # Add foreign key to module table
    await conn.execute(
        "ALTER TABLE module ADD CONSTRAINT fk_module_flow FOREIGN KEY (flow_id) REFERENCES flow(id)"
    )

    # Add unique constraint to module table
    await conn.execute(
        "ALTER TABLE module ADD CONSTRAINT idx_unique_module_name_flow_id UNIQUE (name, flow_id)"
    )

    # Create index on module table
    await conn.execute("CREATE INDEX idx_module_flow ON module (flow_id)")


@upgrade_table.register(description="Add webhook_queue table")
async def upgrade_v9(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE webhook_queue (
            id          SERIAL PRIMARY KEY,
            event       JSONB NOT NULL,
            ending_time BIGINT NOT NULL,
            creation_time BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)
        )"""
    )
    await conn.execute(
        "CREATE INDEX idx_webhook_queue_creation_time ON webhook_queue (creation_time)"
    )
    await conn.execute("CREATE INDEX idx_webhook_queue_id ON webhook_queue (id)")
    await conn.execute("CREATE INDEX idx_webhook_queue_event ON webhook_queue (event)")


@upgrade_table.register(description="Add node_vars column to route table")
async def upgrade_v10(conn: Connection) -> None:
    await conn.execute(
        "ALTER TABLE route ADD COLUMN IF NOT EXISTS node_vars JSONB DEFAULT '{}'::jsonb"
    )


@upgrade_table.register(description="Add tag table and modify flow and module tables structure")
async def upgrade_v11(conn: Connection) -> None:

    # Remove column tag_id from module table
    await conn.execute("ALTER TABLE module DROP COLUMN IF EXISTS tag_id")

    # Delete tag table if exists
    await conn.execute("DROP TABLE IF EXISTS tag")

    # Create tag table
    await conn.execute(
        """CREATE TABLE tag (
            id          SERIAL PRIMARY KEY,
            flow_id     INT NOT NULL,
            name        TEXT,
            create_date TIMESTAMP WITH TIME ZONE DEFAULT now(),
            author      TEXT,
            active      BOOLEAN NOT NULL DEFAULT false,
            flow_vars   JSONB DEFAULT '{}'::jsonb
        )"""
    )

    # Add foreign key constraint to flow table
    await conn.execute(
        "ALTER TABLE tag ADD CONSTRAINT fk_tag_flow FOREIGN KEY (flow_id) REFERENCES flow(id)"
    )

    # Add unique constraint for name per flow
    await conn.execute(
        "ALTER TABLE tag ADD CONSTRAINT idx_unique_tag_name_flow_id UNIQUE (name, flow_id)"
    )

    # Add create_date to flow table
    await conn.execute(
        "ALTER TABLE flow ADD COLUMN IF NOT EXISTS create_date TIMESTAMP WITH TIME ZONE DEFAULT now()"
    )

    # Add tag_id to module table
    await conn.execute("ALTER TABLE module ADD COLUMN tag_id INT")

    # Add foreign key constraint to tag table
    await conn.execute(
        "ALTER TABLE module ADD CONSTRAINT fk_module_tag FOREIGN KEY (tag_id) REFERENCES tag(id)"
    )

    # Drop the old unique constraint from module table (flow_id based)
    await conn.execute(
        "ALTER TABLE module DROP CONSTRAINT IF EXISTS idx_unique_module_name_flow_id"
    )

    # Drop the old unique constraint from module table (flow_id based)
    await conn.execute(
        "ALTER TABLE module DROP CONSTRAINT IF EXISTS idx_unique_module_name_flow_id"
    )

    # Migrate existing flow_vars data to tag table (create default tags for existing flows)
    await conn.execute(
        """INSERT INTO tag (flow_id, flow_vars, active, name)
           SELECT id, flow_vars, true, 'current'
           FROM flow
        """
    )

    # update existing modules to set tag_id to the active tag of the corresponding flow
    await conn.execute(
        """UPDATE module
            SET tag_id = t.id
            FROM tag AS t
            WHERE module.flow_id = t.flow_id
        """
    )

    # Set tag_id as NOT NULL
    await conn.execute("ALTER TABLE module ALTER COLUMN tag_id SET NOT NULL")

    # Add new unique constraint to module table for tag_id
    await conn.execute(
        "ALTER TABLE module ADD CONSTRAINT idx_unique_module_name_tag_id UNIQUE (name, tag_id)"
    )

    # Create indexes for better performance
    await conn.execute("CREATE INDEX idx_tag_flow_id ON tag (flow_id)")
    await conn.execute("CREATE INDEX idx_tag_create_date ON tag (create_date)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_flow_create_date ON flow (create_date)")
    await conn.execute("CREATE INDEX idx_module_tag_id ON module (tag_id)")


@upgrade_table.register(description="Add author_name column to tag table")
async def upgrade_v12(conn: Connection) -> None:
    await conn.execute("ALTER TABLE tag ADD COLUMN IF NOT EXISTS author_name TEXT")
