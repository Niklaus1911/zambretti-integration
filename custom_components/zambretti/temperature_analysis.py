import logging
from datetime import timedelta

from homeassistant.components.recorder import history
from homeassistant.util import dt as dt_util

from .helpers import safe_float

_LOGGER = logging.getLogger(__name__)


async def determine_temperature_effect(hass, entity_id):
    """Fetch temperature history and determine its effect, adjusting for sunset and sunrise."""

    # ✅ Ensure time is always in UTC
    start_time = dt_util.utcnow() - timedelta(hours=2)
    end_time = dt_util.utcnow()

    # ✅ Use `significant_changes_only=False` & `minimal_response=False` to get ALL changes
    history_data = await hass.async_add_executor_job(
        history.get_significant_states,
        hass,
        start_time,
        end_time,
        [entity_id],
        None,
        False,
        False,
        False,
    )

    if not history_data or entity_id not in history_data:
        _LOGGER.debug(f"⚠️ No history for {entity_id}.")
        return "Apprendimento trend temperatura", 0, 1, 0

    # If only one reading, return a learning state
    if len(history_data[entity_id]) == 1:
        earliest_available_temp = safe_float(history_data[entity_id][0].state)
        return "Apprendimento trend temperatura", 0, 1, 0

    # Determine oldest and newest temperature readings
    try:
        earliest_available_temp = safe_float(history_data[entity_id][0].state)
        latest_temp = safe_float(history_data[entity_id][-1].state)
    except ValueError:
        return "Dati temperatura non validi", 0, len(history_data[entity_id]), 0

    temp_change = latest_temp - earliest_available_temp

    # 🌅 Retrieve sunrise and sunset times from Home Assistant's sun entity
    sun_state = hass.states.get("sun.sun")
    if (
        sun_state
        and "next_rising" in sun_state.attributes
        and "next_setting" in sun_state.attributes
    ):
        sunrise = dt_util.parse_datetime(
            sun_state.attributes["next_rising"]
        ).astimezone(dt_util.DEFAULT_TIME_ZONE)
        sunset = dt_util.parse_datetime(
            sun_state.attributes["next_setting"]
        ).astimezone(dt_util.DEFAULT_TIME_ZONE)
    else:
        _LOGGER.debug(
            "⚠️ Could not retrieve sunrise/sunset times from sun.sun. Skipping adjustments."
        )
        sunrise, sunset = None, None

    # 🌅 Define sunset/sunrise bandwidth (1 hour before & after)
    sunset_window_start = sunset - timedelta(hours=1)
    sunset_window_end = sunset + timedelta(hours=3)
    sunrise_window_start = sunrise - timedelta(hours=1)
    sunrise_window_end = sunrise + timedelta(hours=5)

    current_time = dt_util.as_local(dt_util.utcnow()).time()

    in_sunrise_window = (
        sunrise_window_start.time() <= current_time <= sunrise_window_end.time()
    )
    in_sunset_window = (
        sunset_window_start.time() <= current_time <= sunset_window_end.time()
    )

    _LOGGER.debug(f"🌅 Sunrise: {sunrise}, Sunset: {sunset}")
    _LOGGER.debug(
        f"🌅 Current Time: {current_time} | Sunrise Window: {in_sunrise_window} | Sunset Window: {in_sunset_window}"
    )

    # 🌓 Halve temperature change if it's during sunrise or sunset window
    if (in_sunset_window) and temp_change < 0:
        _LOGGER.debug("🌅 Temperature drop detected near sunset, halving temp change.")
        temp_change /= 2
    elif (in_sunrise_window) and temp_change > 0:
        _LOGGER.debug("🌅 Temperature rise detected near sunrise, halving temp change.")
        temp_change /= 2

    # Determine alert level based on adjusted temp_change
    alert_level = 0
    if temp_change >= 10:
        temp_effect = (
            "Riscaldamento rapido e importante; possibile ondata di calore, venti termici forti"
        )
        alert_level = 3
    elif temp_change >= 5:
        temp_effect = (
            "Aumento temperatura evidente; fronte caldo in arrivo, vento in aumento"
        )
    elif temp_change <= -10:
        temp_effect = (
            "Calo termico marcato; fronte freddo, forti raffiche e temporali"
        )
        alert_level = 5
    elif temp_change <= -5:
        temp_effect = "Raffreddamento rapido e importante; meteo instabile, vento in aumento"
        alert_level = 3
    else:
        temp_effect = "Nessuna allerta temperatura"

    return temp_effect, temp_change, len(history_data[entity_id]), alert_level
