from __future__ import annotations

import os
import asyncio
from typing import List, Optional, Dict

from fastapi import HTTPException, status
from bring_api import Bring, BringAuthException, BringErrorResponse


async def _get_bring() -> Bring:
    email = os.getenv("BRING_EMAIL")
    password = os.getenv("BRING_PASSWORD")
    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Einkaufsliste nicht erreichbar (Bring-Zugang nicht konfiguriert).",
        )
    bring = Bring(email, password)
    try:
        await bring.login()
    except BringAuthException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Login fehlgeschlagen: {exc.message}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Bring-Dienst nicht erreichbar: {exc}",
        ) from exc
    return bring


def _normalize_item(text: str) -> str:
    # Grundlegende Normalisierung für Duplikat-Erkennung
    return text.strip().lower()


async def add_items_to_shopping_list(
    items: List[str],
    exclude: Optional[List[str]] = None,
) -> dict:
    """
    Fügt Artikel einer Bring!-Einkaufsliste hinzu.
    Unterstützt Teilfehler: jede Zutat wird einzeln versucht.
    """
    bring = await _get_bring()

    try:
        lists = await asyncio.wait_for(bring.load_lists("lists"), timeout=15.0)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Die Einkaufsliste ist gerade nicht erreichbar. Erneut versuchen?",
        ) from exc

    if not lists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Keine Bring-Einkaufslisten gefunden.",
        )

    first_list = lists[0]
    list_uuid = first_list["listUuid"]
    list_name = first_list.get("listName", "Unbenannte Liste")

    filtered: List[str] = []
    for item in items:
        if exclude:
            if any(sub in item for sub in exclude):
                continue
        filtered.append(item)

    if not filtered:
        return {"status": "no_items_added", "added": [], "failed": [], "list_uuid": list_uuid, "list_name": list_name}

    added: List[str] = []
    failed: List[str] = []
    duplicates_merged: List[str] = []

    # Versuche jede Zutat einzeln, damit Teilfehler nicht alles blockieren
    for txt in filtered:
        try:
            await asyncio.wait_for(bring.save_item(list_uuid, txt, ""), timeout=10.0)
            added.append(txt)
        except Exception as exc:
            # Wenn es einen Duplikat-Fehler gibt, behandeln wir als Erfolg
            msg = str(exc).lower()
            if "duplicate" in msg or "already" in msg or "exists" in msg:
                duplicates_merged.append(txt)
            else:
                failed.append(txt)

    status_str = "ok" if not failed else ("partial" if added else "error")
    return {
        "status": status_str,
        "added": added,
        "failed": failed,
        "duplicates_merged": duplicates_merged,
        "list_uuid": list_uuid,
        "list_name": list_name,
    }
