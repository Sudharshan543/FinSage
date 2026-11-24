from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_cfignore_excludes_local_database_credentials():
    ignored_paths = {
        line.strip()
        for line in (PROJECT_ROOT / ".cfignore").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "db-credentials.json" in ignored_paths
