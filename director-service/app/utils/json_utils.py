import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def load_json(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: dict[str, Any] | list, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def pydantic_to_json(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
