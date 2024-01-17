import logging
import secrets
import string
from dataclasses import dataclass
from typing import Self, Generic, TypeVar, Optional
import aiohttp

_LOGGER = logging.getLogger(__name__)


MODE_MAP = {"IDLE": "Idle", "COOK": "Cook", "LOW WATER": "Low water"}

STATE_MAP = {
    "PREHEATING": "Preheating",
    "COOKING": "Cooking",
    "MAINTAINING": "Maintaining",
    "": "No state",
}

P = TypeVar("P")


@dataclass
class APOSensor:
    @dataclass
    class Nodes:
        @dataclass
        class TemperatureBulbs:
            mode: str
            dosed: bool
            dose_failed: bool
            temperature: float
            target_temperature: float

        @dataclass
        class HeatingElement:
            watts: int
            on: bool

        @dataclass
        class SteamGenerator:
            mode: str
            relative_humidity: int
            target_humidity: int

        @dataclass
        class Cook:
            seconds_elapsed: int

        @dataclass
        class Timer:
            mode: str
            initial: int
            current: int

        cook: Cook
        timer: Timer | None
        temperature_bulbs: TemperatureBulbs
        steam_generator: SteamGenerator
        rear_heating: HeatingElement
        bottom_heating: HeatingElement
        top_heating: HeatingElement

        lamp_on: bool
        door_closed: bool
        water_tank_empty: bool
        fan_speed: int

    mode: str
    firmware_version: str
    nodes: Nodes | None = None


@dataclass
class APOState:
    sensor: APOSensor


class AnovaPrecisionOven:
    def __init__(self, cooker_id: str, type: str) -> None:
        self.cooker_id = cooker_id
        self.type = type
        self.state: APOState | None = None
        self.temperature_unit: str = "C"


# {
#     "stepType": "stage",
#     "id": "android-<uuid>",         # Or ios-<uuid>
#     "title": "First stage",         # The name of the stage (as set in the app)
#     "description": "",
#     "type": "preheat",
#     "userActionRequired": false,    # "false" if the stage starts automatically, "true" if it needs to be started manually
#     "temperatureBulbs": {
#         "dry": {                    # "dry" or "wet", depending on "mode"
#             "setpoint": {           # Set temperature, in both Fahrenheit and Celsius. Unknown which one takes precedence if they differ!
#                 "fahrenheit": 410,
#                 "celsius": 210
#             }
#         },
#         "mode": "dry"               # "sous-vide mode: on" == "mode: wet"; "sous-vide mode: off" == "mode: dry"
#     },
#     "heatingElements": {            # What heating elements are activated
#         "bottom": {
#         "on": false
#         },
#         "top": {
#         "on": false
#         },
#         "rear": {
#         "on": true
#         }
#     },
#     "fan": {                        # Fan speed
#         "speed": 100
#     },
#     "vent": {                       # Unknown
#         "open": false
#     },
#     "rackPosition": 3,              # Tray position
#     "timerAdded": true,
#     "timer": {                      # Only if "timerAdded": true
#         "initial": 600              # Timer in seconds
#     },
#     "probeAdded": false,            # Timer and probe cannot be added at the same time!
#     "temperatureProbe": {           # Only if "probeAdded": true
#         "setpoint": {
#             "fahrenheit": 97,       # Probe target temperature, in both Fahrenheit and Celsius. Unknown which one takes precedence if they differ!
#             "celsius": 36
#         }
#     }
# }

# {
#   "command": "CMD_APO_START",
#   "payload": {
#     "payload": {
#       "cookId": "android-<uuid>",  # Or ios-<uuid>
#       "stages": [
#         <stage_list>
#       ]
#     },
#     "type": "CMD_APO_START",
#     "id": "<your_oven_id>"
#   },
#   "requestId": "<uuid>"
# }

# {
#   "command": "CMD_APO_START",
#   "payload": {
#     "payload": {
#       "cook_id": "ios-22e7e3a7-f54e-40ee-8521-16cc5ddb86ed",
#       "stages": [
#         {
#           "id": "ios-79699629-6d83-4a5c-a688-0479edb9f32a",
#           "type": "preheat",
#           "temperature_bulbs": {
#             "dry": null,
#             "wet": {
#               "fahrenheit": 203,
#               "celsius": 95
#             }
#           },
#           "heating_elements": {
#             "bottom": {
#               "on": false
#             },
#             "top": {
#               "on": false
#             },
#             "rear": {
#               "on": true
#             }
#           },
#           "rack_position": 3,
#           "fan": {
#             "speed": 100
#           },
#           "vent": {
#             "open": false
#           },
#           "step_type": "stage",
#           "title": "",
#           "description": "",
#           "user_action_requiered": false,
#           "timer_added": false,
#           "timer": null,
#           "probe_added": false,
#           "temperature_probe": null
#         }
#       ]
#     },
#     "type": "CMD_APO_START",
#     "id": "0123673966ef4e7601"
#   },
#   "request_id": "efbe4d37-8b09-48a4-8ebd-e195ad89b289"
# }


@dataclass
class APOStage:
    @dataclass
    class TemperatureSetpoint:
        fahrenheit: int
        celsius: int

    @dataclass
    class TemperatureBulb:
        setpoint: "APOStage.TemperatureSetpoint"

    @dataclass
    class TemperatureBulbs:
        mode: str
        dry: Optional["APOStage.TemperatureBulb"] = None
        wet: Optional["APOStage.TemperatureBulb"] = None

    @dataclass
    class On:
        on: bool

    @dataclass
    class HeatingElements:
        bottom: "APOStage.On"
        top: "APOStage.On"
        rear: "APOStage.On"

    @dataclass(frozen=True)
    class Fan:
        speed: int

    @dataclass(frozen=True)
    class Vent:
        open: bool

    @dataclass(frozen=True)
    class Timer:
        initial: int

    @dataclass(frozen=True)
    class Probe:
        setpoint: Optional["APOStage.TemperatureSetpoint"] = None

    @dataclass(frozen=True)
    class SteamGenerators:
        @dataclass(frozen=True)
        class Setpoint:
            setpoint: int

        mode: str
        relative_humidity: Setpoint

    step_type: str
    id: str
    title: str
    description: str
    type: str
    user_action_required: bool
    temperature_bulbs: TemperatureBulbs
    heating_elements: HeatingElements
    fan: Fan
    vent: Vent
    rack_position: int
    steam_generators: SteamGenerators
    timer_added: bool = False
    timer: Timer | None = None
    probe_added: bool = False
    temperature_probe: Probe | None = None


@dataclass
class APOCommand(Generic[P]):
    @dataclass
    class Payload(Generic[P]):
        payload: P | None
        type: str
        id: str

    @dataclass
    class APOStartPayload:
        cook_id: str
        stages: list[APOStage]

    command: str
    request_id: str
    payload: Payload[P]
