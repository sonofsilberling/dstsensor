# __init__.py
"""DST Sensor Integration for Home Assistant.

This integration provides sensors that track Daylight Saving Time (DST) transitions
using high-precision binary search algorithms. It automatically detects the system
timezone and provides countdown information for upcoming clock changes.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

# Define which platforms this integration supports
# Currently only provides sensor entities
PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DST Sensor integration from a config entry.
    
    This function is called when the integration is being loaded. It forwards
    the setup to the appropriate platform(s) - in this case, just the sensor platform.
    
    Args:
        hass: The Home Assistant instance.
        entry: The config entry containing the integration configuration.
    
    Returns:
        True if setup was successful, False otherwise.
    """
    # Forward the setup to all configured platforms (currently just sensor)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a DST Sensor config entry.
    
    This function is called when the integration is being removed or reloaded.
    It ensures all platforms are properly unloaded and cleaned up.
    
    Args:
        hass: The Home Assistant instance.
        entry: The config entry being unloaded.
    
    Returns:
        True if unload was successful, False otherwise.
    """
    # Unload all platforms associated with this config entry
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
