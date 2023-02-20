from typing import Iterator
from pathlib import Path
from contextlib import contextmanager
import tempfile
import shutil


@contextmanager
def make_tempdir() -> Iterator[Path]:
    """Run a block in a temp directory and remove it afterwards."""
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(str(d))
