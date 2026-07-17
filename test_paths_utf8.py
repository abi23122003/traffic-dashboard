from pathlib import Path
from backend.app import paths


def test_paths_constants():
    assert isinstance(paths.APP_DIR, Path)
    assert isinstance(paths.ROOT_DIR, Path)
    assert (paths.ROOT_DIR / 'frontend').exists()
    assert paths.ENV_FILE == paths.ROOT_DIR / ".env"
