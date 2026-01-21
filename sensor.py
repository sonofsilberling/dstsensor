# sensor.py
from __future__ import annotations
from datetime import datetime, date

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
# from homeassistant.util import dt as dt_util

# from .const import DOMAIN
from .entity import DSTForensics


async def async_setup_entry(
    hass: HomeAssistant, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    # Use Home Assistant's configured timezone
    tz_str = hass.config.time_zone
    # We do NOT pass True here anymore. We handle the first update in the entity.
    async_add_entities([DSTNextChangeSensor(tz_str)])


class DSTNextChangeSensor(SensorEntity):
    """The DST Transition Sensor."""

    _attr_icon = "mdi:clock-alert"
    _attr_name = "Next DST Change"
    _attr_has_entity_name = True  # Best practice: uses integration name + entity name

    def __init__(self, timezone_str: str) -> None:
        """Initialize the sensor."""
        self._logic = DSTForensics(timezone_str)
        self._attr_unique_id = f"{timezone_str}_next_dst_change"
        self._data = {}

    @property
    def native_value(self) -> str | None:
        """Return the number of days to the next change as the state."""
        # if moment := self._data.get("moment"):
        #     return moment.date().isoformat()
        if days_to_event := self._data.get("days_to_event"):
            if days_to_event == 0:
                return "Today"
            elif days_to_event == 1:
                return "Tomorrow"
            else:
                return f"In {days_to_event} days"
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._data

    async def async_added_to_hass(self) -> None:
        """Handle being added to HASS."""
        # 1. Perform the very first calculation
        self._update_state_logic()

        # 2. Schedule the daily update at 00:01
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._scheduled_update, hour=0, minute=1, second=0
            )
        )

    @callback
    def _scheduled_update(self, _now: datetime) -> None:
        """Callback for scheduled daily update."""
        self._update_state_logic()
        self.async_write_ha_state()

    def _update_state_logic(self) -> None:
        """Core logic to fetch data from our Forensics class."""
        info = self._logic.get_dst_info()
        current_period = self._logic.get_current_period_name()
        # current_tz_name = datetime.now(self._logic.tz).strftime('%Z')

        self._data = {
            "moment": info["moment"],
            "direction": info["direction"],
            "days_to_event": info["days_to_event"],
            "date": info["date"],
            "iso": info["iso"],
            "timezone": self._logic.tz.key,
            "message": info["message"], 
            "current_period": current_period,
            # "abbreviation" = current_tz_name,
        }
