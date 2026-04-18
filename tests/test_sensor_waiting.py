from __future__ import annotations

from types import SimpleNamespace

import pytest
from homeassistant.core import HomeAssistant

from custom_components.zambretti import sensor as sensor_platform
from custom_components.zambretti.const import DOMAIN
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

    unload_callbacks = []

    def _async_on_unload(callback):
        unload_callbacks.append(callback)
        return callback

    return SimpleNamespace(
        entry_id="test-entry",
        data=data,
        options={},
        async_on_unload=_async_on_unload,
        _unload_callbacks=unload_callbacks,
    )


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
    sensor._schedule_retry_update = lambda: None  # type: ignore[method-assign]

    await sensor.async_update()

    assert sensor.device_tracker_home not in captured["required"]
    assert sensor._attributes["startup_block_reason"] == "update_exception"


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
    entry = _make_entry()
    added: dict[str, object] = {}

    def _add_entities(entities, update_before_add=False):
        added["entities"] = entities
        added["update_before_add"] = update_before_add

    await sensor_platform.async_setup_entry(hass, entry, _add_entities)

    assert added["update_before_add"] is False
    assert len(added["entities"]) == 1
    assert isinstance(added["entities"][0], Zambretti)
    assert len(entry._unload_callbacks) >= 1

    for remove_callback in entry._unload_callbacks:
        remove_callback()


@pytest.mark.asyncio
async def test_async_will_remove_cleans_entity_registry_and_service(
    hass: HomeAssistant,
) -> None:
    """Unloading entity should remove stale registry entry and service registration."""
    entry = _make_entry()
    sensor = Zambretti(hass, entry)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["entities"] = {entry.entry_id: sensor}

    async def _noop_service(call):
        return

    hass.services.async_register(DOMAIN, sensor_platform.SERVICE_FORCE_UPDATE, _noop_service)

    await sensor.async_will_remove_from_hass()

    assert entry.entry_id not in hass.data[DOMAIN]["entities"]
    assert not hass.services.has_service(DOMAIN, sensor_platform.SERVICE_FORCE_UPDATE)


@pytest.mark.asyncio
async def test_schedule_retry_replaces_existing_pending_retry(
    hass: HomeAssistant,
) -> None:
    """Scheduling a retry should cancel any previous pending retry callback."""
    sensor = Zambretti(hass, _make_entry())
    cancellations = {"count": 0}

    def _cancel_old():
        cancellations["count"] += 1

    sensor._retry_unsub = _cancel_old
    sensor._schedule_retry_update()

    assert cancellations["count"] == 1
    assert sensor._retry_unsub is not None

    sensor._cancel_retry_update()
    assert sensor._retry_unsub is None


@pytest.mark.asyncio
async def test_force_update_targets_single_entity_id(hass: HomeAssistant) -> None:
    """force_update with a string entity_id should update only the matching entity."""

    class DummyEntity:
        def __init__(self, entity_id: str):
            self.entity_id = entity_id
            self.calls = 0

        async def async_update(self):
            self.calls += 1

    entry = _make_entry()

    def _add_entities(entities, update_before_add=False):
        return

    await sensor_platform.async_setup_entry(hass, entry, _add_entities)

    ent_a = DummyEntity("sensor.zambretti_a")
    ent_b = DummyEntity("sensor.zambretti_b")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["entities"] = {"a": ent_a, "b": ent_b}

    await hass.services.async_call(
        DOMAIN,
        sensor_platform.SERVICE_FORCE_UPDATE,
        {"entity_id": "sensor.zambretti_a"},
        blocking=True,
    )

    assert ent_a.calls == 1
    assert ent_b.calls == 0

    for remove_callback in entry._unload_callbacks:
        remove_callback()
    if hass.services.has_service(DOMAIN, sensor_platform.SERVICE_FORCE_UPDATE):
        hass.services.async_remove(DOMAIN, sensor_platform.SERVICE_FORCE_UPDATE)


@pytest.mark.asyncio
async def test_async_update_overlap_guard_skips_second_update(
    hass: HomeAssistant,
) -> None:
    """Concurrent update attempts should not run the internal update body twice."""
    sensor = Zambretti(hass, _make_entry())
    calls = {"count": 0}

    async def _fake_internal_update():
        calls["count"] += 1

    sensor._async_update_internal = _fake_internal_update  # type: ignore[method-assign]

    sensor._update_in_progress = True
    await sensor.async_update()
    assert calls["count"] == 0

    sensor._update_in_progress = False
    await sensor.async_update()
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_async_update_keeps_previous_state_when_started_and_sensors_drop(
    hass: HomeAssistant,
) -> None:
    """After first successful startup, temporary sensor drops should not lock to waiting."""
    sensor = Zambretti(hass, _make_entry())
    sensor._attributes["fully_started"] = True
    sensor._set_state("Previsione precedente valida")

    sensor.sensors_valid = lambda _ids: (False, ["sensor.pressure: unavailable"])  # type: ignore[method-assign]
    sensor._state_from_entity_or_cache = lambda _eid, _attr: None  # type: ignore[method-assign]

    calls = {"retry": 0}

    def _schedule_retry():
        calls["retry"] += 1

    sensor._schedule_retry_update = _schedule_retry  # type: ignore[method-assign]

    await sensor.async_update()

    assert calls["retry"] == 1
    assert sensor.state == "Previsione precedente valida"


@pytest.mark.asyncio
async def test_async_update_exception_continues_waiting_attempts(
    hass: HomeAssistant,
) -> None:
    """Unexpected update exceptions should not freeze waiting attempt progression."""
    sensor = Zambretti(hass, _make_entry())
    sensor.counter = 22
    sensor._set_state("Zambretti in attesa dei sensori ... tentativo 22")

    async def _boom():
        raise RuntimeError("forced update error")

    sensor._async_update_internal = _boom  # type: ignore[method-assign]

    calls = {"retry": 0}

    def _schedule_retry():
        calls["retry"] += 1

    sensor._schedule_retry_update = _schedule_retry  # type: ignore[method-assign]

    await sensor.async_update()

    assert calls["retry"] == 1
    assert sensor.counter == 23
    assert "tentativo 23" in sensor.state
    assert sensor._attributes["startup_block_reason"] == "update_exception"
    assert sensor._attributes["update_error_count"] == 1
    assert "forced update error" in sensor._attributes["last_update_error"]
