from __future__ import annotations

import os
import asyncio
from typing import List, Optional

from fastapi import HTTPException, status
from bring_api import Bring, BringAuthException, BringErrorResponse


async def _get_bring() -> Bring:
    email = os.getenv("BRING_EMAIL")
    password = os.getenv("BRING_PASSWORD")
    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Umgebungsvariablen BRING_EMAIL und BRING_PASSWORD müssen gesetzt sein.",
        )
    bring = Bring(email, password)
    try:
        await bring.login()
    except BringAuthException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Login fehlgeschlagen: {exc.message}",
        ) from exc
    return bring


async def add_items_to_shopping_list(
    items: List[str],
    exclude: Optional[List[str]] = None,
) -> dict:
    """
    Fügt Artikel einer Bring!-Einkaufsliste hinzu.

    - `items`: Liste von Text‑Snippets (z. B. "200 g Mehl").
    - `exclude`: optionale Liste von Teilstrings. Artikel, die eines dieser
      Substrings enthalten, werden nicht hinzugefügt.
    Gibt ein Dict mit Status und der Liste der tatsächlich hinzugefügten
    Artikel zurück.
    """
    bring = await _get_bring()

    # Alle verfügbaren Listen laden
    lists = await bring.load_lists("lists")
    if not lists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Keine Bring‑Einkaufslisten gefunden.",
        )
    # Nimm die erste Liste (könnte auch nach Name ausgewählt werden)
    first_list = lists[0]
    list_uuid = first_list["listUuid"]

    # Filtereexclude
    filtered: List[str] = []
    for item in items:
        if exclude:
            if any(sub in item for sub in exclude):
                continue  # artikel ausschalten
        filtered.append(item)

    if not filtered:
        return {"status": "no_items_added", "added": [], "list_uuid": list_uuid}

    # Artikel hinzufügen – die API erwartet BringeItemOperation ADD
    # Wir nutzen batch_update_list für mehrere Einträge auf einmal.
    from bring_api import BringItemOperation

    # Bereite die Items im Format der API vor:
    # jedes Item: { "itemId": "...", "spec": "..." } – aber für einfache Texte
    # können wir den Text als 'name' übergeben; die Doku sagt save_item nimmt
    # (list_uuid, name, spec). Wir nutzen batch_update_list mit Operation ADD.
    items_for_api = [
        {"name": txt, "spec": ""} for txt in filtered
    ]
    # Die Doku zeigt: await bring.batch_update_list(list_uuid, items, BringItemOperation.ADD)
    # Aber batch_update_list erwartet eine Liste von Dicts mit 'itemId' und 'spec'.
    # Um es einfach zu halten, nutzen wir wiederholt await bring.save_item.
    added: List[str] = []
    for txt in filtered:
        try:
            await bring.save_item(list_uuid, txt, "")
            added.append(txt)
        except Exception as e:
            # Fehler weiterlefern, aber andere Artikel trotzdem versuchen
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Fehler beim Speichern von '{txt}': {e}",
            ) from e

    return {
        "status": "ok",
        "added": added,
        "list_uuid": list_uuid,
        "list_name": first_list.get("listName", "Unbenannte Liste"),
    }