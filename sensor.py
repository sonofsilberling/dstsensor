from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.event import async_track_time_change
from homeassistant.core import callback
from .const import DOMAIN
from .entity import DSTForensics

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform."""
    # Use Home Assistant's configured timezone
    tz_str = hass.config.time_zone
    async_add_entities([DSTNextChangeSensor(tz_str)], True)

class DSTNextChangeSensor(SensorEntity):
    _attr_icon = "mdi:clock-alert"
    _attr_name = "Next DST Change"
    _attr_unique_id = "dst_next_change_sensor"

    def __init__(self, timezone_str):
        self._logic = DSTForensics(timezone_str)
        self._state = None
        self._attributes = {}

    async def async_added_to_hass(self):
        """Schedule the daily update."""
        # Update every day at 00:01
        self.async_on_remove(
            async_track_time_change(self.hass, self._update_sensor, hour=0, minute=1, second=0)
        )

    @callback
    def _update_sensor(self, _now=None):
        """Update the sensor state and attributes."""
        info = self._logic.get_dst_info()
        self._state = info["moment"].date().isoformat()
        self._attributes = {
            "moment": info["moment"].isoformat(),
            "direction": info["direction"],
            "days_to_event": info["days_to_event"],
            "timezone": self._logic.tz.key
        }
        self.async_write_ha_state()

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    async def async_update(self):
        """Manual update call (used on first setup)."""
        self._update_state_logic()

    def _update_state_logic(self):
        # Sync wrapper for the update
        self._update_sensor()