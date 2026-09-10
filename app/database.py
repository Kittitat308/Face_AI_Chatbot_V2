from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def init_database():
    from app import models  # noqa: F401

    Base.metadata.create_all(
        bind=engine,
    )

    # create_all does not add columns to an existing PostgreSQL table.
    migrations = (
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP NULL",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS require_password_after_face BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS camera_enabled BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS microphone_enabled BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS speaker_enabled BOOLEAN NOT NULL DEFAULT TRUE",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username_exact ON users (username)",
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_users_username_no_whitespace'
            ) THEN
                ALTER TABLE users
                ADD CONSTRAINT ck_users_username_no_whitespace
                CHECK (username !~ '[[:space:]]');
            END IF;
        END $$
        """,
        "UPDATE users SET display_name = username WHERE display_name IS DISTINCT FROM username",
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_users_display_name_matches_username'
            ) THEN
                ALTER TABLE users
                ADD CONSTRAINT ck_users_display_name_matches_username
                CHECK (display_name = username);
            END IF;
        END $$
        """,
    )
    with engine.begin() as connection:
        for statement in migrations:
            connection.execute(text(statement))
