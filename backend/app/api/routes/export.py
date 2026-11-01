from __future__ import annotations

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/export", tags=["export"])

@router.get("/recipes")
async def export_recipes(request: Request) -> JSONResponse:
    try:
        from app.services.recipes import RecipeService
        svc: RecipeService = request.app.state.recipe_service
        with request.app.state.session_factory() as db:
            # Einfacher Export aller Rezept-Schlüssel und Titel
            # Für volles Db-Dump: DATA_DIR / kochbuch.db kopieren
            items = []
            # Wir nutzen einen einfachen DB-Zugriff
            from sqlalchemy import text
            result = db.execute(text("SELECT cache_key, title, source FROM recipes LIMIT 500"))
            for row in result.mappings().all():
                items.append({"key": row["cache_key"], "title": row["title"], "source": row["source"]})
        return JSONResponse(content={"count": len(items), "items": items})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export fehlgeschlagen: {exc}") from exc

@router.get("/backup")
async def export_backup(request: Request) -> JSONResponse:
    data_dir: Path = request.app.state.settings.data_path
    db_path = data_dir / "kochbuch.db"
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden.")
    # Wir liefern den Pfad und einen Hinweis auf manuelles Kopieren
    return JSONResponse(content={
        "db_path": str(db_path),
        "size_bytes": db_path.stat().st_size,
        "instruction": "Kopiere diese Datei als Backup (z.B. in ein Volume oder externen Storage)."
    })
