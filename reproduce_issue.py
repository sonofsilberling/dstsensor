# reproduce_issue.py
import asyncio
import logging
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, AsyncMock

# Mock Home Assistant modules
import sys
from types import ModuleType

ha_util = ModuleType("homeassistant.util.dt")
ha_util.utcnow = MagicMock(return_value=datetime.now())
sys.modules["homeassistant.util.dt"] = ha_util

ha_config_entries = ModuleType("homeassistant.config_entries")
ha_config_entries.ConfigEntry = MagicMock
sys.modules["homeassistant.config_entries"] = ha_config_entries

ha_sensor = ModuleType("homeassistant.components.sensor")
ha_sensor.SensorEntity = type("SensorEntity", (), {})
ha_sensor.SensorDeviceClass = MagicMock
ha_sensor.SensorEntityDescription = MagicMock
sys.modules["homeassistant.components.sensor"] = ha_sensor

ha_const = ModuleType("homeassistant.const")
ha_const.EntityCategory = MagicMock
ha_const.UnitOfTime = MagicMock
ha_const.Platform = MagicMock
sys.modules["homeassistant.const"] = ha_const

ha_core = ModuleType("homeassistant.core")
ha_core.callback = lambda x: x
ha_core.HomeAssistant = MagicMock
sys.modules["homeassistant.core"] = ha_core

ha_event_platform = ModuleType("homeassistant.helpers.entity_platform")
ha_event_platform.AddEntitiesCallback = MagicMock
sys.modules["homeassistant.helpers.entity_platform"] = ha_event_platform

ha_event = ModuleType("homeassistant.helpers.event")
ha_event.async_track_time_change = MagicMock()
sys.modules["homeassistant.helpers.event"] = ha_event

ha_translations = ModuleType("homeassistant.helpers.translation")
ha_translations.async_get_translations = AsyncMock(return_value={})
sys.modules["homeassistant.helpers.translation"] = ha_translations

ha_typing = ModuleType("homeassistant.helpers.typing")
ha_typing.StateType = Any
sys.modules["homeassistant.helpers.typing"] = ha_typing

print("Starting reproduction script...")
# Mock relative imports
sys.modules["const"] = ModuleType("const")
sys.modules["const"].DOMAIN = "dstsensor"
sys.modules["entity"] = sys.modules["entity"] if "entity" in sys.modules else ModuleType("entity")

print("Importing sensor...")
# Import the code to test
from sensor import DSTNextChangeSensor, DSTSensorEntityDescription
print("Imported sensor.")

async def test_non_dst_timezone():
    print("Testing timezone without DST (UTC)...")
    hass = MagicMock()
    hass.config.language = "en"
    
    description = DSTSensorEntityDescription(key="test")
    # Using UTC which has no DST
    sensor = DSTNextChangeSensor(description, "UTC", "test_entry_id")
    sensor.hass = hass
    
    # This should NOT crash
    await sensor._update_state_logic()
    
    print("Resulting data attributes:")
    for k, v in sensor._data.items():
        print(f"  {k}: {v}")
    
    assert sensor._cached_info is None
    assert sensor._data["moment"] is None
    assert sensor._data["timezone"] == "UTC"
    print("Test passed! No crash and attributes are correctly set to None.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(test_non_dst_timezone())
