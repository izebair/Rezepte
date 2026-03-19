from pathlib import Path


def test_desktop_entrypoint_exists():
    assert Path("app.pyw").exists()
