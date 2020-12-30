import logging
from datetime import timedelta
from typing import Any, Dict, Optional, List

from homeassistant.components.climate import ClimateEntity

from homeassistant.components.climate.const import (
    HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_HEAT_COOL,
    HVAC_MODE_DRY, HVAC_MODE_FAN_ONLY, HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE, SUPPORT_PRESET_MODE,
    ATTR_CURRENT_TEMPERATURE, ATTR_FAN_MODE,
    PRESET_ECO, PRESET_NONE, PRESET_BOOST,
    ATTR_HVAC_MODE, ATTR_SWING_MODE, ATTR_PRESET_MODE)

from homeassistant.const import (
    TEMP_CELSIUS, ATTR_TEMPERATURE)

_LOGGER = logging.getLogger(__name__)

from . import DOMAIN

SCAN_INTERVAL = timedelta(seconds=300)

OPERATION_LIST = {
    HVAC_MODE_OFF: 'Off',
    HVAC_MODE_HEAT: 'Heat',
    HVAC_MODE_COOL: 'Cool',
    HVAC_MODE_HEAT_COOL: 'Auto',
    HVAC_MODE_DRY: 'Dry',
    HVAC_MODE_FAN_ONLY: 'Fan'
    }

PRESET_LIST = {
    PRESET_NONE: 'Auto',
    PRESET_BOOST: 'Powerful',
    PRESET_ECO: 'Quiet'
}

SUPPORT_FLAGS = (
    SUPPORT_TARGET_TEMPERATURE |
    SUPPORT_FAN_MODE |
    SUPPORT_PRESET_MODE |
    SUPPORT_SWING_MODE )

def api_call_login(func):
    def wrapper_call(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except:
            args[0]._api.login()
            func(*args, **kwargs)
    return wrapper_call

def setup_platform(hass, entry, add_entities, discovery_info=None):
    from pcomfortcloud import constants
    api = hass.data[DOMAIN].get('api')

    _LOGGER.debug("Adding panasonic devices")

    devices = []
    for device in api.get_devices():
        _LOGGER.debug("Setting up %s ...", device)
        devices.append(PanasonicDevice(device, api, constants))

    add_entities(devices, True)

class PanasonicDevice(ClimateEntity):
    """Representation of a Panasonic airconditioning."""

    def __init__(self, device, api, constants):
        """Initialize the device."""
        _LOGGER.debug("Add panasonic device '{0}'".format(device['name']))
        self._api = api
        self._device = device
        self._constants = constants
        self._current_temp = None
        self._is_on = False
        self._hvac_mode = OPERATION_LIST[HVAC_MODE_COOL]

        self._unit = TEMP_CELSIUS
        self._target_temp = None
        self._cur_temp = None
        self._mode = None
        self._eco = 'Auto'

        self._current_fan = None
        self._airswing_hor = None
        self._airswing_vert = None

    def update(self):
        """Update the state of this climate device."""
        try:
            data= self._api.get_device(self._device['id'])
        except:
            _LOGGER.debug("Error trying to get device {id} state, probably expired token, trying to update it...".format(**self._device))
            self._api.login()
            data = self._api.get_device(self._device['id'])

        _LOGGER.debug("Received no data for device {0}".format(data['parameters']))

        if data is None:
            _LOGGER.debug("Received no data for device {id}".format(**self._device))
            return

        if data['parameters']['temperature'] != 126:
            self._target_temp = data['parameters']['temperature']
        else:
            self._target_temp = None

        if data['parameters']['temperatureInside'] != 126:
            self._cur_temp = data['parameters']['temperatureInside']
        else:
            self._cur_temp = None

        if self._device['id'] not in self.hass.data[DOMAIN]:
           self.hass.data[DOMAIN][self._device['id']] = {}

        if data['parameters']['temperatureOutside'] != 126:
            self.hass.data[DOMAIN][self._device['id']]['outside_temp'] = data['parameters']['temperatureOutside']
        else:
            self.hass.data[DOMAIN][self._device['id']]['outside_temp'] = None

        self._is_on =bool( data['parameters']['power'].value )
        self._hvac_mode = data['parameters']['mode'].name
        self._current_fan = data['parameters']['fanSpeed'].name
        try:
            self._airswing_hor = data['parameters']['airSwingHorizontal'].name
        except ValueError:
            self._airswing_hor = None

        self._airswing_vert = data['parameters']['airSwingVertical'].name
        self._eco = data['parameters']['eco'].name
        

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the optional state attributes with device specific additions."""
        attr = {}

        swing_horizontal = self._airswing_hor
        if swing_horizontal:
            attr.update(
                {
                    "swing_horizontal": swing_horizontal,
                    "swing_horizontal_positions": [f.name for f in self._constants.AirSwingLR ],
                }
            )
        return attr

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the display name of this climate."""
        return self._device['name']

    @property
    def group(self):
        """Return the display group of this climate."""
        return self._device['group']

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._target_temp

    @property
    def hvac_mode(self):
        """Return the current operation."""
        if not self._is_on:
            return HVAC_MODE_OFF

        for key, value in OPERATION_LIST.items():
            if value == self._hvac_mode:
                return key

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return list(OPERATION_LIST.keys())

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._current_fan

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return [f.name for f in self._constants.FanSpeed ]

    @property
    def swing_mode(self):
        """Return the fan setting."""
        return self._airswing_vert

    @property
    def swing_modes(self):
        """Return the list of available swing modes."""
        return [f.name for f in self._constants.AirSwingUD ]

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._cur_temp

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp.
        Requires SUPPORT_PRESET_MODE.
        """
        for key, value in PRESET_LIST.items():
            if value == self._eco:
                _LOGGER.debug("Preset mode is {0}".format(key))
                return key

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes.
        Requires SUPPORT_PRESET_MODE.
        """
        _LOGGER.debug("Preset modes are {0}".format(",".join(PRESET_LIST.keys())))
        return list(PRESET_LIST.keys())

    @api_call_login
    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        _LOGGER.debug("Set %s ecomode %s", self.name, preset_mode)
        self._api.set_device(
            self._device['id'],
            power = self._constants.Power.On,
            eco = self._constants.EcoMode[ PRESET_LIST[preset_mode] ]
        )


    @api_call_login
    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return

        _LOGGER.debug("Set %s temperature %s", self.name, target_temp)

        self._api.set_device(
            self._device['id'],
            temperature = target_temp
        )

    @api_call_login
    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        _LOGGER.debug("Set %s focus mode %s", self.name, fan_mode)

        self._api.set_device(
            self._device['id'],
            fanSpeed = self._constants.FanSpeed[fan_mode]
        )

    @api_call_login
    def set_hvac_mode(self, hvac_mode):
        """Set operation mode."""
        _LOGGER.debug("Set %s mode %s", self.name, hvac_mode)
        if hvac_mode == HVAC_MODE_OFF:
            self._api.set_device(
                self._device['id'],
                power = self._constants.Power.Off
            )
        else:

            self._api.set_device(
                self._device['id'],
                power = self._constants.Power.On,
                mode = self._constants.OperationMode[OPERATION_LIST[hvac_mode]]
            )

    @api_call_login
    def set_swing_mode(self, swing_mode):
        """Set swing mode."""
        _LOGGER.debug("Set %s swing mode %s", self.name, swing_mode)
        if swing_mode == 'Auto' and self._airswing_hor == 'Auto':
            automode = self._constants.AirSwingAutoMode["Both"]
        if swing_mode == 'Auto':
            automode = self._constants.AirSwingAutoMode["AirSwingUD"]
        else:
            automode = self._constants.AirSwingAutoMode["Disabled"]

        _LOGGER.debug(f"Set {self.name} swing_mode: {swing_mode} automode: {automode}")

        self._api.set_device(
            self._device['id'],
            power = self._constants.Power.On,
            airSwingVertical = self._constants.AirSwingUD[swing_mode],
            fanAutoMode = automode
        )

    @api_call_login
    def set_swing_horizontal(self, position: str) -> None:
        """Set horizontal swing position."""
        if swing_mode not in [f.name for f in self._constants.AirSwingLR ]:
            raise ValueError(
                f"Unsupported horizontal swing position {position}. Check the available modes from state attributes."
            )

        if swing_mode == 'Auto' and self._airswing_vert == 'Auto':
            automode = self._constants.AirSwingAutoMode["Both"]
        if swing_mode == 'Auto':
            automode = self._constants.AirSwingAutoMode["AirSwingLR"]
        else:
            automode = self._constants.AirSwingAutoMode["Disabled"]

        _LOGGER.debug(f"Set {self.name} swing_mode: {swing_mode} automode: {automode}")

        self._api.set_device(
            self._device['id'],
            airSwingHorizontal = self._constants.AirSwingLR[position],
            fanAutoMode = automode
        )

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 16

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 30

    @property
    def target_temp_step(self):
        """Return the temperature step."""
        return 0.5
