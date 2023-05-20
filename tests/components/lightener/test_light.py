"""Tests for the light platform"""

from unittest.mock import ANY, Mock, patch
from uuid import uuid4

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lightener.light import (
    LightenerLight,
    LightenerControlledLight,
    DOMAIN,
    _convert_percent_to_brightness,
    async_setup_platform,
)

###########################################################
### LightenerLight class only tests


async def test_lightener_light_properties(hass):
    """Test all the basic properties of the LightenerLight class"""

    config = {"friendly_name": "Living Room"}
    unique_id = str(uuid4())

    lightener = LightenerLight(config, unique_id)

    assert lightener.unique_id == unique_id

    # Name must be empty so it'll be taken from the device
    assert lightener.name is None
    assert lightener.device_info["name"] == "Living Room"

    assert lightener.should_poll is False
    assert lightener.has_entity_name is True

    assert lightener.icon == "mdi:lightbulb-group"


async def test_lightener_light_properties_no_unique_id(hass):
    """Test all the basic properties of the LightenerLight class when no unique id is provided"""

    config = {"friendly_name": "Living Room"}

    lightener = LightenerLight(config)

    assert lightener.unique_id is None
    assert lightener.device_info is None
    assert lightener.name == "Living Room"


async def test_lightener_light_turn_on(hass: HomeAssistant, create_lightener):
    """Test the state changes of the LightenerLight class when turned on"""

    lightener: LightenerLight = await create_lightener(config={
            "friendly_name": "Test",
            "entities": {
                "light.test1": {},
                "light.test2": {},
            }
        }
    )

    with patch.object(hass.services, "async_call") as async_call_mock:
        await lightener.async_turn_on()

    assert async_call_mock.call_count == 2

    async_call_mock.assert_any_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test1"},
        blocking=False,
        context=ANY,
    )

    async_call_mock.assert_any_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test2"},
        blocking=False,
        context=ANY,
    )

async def test_lightener_light_turn_on_forward(hass: HomeAssistant, create_lightener):
    """Test if passed arguments are forwared when turned on"""

    lightener: LightenerLight = await create_lightener()

    with patch.object(hass.services, "async_call") as async_call_mock:
        await lightener.async_turn_on(
            brightness=50,
            effect="blink",
            color_temp_kelvin=3000
        )

    async_call_mock.assert_called_once_with(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test1",
            'brightness': 50,
            'effect': 'blink',
            'color_temp_kelvin': 3000,
        },
        blocking=False,
        context=ANY,
    )

async def test_lightener_light_turn_on_go_off_if_brightness_0(hass: HomeAssistant, create_lightener):
    """Test that turned on sends brightness 0 if the controlled light is on"""

    lightener: LightenerLight = await create_lightener(config={
        "friendly_name": "Test",
        "entities": {
            "light.test1": {
                "50": "0"
            }
        },
    })

    hass.states.async_set(entity_id="light.test1", new_state="on")

    with patch.object(hass.services, "async_call") as async_call_mock:
        await lightener.async_turn_on(brightness=1)

    async_call_mock.assert_called_once_with(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test1",
            'brightness': 0,
        },
        blocking=False,
        context=ANY,
    )

async def test_lightener_light_async_update_group_state(hass: HomeAssistant, create_lightener):
    """Test that turned on does nothing if the controlled light is already off"""

    lightener: LightenerLight = await create_lightener(config={
        "friendly_name": "Test",
        "entities": {
            "light.test1": {
                "50": "0"
            }
        },
    })

    lightener._attr_brightness = 150    # pylint: disable=protected-access

    hass.states.async_set(entity_id="light.test1", new_state="on",
        attributes={
            'color_temp_kelvin': 3000
        })

    lightener.async_update_group_state()

    assert lightener.is_on is True
    assert lightener.color_temp_kelvin == 3000

    assert lightener.brightness == 150

    hass.states.async_set(entity_id="light.test1", new_state="on",
        attributes={
            'brightness': 255
        })

    lightener.async_update_group_state()

    assert lightener.brightness == 255

    hass.states.async_set(entity_id="light.test1", new_state="on",
        attributes={
            'brightness': 1
        })

    lightener.async_update_group_state()

    assert lightener.brightness == 129

    hass.states.async_set(entity_id="light.test1", new_state="on",
        attributes={
            'brightness': 0
        })

    lightener.async_update_group_state()

    assert lightener.is_on is True
    assert lightener.brightness == 1

async def test_lightener_light_async_update_group_state_zero(hass: HomeAssistant, create_lightener):
    """Test that turned on does nothing if the controlled light is already off"""

    lightener: LightenerLight = await create_lightener(config={
        "friendly_name": "Test",
        "entities": {
            "light.test1": {}
        },
    })

    lightener._attr_brightness = 150    # pylint: disable=protected-access

    hass.states.async_set(entity_id="light.test1", new_state="on",
        attributes={
            'brightness': 0
        })

    lightener.async_update_group_state()

    assert lightener.brightness == 0

async def test_lightener_light_async_update_group_state_unavailable(hass: HomeAssistant, create_lightener):
    """Test that turned on does nothing if the controlled light is already off"""

    lightener: LightenerLight = await create_lightener(config={
        "friendly_name": "Test",
        "entities": {
            "light.test1": {"50": "0"},
            "light.I_DONT_EXIST": {}
        },
    })

    lightener._attr_brightness = 150    # pylint: disable=protected-access

    hass.states.async_set(entity_id="light.test1", new_state="on",
        attributes={
            'brightness': 1
        })

    lightener.async_update_group_state()

    assert lightener.brightness == 129

async def test_lightener_light_async_update_group_state_no_match_no_change(hass: HomeAssistant, create_lightener):
    """Test that turned on does nothing if the controlled light is already off"""

    lightener: LightenerLight = await create_lightener(config={
        "friendly_name": "Test",
        "entities": {
            "light.test1": {"50": "0"},
            "light.test2": {"10": "100"}
        },
    })

    def test(test1: int, test2: int, result: int):
        lightener._attr_brightness = 150    # pylint: disable=protected-access

        hass.states.async_set(entity_id="light.test1", new_state="on",
            attributes={'brightness': test1})

        hass.states.async_set(entity_id="light.test2", new_state="on",
            attributes={'brightness': test2})

        lightener.async_update_group_state()

        assert lightener.brightness == result

    # Matches
    test(0, 26, 3)
    test(1, 255, 129)

    # No matches
    test(129, 1, 150)
    test(1, 254, 150)
    test(1, 1, 150)
    test(1, None, 150)

###########################################################
### LightenerControlledLight class only tests

async def test_lightener_light_entity_properties(hass):
    """Test all the basic properties of the LightenerLight class"""

    light = LightenerControlledLight(
        "light.test1", {"brightness": {"10": "20"}}
    )

    assert light.entity_id == "light.test1"

async def test_lightener_light_entity_calculated_levels(hass):
    """Test the calculation of brigthness levels"""

    light = LightenerControlledLight(
        "light.test1",
        {
            "brightness": {
                "10": "100",
            }
        },
    )

    assert light.levels[0] == 0
    assert light.levels[13] == 128
    assert light.levels[25] == 246
    assert light.levels[26] == 255
    assert light.levels[27] == 255
    assert light.levels[100] == 255
    assert light.levels[255] == 255

    light = LightenerControlledLight(
        "light.test1",
        {
            "brightness": {
                "100": "0",  # Test the ordering
                "10": "10",
                "50": "100",
            }
        },
    )

    assert light.levels[0] == 0
    assert light.levels[15] == 15
    assert light.levels[26] == 26
    assert light.levels[27] == 29
    assert light.levels[128] == 255
    assert light.levels[129] == 253
    assert light.levels[255] == 0

async def test_lightener_light_entity_calculated_to_lightner_levels(hass):
    """Test the calculation of brigthness levels"""

    light = LightenerControlledLight(
        "light.test1",
        {
            "brightness": {
                "10": "100" # 26: 255
            }
        },
    )

    assert light.to_lightener_levels[0] == [0]
    assert light.to_lightener_levels[26] == [3]
    assert light.to_lightener_levels[253] == [26]
    assert light.to_lightener_levels[254] == [26]
    assert light.to_lightener_levels[255] == list(range(26,256))


    light = LightenerControlledLight(
        "light.test1",
        {
            "brightness": {
                "100": "0",  # Test the ordering
                "10": "10",
                "50": "100",
            }
        },
    )

    assert light.to_lightener_levels[0] == [0,255]
    assert light.to_lightener_levels[26] == [26,243]
    assert light.to_lightener_levels[255] == [128]

    assert light.to_lightener_levels[3] == [3,254]
    assert light.to_lightener_levels[10] == [10, 251]

async def test_lightener_light_entity_translate_brightness_float(hass):
    """Test translate_brightness_back with float values"""

    light = LightenerControlledLight(
        "light.test1",
        {
            "brightness": {
                "10": "100" # 26: 255
            }
        },
    )

    assert light.translate_brightness(2.9) == 20

async def test_lightener_light_entity_translate_brightness_back_float(hass):
    """Test translate_brightness_back with float values"""

    light = LightenerControlledLight(
        "light.test1",
        {
            "brightness": {
                "10": "100" # 26: 255
            }
        },
    )

    assert light.translate_brightness_back(25.9) == [3]

###########################################################
### Other


def test_convert_percent_to_brightness():
    """Test the _convert_percent_to_brightness function"""

    assert _convert_percent_to_brightness(0) == 0
    assert _convert_percent_to_brightness(10) == 26
    assert _convert_percent_to_brightness(100) == 255


async def test_async_setup_platform(hass):
    """Test for platform setup"""

    # pylint: disable=W0212

    async_add_entities_mock = Mock()

    config = {
        "platform": "lightener",
        "lights": {
            "lightener_1": {
                "friendly_name": "Lightener 1",
                "entities": {"light.test1": {10: 100}},
            },
            "lightener_2": {
                "friendly_name": "Lightener 2",
                "entities": {"light.test2": {100: 10}},
            },
        },
    }

    await async_setup_platform(hass, config, async_add_entities_mock)

    assert async_add_entities_mock.call_count == 1

    created_lights: list = async_add_entities_mock.call_args.args[0]

    assert len(created_lights) == 2

    light: LightenerLight = created_lights[0]

    assert isinstance(light, LightenerLight)
    assert light.name == "Lightener 1"
    assert len(light._entities) == 1

    controlled_light: LightenerControlledLight = light._entities[0]

    assert isinstance(controlled_light, LightenerControlledLight)
    assert controlled_light.entity_id == "light.test1"
    assert controlled_light.levels[26] == 255

    light: LightenerLight = created_lights[1]

    assert isinstance(light, LightenerLight)
    assert light.name == "Lightener 2"
    assert len(light._entities) == 1

    controlled_light: LightenerControlledLight = light._entities[0]

    assert isinstance(controlled_light, LightenerControlledLight)
    assert light.extra_state_attributes["entity_id"][0] == "light.test2"
    assert controlled_light.entity_id == "light.test2"
    assert controlled_light.levels[255] == 26
