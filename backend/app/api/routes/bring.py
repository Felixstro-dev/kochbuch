from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, status

from app.services.bring_service import add_items_to_shopping_list

router = APIRouter(prefix="/shopping-list", tags=["shopping-list"])


@router.post("/add", response_model=None)
async def add_to_shopping_list(
    payload: dict = Body(
        ...,
        description={
            "items": "Liste von Zutaten‑Texten, z. B. ['200 g Mehl', '1 Ei'].",
            "exclude": "optionale Liste von Teilstrings, die in Artikeln gesucht und weggelassen werden.",
        },
    ),
):
    """Fügt Zutaten in die Bring!-Einkaufsliste ein."""
    items: List[str] = payload.get("items", [])
    exclude: List[str] = payload.get("exclude", [])

    if not isinstance(items, list) or not all(isinstance(i, str) for i in items):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parameter 'items' muss eine Liste von Strings sein.",
        )

    try:
        result = await add_items_to_shopping_list(items, exclude)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        # Keine technischen Details ins UI – zentraler Fallback
        detail = str(exc)
        if len(detail) > 120:
            detail = "Unerwarteter Fehler beim Speichern. Bitte später erneut versuchen."
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        ) from exc