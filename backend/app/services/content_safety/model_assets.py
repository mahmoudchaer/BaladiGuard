"""Pinned Community Forensics DeepfakeDet ViT ONNX weights (MIT)."""

from __future__ import annotations

from pathlib import Path

# backend/app/services/content_safety/model_assets.py -> backend/
_BACKEND_DIR = Path(__file__).resolve().parents[3]

AUTHENTICITY_MODEL_FILENAME = "community-forensics-deepfakedet-vit.onnx"
AUTHENTICITY_MODEL_REVISION = "ac6ee457bea904a373065754107451793b56db00"
AUTHENTICITY_MODEL_URL = (
    "https://huggingface.co/buildborderless/CommunityForensics-DeepfakeDet-ViT/"
    f"resolve/{AUTHENTICITY_MODEL_REVISION}/onnx/model.onnx"
)
AUTHENTICITY_MODEL_SHA256 = "a42c7d740fbb345ba9a26d469b22f301d73089ce3c6da993877ed2b6965a8ba1"
AUTHENTICITY_MODEL_NAME = "community-forensics-deepfakedet-vit"


def authenticity_model_candidates() -> tuple[Path, ...]:
    return (
        Path("/opt/models") / AUTHENTICITY_MODEL_FILENAME,
        _BACKEND_DIR / "models" / AUTHENTICITY_MODEL_FILENAME,
    )


def resolve_authenticity_model_path(raw: str | None) -> str | None:
    """Return a readable ONNX path, or None when the pinned weights are absent.

    Empty / named default searches the Docker and local download locations.
    An explicit ``.onnx`` path that does not exist is not silently replaced.
    """
    value = (raw or "").strip()
    if value:
        explicit = Path(value)
        if explicit.is_file():
            return str(explicit.resolve())
        if value.lower().endswith(".onnx"):
            return None
    for candidate in authenticity_model_candidates():
        if candidate.is_file():
            return str(candidate.resolve())
    return None
