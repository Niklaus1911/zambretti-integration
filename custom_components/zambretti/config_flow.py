import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
)
from .options_flow import ZambrettiOptionsFlowHandler


class ZambrettiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Zambretti integration."""

    async def async_step_user(self, user_input=None) -> dict:
        """Handle the initial step where the user selects sensors."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title="Zambretti Forecast", data=user_input)

        # ✅ Define schema with clear field names and suggested values
        schema = vol.Schema(
            {
                vol.Required(
                    "wind_direction_sensor",
                    description={"suggested_value": "Sensore direzione vento (360 gradi)"},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    "wind_speed_sensor_knots",
                    description={"suggested_value": "Sensore velocita vento (nodi)"},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    "atmospheric_pressure_sensor",
                    description={
                        "suggested_value": "Sensore pressione esterna (hPa)"
                    },
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    "temperature_sensor",
                    description={
                        "suggested_value": "Sensore temperatura esterna (gradi C)"
                    },
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    "humidity_sensor",
                    description={"suggested_value": "Sensore umidita esterna (%)"},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    "device_tracker_home",
                    description={
                        "suggested_value": "Device tracker per la tua posizione (di solito casa)"
                    },
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="device_tracker")
                ),
                vol.Required(
                    "update_interval_minutes", default="10"
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["1", "5", "10", "15", "20", "30", "60"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    "pressure_history_hours", default="3"
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["3", "6", "9", "12"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    "fog_area_type", default="normal"
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {
                                "value": "frequent_dense_fog",
                                "label": "Nebbia fitta frequente",
                            },
                            {"value": "fog_prone", "label": "Zona soggetta a nebbia"},
                            {"value": "normal", "label": "Normale"},
                            {"value": "rare_fog", "label": "Nebbia rara"},
                            {
                                "value": "hardly_ever_fog",
                                "label": "Quasi mai nebbia",
                            },
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "info": "Seleziona i sensori per vento, pressione, temperatura, umidita e GPS."
            },
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return ZambrettiOptionsFlowHandler()
