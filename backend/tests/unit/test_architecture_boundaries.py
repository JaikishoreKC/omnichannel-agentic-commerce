from __future__ import annotations

from pathlib import Path


def test_api_routes_and_middleware_do_not_import_container_directly() -> None:
    app_root = Path(__file__).resolve().parents[2] / "app"
    targets = [app_root / "api" / "routes", app_root / "middleware"]

    violations: list[str] = []
    for target in targets:
        for path in target.rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            if "from app.container import container" in content:
                violations.append(str(path.relative_to(app_root.parent)).replace("\\", "/"))

    assert violations == [], f"Direct container imports found: {violations}"
