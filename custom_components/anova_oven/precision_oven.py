import logging
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

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
class Temperature:
    celsius: float
    fahrenheit: float


@dataclass
class APOSensor:
    @dataclass
    class Nodes:
        @dataclass
        class TemperatureBulbs:
            mode: str
            dosed: bool
            dose_failed: bool
            temperature: Temperature
            target_temperature: Temperature

        @dataclass
        class TemperatureProbe:
            temperature: Temperature
            target_temperature: Temperature

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
        temperature_probe: TemperatureProbe
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
    @dataclass
    class Stages:
        active: int
        count: int

    sensor: APOSensor
    stages: Stages
    raw_stages: str


class Target:
    @property
    def reached(self) -> bool:
        pass


@dataclass
class ProbeTarget(Target):
    temperature: Temperature
    target_temperature: Temperature

    @property
    def reached(self) -> bool:
        return (
            self.temperature
            and self.target_temperature
            and self.temperature.celsius >= self.target_temperature.celsius
        )


@dataclass
class TimerTarget(Target):
    initial: int
    current: int

    @property
    def reached(self) -> bool:
        return self.current and self.initial and self.current >= self.initial


class AnovaPrecisionOven:
    def __init__(self, cooker_id: str, type: str) -> None:
        self.cooker_id = cooker_id
        self.type = type
        self.state: APOState | None = None
        self.temperature_unit: str = "C"


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
        steam_percentage: Setpoint

    id: str
    title: str
    type: str
    temperature_bulbs: TemperatureBulbs
    heating_elements: HeatingElements
    fan: Fan
    vent: Vent
    step_type: str = "stage"
    description: str = ""
    user_action_required: bool = False
    rack_position: int = 3
    steam_generators: SteamGenerators | None = None
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
