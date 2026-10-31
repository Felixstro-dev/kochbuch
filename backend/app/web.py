from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI, frontend_dir: Path) -> None:
    assets = frontend_dir / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    index = frontend_dir / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        candidate = (frontend_dir / full_path).resolve()
        if (
            full_path
            and candidate.is_file()
            and frontend_dir.resolve() in candidate.parents
        ):
            return FileResponse(candidate)
        return FileResponse(index)
