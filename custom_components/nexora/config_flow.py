"""Configure a fallback agent and local account labels."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import conversation

class ConfigFlow(config_entries.ConfigFlow, domain="nexora"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        if user_input is not None:
            data = {key: value.strip() for key, value in user_input.items()}
            try:
                agent = conversation.async_get_agent(self.hass, data["fallback_agent"])
            except (ValueError, KeyError):
                agent = None
            if agent is None:
                errors["fallback_agent"] = "invalid_agent"
            elif any(len(data.get(key, "")) > 40 for key in ("primary_label", "secondary_label", "secondary")):
                errors["base"] = "invalid_label"
            elif not data.get("primary_label"):
                errors["primary_label"] = "invalid_label"
            else:
                return self.async_create_entry(title="Nexora", data=data)
        defaults = user_input or {}
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("fallback_agent", default=defaults.get("fallback_agent", "conversation.home_assistant")): str,
            vol.Required("primary_label", default=defaults.get("primary_label", "主账户")): str,
            vol.Optional("secondary_label", default=defaults.get("secondary_label", "第二账户")): str,
            vol.Optional("secondary", default=defaults.get("secondary", "")): str,
        }), errors=errors)
