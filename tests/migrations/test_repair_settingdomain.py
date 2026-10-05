"""Verify the repair emits committed, repeatable DDL for the model's domains."""

from io import StringIO
from pathlib import Path

from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.models.domain_settings import SettingDomain


def test_repair_covers_persisted_domains_and_can_be_repeated():
    root = Path(__file__).resolve().parents[2]
    config = Config()
    config.set_main_option("script_location", str(root / "alembic"))
    script = ScriptDirectory.from_config(config)
    revision = script.get_revision("20261005_settingdomain_repair")
    assert revision is not None
    migration = revision.module
    assert migration.down_revision == "20260616_add_collaboration"
    assert set(migration.SETTING_DOMAINS) == {domain.name for domain in SettingDomain}

    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    with Operations.context(context), context.begin_transaction():
        migration.upgrade()
        migration.upgrade()
    ddl = output.getvalue()
    for domain in SettingDomain:
        assert (
            ddl.count(
                f"ALTER TYPE settingdomain ADD VALUE IF NOT EXISTS '{domain.name}'"
            )
            == 2
        )
    assert ddl.index("COMMIT;") < ddl.index("ALTER TYPE")
    assert "DROP" not in ddl and "DELETE" not in ddl
