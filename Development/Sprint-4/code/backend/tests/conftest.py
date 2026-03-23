from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
from _pytest import pathlib as pytest_pathlib
from _pytest import tmpdir as pytest_tmpdir

os.environ["DATABASE_URL"] = "sqlite:///./test_suite.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"

_original_cleanup_dead_symlinks = pytest_pathlib.cleanup_dead_symlinks
_original_make_numbered_dir = pytest_pathlib.make_numbered_dir
_TEST_ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "test_artifacts" / "tmp"


def _safe_cleanup_dead_symlinks(root: Path) -> None:
    try:
        _original_cleanup_dead_symlinks(root)
    except PermissionError:
        # Windows file locking can leave pytest basetemp roots unreadable at teardown.
        return


def _safe_make_numbered_dir(root: Path, prefix: str, mode: int = 0o700) -> Path:
    return _original_make_numbered_dir(root, prefix, 0o777)


def _safe_mktemp(self: pytest_tmpdir.TempPathFactory, basename: str, numbered: bool = True) -> Path:
    basename = self._ensure_relative_to_basetemp(basename)
    if not numbered:
        path = self.getbasetemp().joinpath(basename)
        path.mkdir(mode=0o777)
    else:
        path = _safe_make_numbered_dir(root=self.getbasetemp(), prefix=basename, mode=0o777)
        self._trace("mktemp", path)
    return path


pytest_pathlib.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
pytest_tmpdir.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
pytest_pathlib.make_numbered_dir = _safe_make_numbered_dir
pytest_tmpdir.make_numbered_dir = _safe_make_numbered_dir
pytest_tmpdir.TempPathFactory.mktemp = _safe_mktemp


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config) -> None:
    _TEST_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    basetemp = _TEST_ARTIFACTS_DIR / f"pytest-{uuid4().hex[:8]}"
    basetemp.mkdir()
    config.option.basetemp = str(basetemp)
    if hasattr(config, "_tmp_path_factory"):
        config._tmp_path_factory._basetemp = basetemp
