from __future__ import annotations

from types import SimpleNamespace

import pytest
from homeassistant.core import HomeAssistant

from custom_components.zambretti import sensor as sensor_platform
from custom_components.zambretti.sensor import Zambretti


def _make_entry(**overrides):
    data = {
        "wind_direction_sensor": "sensor.wind_direction",
        "wind_speed_sensor_knots": "sensor.wind_speed",
        "atmospheric_pressure_sensor": "sensor.pressure",
        "temperature_sensor": "sensor.temperature",
        "humidity_sensor": "sensor.humidity",
        "device_tracker_home": "device_tracker.boat",
        "update_interval_minutes": "10",
        "pressure_history_hours": "3",
        "fog_area_type": "normal",
    }
    data.update(overrides)
    return SimpleNamespace(entry_id="test-entry", data=data, options={})


@pytest.mark.asyncio
async def test_async_update_sensor_gate_excludes_device_tracker(
    hass: HomeAssistant,
) -> None:
    """The initial required-sensor gate should not block on device_tracker state."""
    sensor = Zambretti(hass, _make_entry())
    captured: dict[str, list[str]] = {}

    def _capture_required_sensors(sensor_ids):
        captured["required"] = list(sensor_ids)
        raise RuntimeError("stop-after-capture")

    sensor.sensors_valid = _capture_required_sensors  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="stop-after-capture"):
        await sensor.async_update()

    assert sensor.device_tracker_home not in captured["required"]


@pytest.mark.asyncio
async def test_sensors_valid_reports_invalid_states(hass: HomeAssistant) -> None:
    """Unknown/unavailable/missing sensors should be reported as invalid."""
    sensor = Zambretti(hass, _make_entry())

    hass.states.async_set("sensor.pressure", "unknown")
    hass.states.async_set("sensor.wind_direction", "UNAVAILABLE")
    hass.states.async_set("sensor.temperature", "21.5")

    is_valid, errors = sensor.sensors_valid(
        [
            "sensor.pressure",
            "sensor.wind_direction",
            "sensor.temperature",
            "sensor.missing",
            None,
        ]
    )

    assert not is_valid
    assert any("sensor.pressure" in err for err in errors)
    assert any("sensor.wind_direction" in err for err in errors)
    assert any("sensor.missing" in err for err in errors)
    assert any("missing entity_id in config" in err for err in errors)


@pytest.mark.asyncio
async def test_async_setup_entry_does_not_block_entity_add(
    hass: HomeAssistant,
) -> None:
    """Entity should be added immediately without waiting for first successful update."""
    added: dict[str, object] = {}

    def _add_entities(entities, update_before_add=False):
        added["entities"] = entities
        added["update_before_add"] = update_before_add

    await sensor_platform.async_setup_entry(hass, _make_entry(), _add_entities)

    assert added["update_before_add"] is False
    assert len(added["entities"]) == 1
    assert isinstance(added["entities"][0], Zambretti)
