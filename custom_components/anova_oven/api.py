import asyncio
import json
import logging
import time
from abc import ABC

import aiohttp
from aiohttp.client_ws import ClientWebSocketResponse

from .const import PLATFORM, AnovaUnitOfTemperature
from .exceptions import CommandError, InvalidAuth, NoDevicesFound
from .precision_oven import (
    AnovaPrecisionOven,
    APOCommand,
    APOSensor,
    APOState,
    ProbeTarget,
    Target,
    Temperature,
    TimerTarget,
)
from .util import dict_keys_to_camel_case, snake_case_to_camel_case, to_dict

_LOGGER = logging.getLogger(__name__)


class AnovaOvenApi:
    """A class to handle communicating with the anova api to get devices"""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        app_key: str,
        access_token: str,
        refresh_token: str,
        existing_devices: list[AnovaPrecisionOven] | None = None,
        unit_of_temperature: AnovaUnitOfTemperature = AnovaUnitOfTemperature.CELSIUS,
    ) -> None:
        """Creates an anova api class"""
        self.devices = {d.cooker_id: d for d in existing_devices or []}
        self.session: aiohttp.ClientSession = session
        self.app_key: str = app_key
        self.access_token: str = access_token
        self.refresh_token: str = refresh_token
        self._shold_stop = False
        self._listeners: list[AnovaOvenUpdateListener] = []
        self._ws: ClientWebSocketResponse | None = None
        self._response_fut: asyncio.Future | None
        self.unit_of_temperature = unit_of_temperature

    def add_listener(self, listener: "AnovaOvenUpdateListener"):
        self._listeners.append(listener)

    async def run(self):
        self._shold_stop = False

        attempt = 0

        while not self._shold_stop:
            url = f"https://devices.anovaculinary.io/?token={self.access_token}&supportedAccessories=APO&platform={PLATFORM}"
            headers = {
                "Sec-WebSocket-Protocol": "ANOVA_V2",
                "Sec-WebSocket-Version": "13",
            }
            async with self.session.ws_connect(url, headers=headers) as ws:
                self._ws = ws
                target: Target = None
                async for msg in ws:
                    attempt = 0
                    if self._shold_stop:
                        break
                    try:
                        _LOGGER.debug("Found message %s", msg)
                        match msg.type:
                            case aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                match data.get("command"):
                                    case "EVENT_APO_STATE":
                                        payload = data["payload"]
                                        state = payload["state"]
                                        nodes = state["nodes"]
                                        bulbs = nodes["temperatureBulbs"]
                                        he = nodes["heatingElements"]
                                        sg = nodes["steamGenerators"]
                                        hum = (
                                            sg["relativeHumidity"]
                                            if sg["mode"] == "idle"
                                            else sg[
                                                snake_case_to_camel_case(sg["mode"])
                                            ]
                                        )
                                        cook = state.get("cook", {})
                                        timer = nodes.get("timer", {})
                                        tp = nodes.get("temperatureProbe")
                                        raw_stages = json.dumps(cook.get("stages", []))

                                        active_stage_index = None
                                        for idx, s in enumerate(
                                            (s for s in cook.get("stages", [])), start=1
                                        ):
                                            if s["id"] == cook.get("activeStageId"):
                                                active_stage_index = idx
                                                break
                                        state = APOState(
                                            sensor=APOSensor(
                                                mode=state["state"]["mode"],
                                                firmware_version=state["systemInfo"][
                                                    "firmwareVersion"
                                                ],
                                                nodes=APOSensor.Nodes(
                                                    cook=APOSensor.Nodes.Cook(
                                                        seconds_elapsed=cook.get(
                                                            "secondsElapsed", 0
                                                        )
                                                    ),
                                                    temperature_probe=APOSensor.Nodes.TemperatureProbe(
                                                        temperature=Temperature(
                                                            celsius=tp["current"][
                                                                "celsius"
                                                            ],
                                                            fahrenheit=tp["current"][
                                                                "fahrenheit"
                                                            ],
                                                        )
                                                        if "current" in tp
                                                        else None,
                                                        target_temperature=Temperature(
                                                            celsius=tp["setpoint"][
                                                                "celsius"
                                                            ],
                                                            fahrenheit=tp["setpoint"][
                                                                "fahrenheit"
                                                            ],
                                                        )
                                                        if "setpoint" in tp
                                                        else None,
                                                    )
                                                    if tp
                                                    else None,
                                                    temperature_bulbs=APOSensor.Nodes.TemperatureBulbs(
                                                        mode=bulbs["mode"],
                                                        temperature=Temperature(
                                                            celsius=bulbs[
                                                                bulbs["mode"]
                                                            ]["current"]["celsius"],
                                                            fahrenheit=bulbs[
                                                                bulbs["mode"]
                                                            ]["current"]["fahrenheit"],
                                                        ),
                                                        target_temperature=Temperature(
                                                            celsius=bulbs[
                                                                bulbs["mode"]
                                                            ]["setpoint"]["celsius"],
                                                            fahrenheit=bulbs[
                                                                bulbs["mode"]
                                                            ]["setpoint"]["fahrenheit"],
                                                        ),
                                                        dosed=bulbs["wet"]["dosed"],
                                                        dose_failed=bulbs["wet"][
                                                            "doseFailed"
                                                        ],
                                                    ),
                                                    rear_heating=APOSensor.Nodes.HeatingElement(
                                                        watts=he["rear"]["watts"],
                                                        on=he["rear"]["on"],
                                                    ),
                                                    bottom_heating=APOSensor.Nodes.HeatingElement(
                                                        watts=he["bottom"]["watts"],
                                                        on=he["bottom"]["on"],
                                                    ),
                                                    top_heating=APOSensor.Nodes.HeatingElement(
                                                        watts=he["top"]["watts"],
                                                        on=he["top"]["on"],
                                                    ),
                                                    steam_generator=APOSensor.Nodes.SteamGenerator(
                                                        mode=sg["mode"],
                                                        relative_humidity=hum.get(
                                                            "current"
                                                        ),
                                                        target_humidity=hum.get(
                                                            "setpoint", 0
                                                        ),
                                                    ),
                                                    timer=APOSensor.Nodes.Timer(
                                                        mode=timer.get("mode"),
                                                        initial=timer.get("initial"),
                                                        current=timer.get("current"),
                                                    ),
                                                    lamp_on=nodes["lamp"]["on"],
                                                    door_closed=nodes["door"]["closed"],
                                                    water_tank_empty=nodes["waterTank"][
                                                        "empty"
                                                    ],
                                                    fan_speed=nodes["fan"]["speed"],
                                                ),
                                            ),
                                            stages=APOState.Stages(
                                                active=active_stage_index,
                                                count=len(cook.get("stages", [])),
                                            ),
                                            raw_stages=raw_stages,
                                        )
                                        device_id = payload["cookerId"]
                                        device = self.devices[device_id]
                                        device.state = state
                                        for listener in self._listeners:
                                            await listener.on_state(device, state)

                                        current_target: Target | None = None
                                        if (
                                            state.sensor.nodes.temperature_probe
                                            and state.sensor.nodes.temperature_probe.target_temperature
                                        ):
                                            current_target = ProbeTarget(
                                                temperature=state.sensor.nodes.temperature_probe.temperature,
                                                target_temperature=state.sensor.nodes.temperature_probe.target_temperature,
                                            )
                                        elif (
                                            state.sensor.nodes.timer
                                            and state.sensor.nodes.timer.initial
                                        ):
                                            current_target = TimerTarget(
                                                current=state.sensor.nodes.timer.current,
                                                initial=state.sensor.nodes.timer.initial,
                                            )
                                        if target != current_target and (
                                            (current_target and current_target.reached)
                                            or current_target is None
                                        ):
                                            for listener in self._listeners:
                                                await listener.on_target_reached(
                                                    device, target
                                                )
                                        target = current_target
                                    case "EVENT_APO_WIFI_LIST":
                                        payload = data.get("payload")
                                        new_devices: list[tuple[str, str]] = [
                                            (d["cookerId"], d["type"])
                                            for d in payload
                                            if d["cookerId"] not in self.devices
                                        ]
                                        for device in new_devices:
                                            _LOGGER.debug("Found device %s", device[0])
                                            oven = AnovaPrecisionOven(
                                                cooker_id=device[0],
                                                type=device[1],
                                            )
                                            self.devices[device[0]] = oven
                                            for listener in self._listeners:
                                                await listener.on_new_device(oven)

                                    case "RESPONSE":
                                        if self._response_fut:
                                            payload = data.get("payload")
                                            self._response_fut.set_result(payload)
                                    case _:
                                        pass
                            case aiohttp.WSMsgType.CLOSE:
                                break
                            case aiohttp.WSMsgType.ERROR:
                                break
                            case _:
                                _LOGGER.debug(f"Unknown message type: {msg}")
                        await asyncio.sleep(0)
                    except Exception as err:
                        _LOGGER.exception("Failed processing msg {msg}: {err}")
                        self._ws = None
                        raise err
            _LOGGER.info("WS stream closed.")
            if attempt > 0:
                raise InvalidAuth("Access Token invalid")

            if not self._shold_stop:
                await self.renew_token()
                await asyncio.sleep(1)
            attempt += 1
        self._ws = None

    async def stop(self):
        self._shold_stop = True
        if self._ws:
            await self._ws.close()

    async def renew_token(self):
        url = f"https://securetoken.googleapis.com/v1/token?key={self.app_key}"
        data = {"grant_type": "refresh_token", "refresh_token": self.refresh_token}
        try:
            async with self.session.post(url, data=data) as resp:
                res = await resp.json()
                if "error" in res:
                    raise InvalidAuth(res)
                self.access_token = res["access_token"]
                self.refresh_token = res["refresh_token"]

                _LOGGER.info("Token refreshed.")

                for listener in self._listeners:
                    await listener.on_new_token(self.access_token, self.refresh_token)
        except Exception as err:
            _LOGGER.exception(f"Failed renew token: {err}")
            raise InvalidAuth("Access Token invalid")

    async def get_devices(self) -> list[AnovaPrecisionOven]:
        timeout = time.time() + 5.5  # 5 seconds from now
        while time.time() < timeout:
            if self.devices:
                return list(self.devices.values())
            await asyncio.sleep(1)
        raise NoDevicesFound("Found no devices on the websocket")

    async def send_command(self, command: APOCommand):
        if self._ws:
            data = dict_keys_to_camel_case(to_dict(command))
            _LOGGER.info(json.dumps(data))
            self._response_fut = asyncio.Future()
            await self._ws.send_json(data)
            try:
                res = await asyncio.wait_for(self._response_fut, timeout=10)
            finally:
                self._response_fut = None
            if res and res.get("status") == "error":
                raise CommandError(res.get("error", "Unknown error"))


class AnovaOvenUpdateListener(ABC):
    async def on_state(self, device: AnovaPrecisionOven, state: APOState):
        pass

    async def on_new_device(self, device: AnovaPrecisionOven):
        pass

    async def on_new_token(self, access_token: str, refresh_token: str):
        pass

    async def on_target_reached(self, device: AnovaPrecisionOven, target: Target):
        pass
