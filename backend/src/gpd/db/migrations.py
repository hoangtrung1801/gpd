from pathlib import Path
from alembic import command
from alembic.config import Config
from gpd.db.engine import Database


def run_migrations(database: Database, config_path: Path | None = None) -> None:
    """Run Alembic migrations up to head using the database connection."""
    if config_path is None:
        here = Path(__file__).resolve()
        potential = [
            here.parents[3] / "backend" / "alembic.ini",
            here.parents[2] / "alembic.ini",
            Path("backend/alembic.ini"),
            Path("alembic.ini"),
        ]
        for p in potential:
            if p.exists():
                config_path = p
                break

    resolved_path = str(config_path) if config_path and config_path.exists() else "backend/alembic.ini"
    alembic_cfg = Config(resolved_path)

    # Set script_location explicitly to absolute path if found
    if config_path and config_path.exists():
        migrations_dir = config_path.parent / "migrations"
        if migrations_dir.exists():
            alembic_cfg.set_main_option("script_location", str(migrations_dir))

    with database.connect() as connection:
        alembic_cfg.attributes["connection"] = connection
        command.upgrade(alembic_cfg, "head")
        connection.commit()
