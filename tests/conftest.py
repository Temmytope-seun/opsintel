import shutil
from pathlib import Path

import pytest

from opsintel import config


@pytest.fixture(scope="session", autouse=True)
def isolated_db(tmp_path_factory):
    """Run every test against a private copy of the operational store."""
    if not (config.RAW_DIR / "itsm_incidents.csv").exists():
        from opsintel.datagen import generate

        generate.main()
    tmp = tmp_path_factory.mktemp("db") / "opsintel.db"
    if config.DB_PATH.exists():
        shutil.copy(config.DB_PATH, tmp)
        config.DB_PATH = tmp
    else:
        config.DB_PATH = tmp
        from opsintel.etl.pipeline import run_pipeline

        run_pipeline(tmp)
    yield tmp


@pytest.fixture
def con():
    from opsintel import db

    c = db.connect()
    yield c
    c.close()


@pytest.fixture
def users(con):
    from opsintel.governance.rbac import get_user

    return {u: get_user(con, u) for u in ("exec.demo", "opsmgr.demo", "opsmgr2.demo", "analyst.demo", "desk.demo", "audit.demo")}
