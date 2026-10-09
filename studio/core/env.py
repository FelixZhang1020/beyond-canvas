from __future__ import annotations

import os
import re
from pathlib import Path

_LINE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*[=:]\s*(.*)$")


def load_dotenv(path: Path | str = Path(".env")) -> None:
    """Copy KEY=value lines into the environment without overwriting it.

    Values already in the environment win, so a shell export beats the file.
    A missing file is not an error: on the Spark the studio reads real
    environment variables and has no .env at all.
    """
    file = Path(path)
    if not file.is_file():
        return
    for line in file.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _LINE.match(stripped)
        if not match:
            continue
        name, raw = match.group(1), match.group(2).strip()
        os.environ.setdefault(name, raw.strip('"').strip("'"))
