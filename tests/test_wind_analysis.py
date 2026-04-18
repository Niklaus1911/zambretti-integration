from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from custom_components.zambretti import wind_analysis


@pytest.mark.asyncio
async def test_calculate_most_frequent_wind_direction_fallback_when_history_missing_key(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Template/helper sensors may have current state but no recorder key; fallback must work."""
    entity_id = "sensor.forecast_direzione_vento_met_no"
    hass.states.async_set(entity_id, "20")

    # Recorder result exists but does not include our entity_id key.
    monkeypatch.setattr(
        wind_analysis.history,
        "get_significant_states",
        lambda *args, **kwargs: {"sensor.other": []},
    )

    direction, points = await wind_analysis.calculate_most_frequent_wind_direction(
        hass, entity_id
    )

    assert direction == "N-NE"
    assert points == 1


@pytest.mark.asyncio
async def test_calculate_most_frequent_wind_direction_returns_error_when_no_state(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When neither history nor current state are usable, keep explicit error output."""
    entity_id = "sensor.forecast_direzione_vento_met_no"

    monkeypatch.setattr(
        wind_analysis.history,
        "get_significant_states",
        lambda *args, **kwargs: {},
    )

    direction, points = await wind_analysis.calculate_most_frequent_wind_direction(
        hass, entity_id
    )

    assert direction == "Errore: direzione vento non disponibile."
    assert points == 0
