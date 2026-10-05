"""Exercise the real container entrypoint with stub commands, without Docker or a DB."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def run_entrypoint(tmp_path):
    shell = shutil.which("sh")
    if not shell and os.name == "nt":
        candidate = Path("C:/Program Files/Git/bin/sh.exe")
        if candidate.is_file():
            shell = str(candidate)
    if not shell:
        pytest.skip("A POSIX shell is required for the container entrypoint test")
    root = Path(__file__).resolve().parents[1]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    commands = {
        "python": '#!/bin/sh\nprintf "%s\\n" "$*" >> "$SEED_TEST_LOG"\ncase "$*" in\n*seed_sherpackage_digital_marketer_on_start.py*) exit "${SEED_TEST_JOB_EXIT:-0}" ;;\n*) exit 0 ;;\nesac\n',
        "gunicorn": '#!/bin/sh\nprintf "service-started\\n" >> "$SEED_TEST_LOG"\n',
        "celery": '#!/bin/sh\nprintf "service-started\\n" >> "$SEED_TEST_LOG"\n',
    }
    for name, body in commands.items():
        path = bin_dir / name
        path.write_text(body, encoding="utf-8", newline="\n")
        path.chmod(0o755)
    log = tmp_path / "commands.log"

    def run(command="gunicorn", **overrides):
        env = dict(os.environ)
        env.update(
            PATH=str(bin_dir) + os.pathsep + env.get("PATH", ""),
            APP_ROOT=root.as_posix(),
            SEED_TEST_LOG=log.as_posix(),
            SEED_TEST_JOB_EXIT="0",
            SEED_ADMIN_ON_START="true",
            SEED_DEMO_ON_START="true",
            SEED_SHERPACKAGE_ON_START="true",
            SEED_SHERPACKAGE_DIGITAL_MARKETER_RETRIES="3",
            SEED_SHERPACKAGE_DIGITAL_MARKETER_RETRY_DELAY_SECONDS="0",
        )
        env.pop("SEED_SHERPACKAGE_DIGITAL_MARKETER_ON_START", None)
        env.update(overrides)
        result = subprocess.run(  # noqa: S603 - repository script with test-owned command stubs
            [shell, (root / "scripts/entrypoint-monitoring.sh").as_posix(), command],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout, log.read_text(encoding="utf-8").splitlines()

    return run


def test_job_seed_runs_after_migrations_and_org_before_web(run_entrypoint):
    _, commands = run_entrypoint()
    job_index = next(
        i
        for i, cmd in enumerate(commands)
        if cmd.endswith("seed_sherpackage_digital_marketer_on_start.py")
    )
    org_index = next(
        i for i, cmd in enumerate(commands) if cmd.endswith("seed_sherpackage.py")
    )
    assert (
        commands.index("-m alembic upgrade heads")
        < org_index
        < job_index
        < commands.index("service-started")
    )


def test_failed_optional_job_seed_retries_without_blocking_web(run_entrypoint):
    output, commands = run_entrypoint(SEED_TEST_JOB_EXIT="1")
    assert (
        sum(
            cmd.endswith("seed_sherpackage_digital_marketer_on_start.py")
            for cmd in commands
        )
        == 3
    )
    assert "WARNING:" in output and "next restart" in output
    assert commands[-1] == "service-started"


def test_job_seed_can_be_disabled(run_entrypoint):
    output, commands = run_entrypoint(
        SEED_SHERPACKAGE_DIGITAL_MARKETER_ON_START="false"
    )
    assert "startup seed disabled" in output
    assert not any(
        "seed_sherpackage_digital_marketer_on_start.py" in cmd for cmd in commands
    )


def test_worker_does_not_run_job_seed(run_entrypoint):
    _, commands = run_entrypoint("celery")
    assert not any(
        "seed_sherpackage_digital_marketer_on_start.py" in cmd for cmd in commands
    )
    assert "-m alembic upgrade heads" not in commands
