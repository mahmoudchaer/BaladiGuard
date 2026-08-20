"""Download the pinned Community Forensics DeepfakeDet ViT ONNX weights.

Weights are not stored in git. Docker and local workers both use this checksum.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from urllib.request import urlretrieve

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.content_safety.model_assets import (  # noqa: E402
    AUTHENTICITY_MODEL_FILENAME,
    AUTHENTICITY_MODEL_SHA256,
    AUTHENTICITY_MODEL_URL,
)


def main() -> int:
    dest = BACKEND_ROOT / "models" / AUTHENTICITY_MODEL_FILENAME
    dest.parent.mkdir(parents=True, exist_ok=True)
    if (
        dest.is_file()
        and hashlib.sha256(dest.read_bytes()).hexdigest() == AUTHENTICITY_MODEL_SHA256
    ):
        print(f"Authenticity model already present: {dest}")
        return 0
    print(f"Downloading {AUTHENTICITY_MODEL_URL}")
    urlretrieve(AUTHENTICITY_MODEL_URL, dest)
    actual = hashlib.sha256(dest.read_bytes()).hexdigest()
    if actual != AUTHENTICITY_MODEL_SHA256:
        dest.unlink(missing_ok=True)
        print(f"Checksum mismatch: {actual}")
        return 1
    print(f"Wrote {dest} ({dest.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
