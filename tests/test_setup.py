from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import custom_components.zambretti as zambretti_init
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.zambretti.const import DOMAIN


@pytest.mark.asyncio
async def test_setup_component(hass: HomeAssistant) -> None:
    # Ensure the integration can be set up via async_setup_component without errors.
    assert await async_setup_component(hass, DOMAIN, {})


@pytest.mark.asyncio
async def test_async_setup_entry_registers_update_listener(hass: HomeAssistant) -> None:
    """Config entry setup should register an options update listener."""
    remove_listener = MagicMock()
    entry = SimpleNamespace(
        entry_id="entry-id",
        data={},
        add_update_listener=MagicMock(return_value=remove_listener),
        async_on_unload=MagicMock(),
    )

    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    assert await zambretti_init.async_setup_entry(hass, entry)
    entry.add_update_listener.assert_called_once_with(zambretti_init.update_listener)
    entry.async_on_unload.assert_called_once_with(remove_listener)
