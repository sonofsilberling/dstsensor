# sensor.py
from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable
from datetime import datetime 
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util
from homeassistant.helpers.translation import async_get_translations
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfTime,
)
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .entity import DSTForensics

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class DSTSensorEntityDescription(SensorEntityDescription):
    """Extended sensor entity description for DST sensors.
    
    This dataclass extends the standard SensorEntityDescription to add
    custom value transformation capabilities specific to DST sensors.
    
    Attributes:
        value: Callable function to transform raw data values. Defaults to identity function.
               Can be used to format or convert sensor values before display.
    """

    value: Callable = lambda x: x


# Sensor type definitions for the DST integration
# This tuple defines all sensor entities that will be created
DST_SENSOR_TYPES: tuple[DSTSensorEntityDescription, ...] = (
    DSTSensorEntityDescription(
        key="daysTotal",  # Unique identifier for this sensor type
        device_class=SensorDeviceClass.DURATION,  # Indicates this measures a duration
        translation_key="days_to_next_change",  # Key for localized name/description
        native_unit_of_measurement=UnitOfTime.DAYS,  # Display unit
        entity_category=EntityCategory.DIAGNOSTIC,  # Categorize as diagnostic info
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DST sensor entities from a config entry.
    
    This is the main entry point for creating sensor entities when the integration
    is configured. It creates one sensor entity for each sensor type defined in
    DST_SENSOR_TYPES.
    
    Args:
        hass: The Home Assistant instance.
        config_entry: The config entry for this integration instance.
        async_add_entities: Callback to add new entities to Home Assistant.
    """
    # Use Home Assistant's configured timezone for DST calculations
    tz_str = hass.config.time_zone
    
    # Create sensor entities for each defined sensor type
    # Each sensor will track DST transitions for the configured timezone
    entities = [
        DSTNextChangeSensor(description, tz_str, config_entry.entry_id) 
        for description in DST_SENSOR_TYPES
    ]
    async_add_entities(entities)


class DSTNextChangeSensor(SensorEntity):
    """Sensor entity that tracks the next DST transition.
    
    This sensor provides comprehensive information about upcoming DST changes,
    including the exact moment, direction (Spring Forward/Fall Back), and countdown.
    
    Key Features:
    - Intelligent caching: Only recalculates when necessary to minimize CPU usage
    - Daily updates: Automatically refreshes at 00:01 each day
    - Dynamic icon: Battery-style icon that depletes as the transition approaches
    - Rich attributes: Provides detailed information about the transition
    
    The sensor uses a sophisticated caching strategy to balance accuracy with efficiency:
    - Full recalculation occurs when:
      1. No cached data exists
      2. The cached transition has passed
      3. The transition is less than 7 days away (for precision)
      4. More than 7 days have passed since last calculation
    - Otherwise, only the countdown is updated using cached data
    
    Attributes:
        _logic: DSTForensics instance for DST calculations
        _cached_info: Cached transition information to avoid repeated calculations
        _last_calculated_at: Timestamp of last full calculation
        _data: Current sensor data exposed as state attributes
    """

    has_entity_name = True
    _attr_translation_key = "dst_change_sensor"
    _attr_has_entity_name = True  # Best practice: uses integration name + entity name

    def __init__(self, description: SensorEntityDescription, timezone_str: str, entry_id: str) -> None:
        """Initialize the DST sensor.
        
        Args:
            description: Entity description defining sensor properties (unit, device class, etc.)
            timezone_str: IANA timezone identifier (e.g., 'Europe/London', 'America/New_York')
            entry_id: Unique identifier for this config entry, used as the entity's unique_id
        """
        # Initialize the DST calculation engine
        self._logic = DSTForensics(timezone_str)
        self.entity_description = description
        self._attr_unique_id = entry_id

        # Internal caching system to minimize expensive binary search calculations
        self._cached_info = None  # Stores full DST transition information
        self._last_calculated_at = None  # Timestamp of last full calculation
        self._data = {}  # Current sensor data (state attributes)

    @property
    def icon(self) -> str:
        """Return a dynamic icon based on days until DST transition.
        
        Uses a battery-style icon that "depletes" as the transition approaches,
        providing a visual countdown indicator. The icon changes at weekly intervals
        for the first 9 weeks, then shows a full battery for transitions further out.
        
        Returns:
            Material Design Icon identifier (mdi:battery-*)
        """
        days = self._data.get('days_to_event')
        if days is None:
            return 'mdi:battery-unknown'  # No data available yet
        # Battery depletes as transition approaches (weekly intervals)
        if days <= 1:  return 'mdi:battery'  # Critical: 0-1 days
        if days <= 7:  return 'mdi:battery-90'  # 2-7 days
        if days <= 14: return 'mdi:battery-80'  # 1-2 weeks
        if days <= 21: return 'mdi:battery-70'  # 2-3 weeks
        if days <= 28: return 'mdi:battery-60'  # 3-4 weeks
        if days <= 35: return 'mdi:battery-50'  # 4-5 weeks
        if days <= 42: return 'mdi:battery-40'  # 5-6 weeks
        if days <= 49: return 'mdi:battery-30'  # 6-7 weeks
        if days <= 56: return 'mdi:battery-20'  # 7-8 weeks
        if days <= 63: return 'mdi:battery-10'  # 8-9 weeks
        return 'mdi:battery-outline'  # 9+ weeks

    @property
    def native_value(self) -> str | None:
        """Return the main sensor state value.
        
        Returns:
            The number of days until the next DST transition, or None if unavailable.
        """
        return self._data.get("days_to_event")

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes.
        
        Provides comprehensive information about the DST transition including:
        - moment: Exact datetime of the transition
        - direction: 'Spring Forward' or 'Fall Back' (localized)
        - date/iso: Various date formats
        - timezone: The timezone being monitored
        - message: Localized description message
        - current_period: 'Summer Time' or 'Winter Time' (localized)
        - last_recalculated: When the binary search was last performed
        
        Returns:
            Dictionary of state attributes.
        """
        return self._data

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to Home Assistant.
        
        This lifecycle method is called when the entity is first added to HA.
        It performs the initial data calculation and sets up the daily update schedule.
        """
        # Step 1: Perform the initial calculation to populate sensor data
        await self._update_state_logic()
        self.async_write_ha_state()
        
        # Step 2: Schedule daily updates at 00:01 (1 minute past midnight)
        # This ensures the countdown is updated daily without excessive recalculation
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._scheduled_update, hour=0, minute=1, second=0
            )
        )

    @callback
    def _scheduled_update(self, _now: datetime) -> None:
        """Handle scheduled daily update callback.
        
        This is a synchronous callback that runs at 00:01 daily. It schedules
        the async update logic to run in the event loop.
        
        Args:
            _now: Current datetime (unused, provided by async_track_time_change)
        """
        self.hass.async_create_task(self._update_state_logic())

    async def _update_state_logic(self) -> None:
        """Core update logic with intelligent caching.
        
        This method implements a sophisticated caching strategy to balance accuracy
        with computational efficiency. The expensive binary search is only performed
        when necessary, otherwise the countdown is simply recalculated from cached data.
        
        Recalculation triggers:
        1. No cached data exists (first run)
        2. The cached transition moment has passed (need next transition)
        3. Transition is less than 7 days away (precision mode)
        4. More than 7 days since last full calculation (freshness check)
        
        Otherwise, only the days_to_event countdown is updated using cached data.
        """

        now_utc = dt_util.utcnow()

        # --- Decision Logic: Determine if full recalculation is needed ---
        should_recalculate = False

        if self._cached_info is None:
            # Trigger 1: No cached data available (initial run)
            should_recalculate = True
        elif now_utc >= self._cached_info["moment"]:
            # Trigger 2: The cached transition has already occurred
            # We need to find the NEXT transition
            should_recalculate = True
        elif (self._cached_info["moment"] - now_utc).days < 7:
            # Trigger 3: Transition is imminent (less than 7 days away)
            # Recalculate for maximum precision as the event approaches
            should_recalculate = True
        elif (
            self._last_calculated_at and (now_utc - self._last_calculated_at).days >= 7
        ):
            # Trigger 4: Last full calculation was over a week ago
            # Periodic refresh to ensure data freshness
            should_recalculate = True

        # --- Execute the appropriate update strategy ---
        if should_recalculate:
            # EXPENSIVE PATH: Full binary search recalculation
            
            # Load localized translations for direction, message, and period strings
            translations = await async_get_translations(
                self.hass, self.hass.config.language, "entity_component", [DOMAIN]
            )

            # Helper function to retrieve localized strings from translation map
            def get_string(category, key):
                """Look up a localized string from the translation dictionary.
                
                Args:
                    category: The category in the translation structure (e.g., 'direction', 'message')
                    key: The specific key to look up within that category
                
                Returns:
                    Localized string, or the key itself if translation not found
                """
                # Translation path structure: component.DOMAIN.entity_component.sensor.state_attributes.CATEGORY.state.KEY
                path = f"component.{DOMAIN}.entity_component.sensor.state_attributes.{category}.state.{key}"
                return translations.get(path, key)  # Fallback to key if not found

            # Perform the expensive binary search to find the next DST transition
            self._cached_info = self._logic.get_dst_info()
            self._last_calculated_at = now_utc

            if self._cached_info is not None:
                # Localize the string values
                self._cached_info["direction"] = get_string(
                    "direction", self._cached_info["direction"]
                )
                self._cached_info["message"] = get_string(
                    "message", self._cached_info["message"]
                )
                self._cached_info["current_period"] = get_string(
                    "current_period", self._logic.get_current_period_key()
                )
                _LOGGER.debug("DST Sensor: Performed full binary search recalculation.")
            else:
                _LOGGER.debug("DST Sensor: No DST transition found for this timezone.")
        else:
            # CHEAP PATH: Reuse cached data, only update the countdown
            # This is much more efficient than running the full binary search
            if (
                self._cached_info is not None
                and self._cached_info.get("moment") is not None
            ):
                # Recalculate only the days remaining using cached transition moment
                local_today = datetime.now(self._logic.tz).date()
                self._cached_info['days_to_event'] = (
                    self._cached_info['moment'].date() - local_today
                ).days
                _LOGGER.debug("DST Sensor: Reusing cached transition data.")
            else:
                _LOGGER.debug("DST Sensor: No cached transition data to reuse.")

        info = self._cached_info

        # Build the final data dictionary for state attributes
        if info is not None:
            # Normal case: We have valid DST transition information
            self._data = {
                "moment": info["moment"],  # Exact datetime of transition
                "direction": info["direction"],  # Localized direction (Spring Forward/Fall Back)
                "days_to_event": info["days_to_event"],  # Countdown in days
                "date": info["date"],  # ISO date string
                "iso": info["iso"],  # Full ISO datetime string
                "timezone": self._logic.tz.key,  # IANA timezone identifier
                "message": info["message"],  # Localized message
                "last_recalculated": self._last_calculated_at.isoformat(),  # pyright: ignore[reportOptionalMemberAccess]
                "current_period": info["current_period"],  # Summer/Winter time (localized)
            }
        else:
            # Edge case: Timezone doesn't observe DST (e.g., Arizona, Hawaii)
            # Populate attributes with None values
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
