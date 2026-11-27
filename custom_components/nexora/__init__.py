"""Nexora opt-in conversation agent."""
import json
import logging
from pathlib import Path

from homeassistant.components import conversation
from homeassistant.exceptions import ConfigEntryNotReady

from .agent import NexoraAgent
from .menu import Menu

DOMAIN = "nexora"
_LOGGER = logging.getLogger(__name__)

def load_catalogs(local):
    """Load built-in and administrator-supplied catalogs at entry setup."""
    import yaml
    paths = [Path(__file__).parent / "catalogs", Path(local)]
    result = []
    for directory in paths:
        for path in sorted(directory.iterdir()) if directory.is_dir() else []:
            if path.suffix not in (".json", ".yaml", ".yml"):
                continue
            if path.stat().st_size > 2_000_000:
                raise ValueError("Catalog too large")
            with path.open(encoding="utf-8") as stream:
                try:
                    result.append(json.load(stream) if path.suffix == ".json" else yaml.safe_load(stream))
                except yaml.YAMLError as err:
                    raise ValueError("Invalid YAML catalog") from err
    return result

async def async_setup_entry(hass, entry):
    try:
        catalogs = await hass.async_add_executor_job(load_catalogs, hass.config.path("nexora", "catalogs"))
        menu = Menu(catalogs, settings=entry.data)
    except (ValueError, TypeError, KeyError, OSError) as err:
        _LOGGER.error("Nexora catalog initialization failed: %s", type(err).__name__)
        raise ConfigEntryNotReady("Invalid Nexora catalog") from err
    agent = NexoraAgent(hass, entry.entry_id, menu, entry.data["fallback_agent"])
    conversation.async_set_agent(hass, entry, agent)
    return True

async def async_unload_entry(hass, entry):
    conversation.async_unset_agent(hass, entry)
    return True
