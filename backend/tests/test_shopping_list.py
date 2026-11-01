"""Tests für Einkaufsliste: Auswahl, Duplikate, Teilfehler, Fehlerfälle."""
import pytest
from unittest.mock import AsyncMock, patch
from app.services.bring_service import add_items_to_shopping_list

@pytest.mark.asyncio
async def test_partial_failure_keeps_others():
    with patch("app.services.bring_service._get_bring") as mock_get:
        bring = AsyncMock()
        bring.load_lists = AsyncMock(return_value=[{"listUuid": "l1", "listName": "Liste"}])
        # Erste Zutat schlägt fehl, zweite geht
        async def save_item(list_uuid, name, spec):
            if "Mehl" in name:
                raise Exception("timeout")
        bring.save_item = save_item
        mock_get.return_value = bring
        result = await add_items_to_shopping_list(["200 g Mehl", "1 Ei"])
        assert result["status"] == "partial"
        assert "200 g Mehl" in result["failed"]
        assert "1 Ei" in result["added"]

@pytest.mark.asyncio
async def test_empty_items_returns_no_items():
    with patch("app.services.bring_service._get_bring") as mock_get:
        bring = AsyncMock()
        bring.load_lists = AsyncMock(return_value=[{"listUuid": "l1", "listName": "Liste"}])
        mock_get.return_value = bring
        result = await add_items_to_shopping_list([])
        assert result["status"] == "no_items_added"
