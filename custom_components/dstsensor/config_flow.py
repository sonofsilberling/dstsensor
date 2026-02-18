from __future__ import annotations
from homeassistant import config_entries
from .const import DOMAIN

class DSTSensorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configuration flow for the DST Sensor integration.
    
    This config flow handles the setup of the DST Sensor integration in Home Assistant.
    It enforces a single-instance pattern, meaning only one instance of this integration
    can be configured per Home Assistant installation.
    
    The integration requires no user configuration as it automatically detects the
    system timezone from Home Assistant's settings.
    
    Attributes:
        VERSION: Config flow version (inherited from ConfigFlow)
        domain: The integration domain identifier (set to DOMAIN constant)
    """

    async def async_step_user(self, user_input=None):
        """Handle the initial user configuration step.
        
        This method is called when a user initiates the configuration flow from the
        Home Assistant UI. It implements a single-instance check to prevent multiple
        configurations of the same integration.
        
        The flow has three possible outcomes:
        1. Abort if an instance already exists (single_instance_allowed)
        2. Create entry if user confirms the setup
        3. Show form if initial visit (no user_input yet)
        
        Args:
            user_input: Dictionary containing user-provided configuration data.
                       None on the initial form display, populated after user submission.
        
        Returns:
            FlowResult: One of:
                - async_abort() if integration is already configured
                - async_create_entry() to complete setup with empty config
                - async_show_form() to display the initial configuration form
        """
        # Check if this integration is already configured
        # Only one instance is allowed per Home Assistant installation
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        
        # If user has submitted the form (user_input is not None),
        # create the config entry with no additional data needed
        if user_input is not None:
            return self.async_create_entry(title="DST Sensor", data={})
        
        # Initial form display - show empty form to user
        # No input fields are needed as the integration auto-configures
        return self.async_show_form(step_id="user")
