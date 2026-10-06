"""Atomic derived-pointer replacement with bounded Windows sharing retries."""

import os
from pathlib import Path
import time


def replace_pointer(source: str | Path, target: str | Path) -> None:
    """Keep the old pointer if replacement fails; never delete it before replacing."""
    for attempt in range(10):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(min(.05 * 2**attempt, .5))
