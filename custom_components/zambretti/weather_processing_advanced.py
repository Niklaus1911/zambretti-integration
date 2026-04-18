import calendar
import logging
from datetime import datetime, timedelta

import numpy as np
from homeassistant.components.recorder import history
from homeassistant.util import dt as dt_util

from .dictionaries import MONTHLY_NORMALS_BY_REGION
from .helpers import safe_float

_LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.DEBUG)  # Or use logging.INFO for less verbosity

MONTH_ABBR_IT = {
    1: "Gen",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "Mag",
    6: "Giu",
    7: "Lug",
    8: "Ago",
    9: "Set",
    10: "Ott",
    11: "Nov",
    12: "Dic",
}


async def generate_pressure_forecast_advanced(
    hass, entity_id, current_pressure, region, short=False, region_name=None
):
    # Monthly averages (should be defined outside function ideally)
    region_normals = MONTHLY_NORMALS_BY_REGION.get(region)

    if not region_normals:
        return f"❌ Regione '{region}' non trovata nelle norme di pressione."

    # Get month here, no pass as variable
    month = datetime.now().month
    month_name = MONTH_ABBR_IT.get(month, calendar.month_abbr[month])

    # Get normal pressure for this month and region
    normal = region_normals.get(month, 1015)
    anomaly = current_pressure - normal

    # Classify anomaly
    if anomaly > 5:
        pressure_context = "Pressione insolitamente alta - situazione molto stabile"
    elif anomaly > 2:
        pressure_context = "Leggermente sopra la media - tendenza stabile"
    elif anomaly > -2:
        pressure_context = "Vicina alla media stagionale - variabilita normale"
    elif anomaly > -5:
        pressure_context = "Sotto la media - instabilita in aumento"
    else:
        pressure_context = "Insolitamente bassa - probabile fase perturbata"

    # Get pressure trends in hPa/hr
    trend_3h = await get_trend(hass, entity_id, 3)
    trend_6h = await get_trend(hass, entity_id, 6)
    trend_12h = await get_trend(hass, entity_id, 12)

    # Trend classification
    def classify_trend(trend):
        if trend > 1.0:
            return "↑↑↑ (aumento rapido)"
        elif trend > 0.5:
            return "↑↑ (aumento deciso)"
        elif trend > 0.1:
            return "↑ (in aumento)"
        elif trend > -0.1:
            return "→ (stabile)"
        elif trend > -0.5:
            return "↓ (in calo)"
        elif trend > -1.0:
            return "↓↓ (calo rapido)"
        else:
            return "⬇⬇⬇ (in crollo)"

    trend_labels = {
        "3h": classify_trend(trend_3h),
        "6h": classify_trend(trend_6h),
        "12h": classify_trend(trend_12h),
    }

    # Forecast summary & warning level
    if trend_3h < -1.0:
        trend_summary = "La pressione e in crollo - molto probabile l'arrivo di tempesta o groppo."
        warning_level = 5
    elif trend_3h < -0.5 and trend_6h < -0.5 and trend_12h < -0.5:
        trend_summary = "Calo forte e costante - molto probabile meteo perturbato o in peggioramento."
        warning_level = 4
    elif trend_3h > 0.5 and trend_6h > 0.5 and trend_12h > 0.5:
        trend_summary = "Aumento forte e costante - miglioramento e tempo stabile."
        warning_level = 1
    elif trend_3h < 0 and trend_6h > 0 and trend_12h > 0:
        trend_summary = "Calo di breve periodo in un trend in aumento - possibile stabilizzazione dopo una flessione."
        warning_level = 2
    elif trend_3h > 0 and trend_6h < 0 and trend_12h < 0:
        trend_summary = "Rialzo di breve periodo in un trend in calo - possibile miglioramento temporaneo."
        warning_level = 3
    elif -0.1 < trend_3h < 0.1 and -0.1 < trend_6h < 0.1 and -0.1 < trend_12h < 0.1:
        trend_summary = "Pressione stabile su tutte le finestre - condizioni stabili."
        warning_level = 2 if anomaly < -2 else 1
    else:
        trend_summary = "Trend di pressione misti - possibile instabilita o fase di transizione."
        warning_level = 3 if anomaly < -2 else 2

    if short:
        # Short summary, under 255 characters
        return (
            f"{current_pressure:.1f} hPa ({anomaly:+.1f} rispetto alla norma) - "
            f"{trend_labels['3h']}/{trend_labels['6h']}/{trend_labels['12h']} - "
            f"{trend_summary} [Livello {warning_level}/5]"
        )[:255]

    display_region = region_name or region.replace("_", " ").title()

    # Full forecast
    # Compose result
    forecast = (
        f"🧭 Pressione attuale: {current_pressure:.1f} hPa\n"
        f"📊 Pressione vs norma {display_region} {month_name} ({normal} hPa): {anomaly:+.1f} hPa\n"
        f"🌀 Contesto pressione: {pressure_context}\n\n"
        f"📉 Trend 3h: {trend_labels['3h']} ({trend_3h:+.2f} hPa/h)\n"
        f"📉 Trend 6h: {trend_labels['6h']} ({trend_6h:+.2f} hPa/h)\n"
        f"📉 Trend 12h: {trend_labels['12h']} ({trend_12h:+.2f} hPa/h)\n\n"
        f"🗺️ Previsione: {trend_summary}\n"
        f"⚠️ Livello di allerta: {warning_level}/5"
    )

    return forecast


async def get_trend(hass, entity_id, trend_duration):
    """Fetches historical pressure data, analyzing strongest rising or falling trend."""

    # Set the maximum deviation to switch from straight line analysis to U-shaped analysis
    # If the model detects U-curves too often, try increasing the threshold (e.g., avg_deviation > 2.0).
    # If it sticks to straight-line too much, decrease it slightly (e.g., avg_deviation > 1.0).
    MAX_DEVIATION = 1.5

    # Fixed interval of 15 minutes, 12 samples over 3 hours
    hours_to_read = safe_float(trend_duration)
    time_interval_minutes = 15
    num_intervals = (60 / time_interval_minutes) * hours_to_read

    # Get current time & calculate start time
    end_time = dt_util.utcnow()
    start_time = end_time - timedelta(hours=hours_to_read)

    # Fetch recorded history from Home Assistant
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
        _LOGGER.debug(
            f"⚠️ No history data available for {entity_id}. Using current state instead."
        )
        return "learning", "", "", 0, "", 0  # No data at all, return steady trend

    _LOGGER.debug(f"History array: {history_data}")

    # Ensure data is sorted in time order (oldest → newest)
    data_points = sorted(history_data[entity_id], key=lambda state: state.last_changed)

    pressure_values = []
    timestamps = []
    last_used_time = None

    # Select one reading per interval
    for state in data_points:
        rounded_time = state.last_changed.replace(
            minute=(state.last_changed.minute // time_interval_minutes)
            * time_interval_minutes,
            second=0,
            microsecond=0,
        )

        if last_used_time is None or rounded_time > last_used_time:
            pressure_values.append(safe_float(state.state))
            timestamps.append(rounded_time.timestamp())  # Store time in seconds
            last_used_time = rounded_time

        if len(pressure_values) >= num_intervals:
            break

    if len(pressure_values) < 2:
        return "learning", "", "", 0, "", 0  # No data at all, return steady trend

    _LOGGER.debug(f"DPT: pressure values {len(pressure_values)}")
    _LOGGER.debug(f"Pressure values array: {pressure_values}")
    _LOGGER.debug(f"Timestamp array: {timestamps}")

    # **Straight-Line Method (Linear Regression)**
    x = np.array(timestamps) - timestamps[0]  # Convert timestamps to relative time
    y = np.array(pressure_values)

    # Fit a straight line (1st degree polynomial)
    slope, intercept = np.polyfit(x, y, 1)

    # Calculate how well this straight-line fits the actual data
    fitted_y = slope * x + intercept
    deviations = np.abs(y - fitted_y)  # Absolute deviations from the fitted line
    avg_deviation = np.mean(deviations)  # Mean deviation

    _LOGGER.debug(f"DPT: Straight-line slope: {slope}, Avg deviation: {avg_deviation}")

    # **Decide if we switch to U-curve detection**
    # If deviations are large, fall back to U-curve method
    if avg_deviation > MAX_DEVIATION:  # Adjust this threshold as needed
        _LOGGER.debug(
            "DPT: Deviation from straight-line too large. Switching to U-curve analysis."
        )

        # **U-curve Method**
        min_pressure = min(pressure_values)
        max_pressure = max(pressure_values)
        min_index = pressure_values.index(min_pressure)
        max_index = pressure_values.index(max_pressure)

        last_pressure = pressure_values[-1]  # Compare to latest reading

        time_to_min = (len(pressure_values) - min_index) * (
            time_interval_minutes / 60
        )  # Convert to hours
        time_to_max = (len(pressure_values) - max_index) * (
            time_interval_minutes / 60
        )  # Convert to hours

        slope_to_min = (
            (last_pressure - min_pressure) / time_to_min if time_to_min > 0 else 0
        )
        slope_to_max = (
            (last_pressure - max_pressure) / time_to_max if time_to_max > 0 else 0
        )

        slope = slope_to_min if abs(slope_to_min) > abs(slope_to_max) else slope_to_max
    else:
        _LOGGER.debug(
            f"DPT2: Straight-line slope: {slope}, Avg deviation: {avg_deviation}"
        )

        # **Use Straight-Line Slope as Trend**
        # Convert slope to hPa per hour
        slope = slope * (3600)

    return slope
