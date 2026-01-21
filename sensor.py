# sensor.py
from __future__ import annotations
from datetime import datetime #, date
import logging

# from const import DOMAIN
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util
from homeassistant.helpers.translation import async_get_translations

from .const import DOMAIN
from .entity import DSTForensics

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry:ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    # Use Home Assistant's configured timezone
    tz_str = hass.config.time_zone
    # We do NOT pass True here anymore. We handle the first update in the entity.
    async_add_entities([DSTNextChangeSensor(tz_str)])


class DSTNextChangeSensor(SensorEntity):
    """The DST Transition Sensor."""
    _attr_has_entity_name = True
    _attr_translation_key = "dst_change_sensor"
    _attr_icon = "mdi:clock-alert"
    _attr_name = "Next DST Change"
    _attr_has_entity_name = True  # Best practice: uses integration name + entity name

    def __init__(self, timezone_str: str) -> None:
        """Initialise the sensor."""
        self._logic = DSTForensics(timezone_str)
        self._attr_unique_id = f"{timezone_str}_next_dst_change"

        # Internal Cache
        self._cached_info = None
        self._last_calculated_at = None
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
        await self._update_state_logic()

        # 2. Schedule the daily update at 00:01
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._scheduled_update, hour=0, minute=1, second=0
            )
        )

    @callback
    async def _scheduled_update(self, _now: datetime) -> None:
        """Callback for scheduled daily update."""
        await self._update_state_logic()
        self.async_write_ha_state()

    async def _update_state_logic(self) -> None:
        """Core logic to fetch data from our Forensics class."""

        now_utc = dt_util.utcnow()

        # --- Logic Gate: Should we recalculate? ---
        should_recalculate = False

        if self._cached_info is None:
            # 1. No data available
            should_recalculate = True
        elif now_utc >= self._cached_info["moment"]:
            # 2. Upcoming change is now in the past
            should_recalculate = True
        elif (self._cached_info["moment"] - now_utc).days < 7:
            # 3. Upcoming change is less than a week away (Fail-safe for precision)
            should_recalculate = True
        elif self._last_calculated_at and (now_utc - self._last_calculated_at).days >= 7:
            # 4. Last calculation was more than a week ago
            should_recalculate = True    

        # --- Execution ---
        if should_recalculate:
            # This looks into your strings.json (or the localized equivalent)
            translations = await async_get_translations(
                self.hass,
                self.hass.config.language,
                "entity_component",
                [DOMAIN]
            )

            # Helper to find the string in the translation map
            def get_string(category, key):
                # The translation map key structure: component.DOMAIN.entity_component._.state_attributes.CATEGORY.state.KEY
                path = f"component.{DOMAIN}.entity_component.sensor.state_attributes.{category}.state.{key}"
                return translations.get(path, key) # Fallback to the key itself if not found            
            # Expensive: Run the Binary Search
            self._cached_info = self._logic.get_dst_info()
            self._last_calculated_at = now_utc
            self._cached_info["direction"] = get_string("direction", self._cached_info["direction"])
            self._cached_info["message"] = get_string("message", self._cached_info["message"])
            self._cached_info["current_period"] = get_string("current_period", self._logic.get_current_period_key())
            _LOGGER.debug("DST Sensor: Performed full binary search recalculation.")
        else:
            # Cheap: Reuse cached moment, but recalculate the countdown
            if self._cached_info is not None and self._cached_info.get("moment") is not None:
                self._cached_info["days_to_event"] = (self._cached_info["moment"].date() - now_utc.date()).days
                _LOGGER.debug("DST Sensor: Reusing cached transition data.")                
            else:
                _LOGGER.debug("DST Sensor: No cached transition data to reuse.")                

        info = self._cached_info
        
        # current_tz_name = datetime.now(self._logic.tz).strftime('%Z')

        if info is not None:
            self._data = {
                "moment": info["moment"],
                "direction": info["direction"],
                "days_to_event": info["days_to_event"],
                "date": info["date"],
                "iso": info["iso"],
                "timezone": self._logic.tz.key,
                "message": info["message"], 
                "last_recalculated": self._last_calculated_at.isoformat(), # pyright: ignore[reportOptionalMemberAccess]
                "current_period": info["current_period"],
            }
        else:
            self._data = {
                "moment": None,
                "direction": None,
                "days_to_event": None,
                "date": None,
                "iso": None,
                "timezone": getattr(self._logic.tz, "key", None),
                "last_recalculated": None,
                "message": None,
                "current_period": None,
            }
