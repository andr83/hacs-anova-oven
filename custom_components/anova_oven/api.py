import asyncio
import json
import logging
import time
import typing
from typing import Tuple

import aiohttp
from abc import ABC, abstractmethod

from aiohttp.client_ws import ClientWebSocketResponse

from dataclasses import dataclass, asdict

from .precision_oven import (
    AnovaPrecisionOven,
    APOState,
    APOSensor,
    APOCommand,
    APOStage,
)
from .const import PLATFORM
from .exceptions import CommandError, NoDevicesFound, InvalidAuth
from .util import snake_case_to_camel_case, dict_keys_to_camel_case, to_dict


_LOGGER = logging.getLogger(__name__)

# Found here - https://github.com/ammarzuberi/pyanova-api/blob/master/anova/AnovaCooker.py and personally confirmed.
ANOVA_FIREBASE_KEY = "AIzaSyDQiOP2fTR9zvFcag2kSbcmG9zPh6gZhHw"


class AnovaOvenApi:
    """A class to handle communicating with the anova api to get devices"""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        app_key: str,
        access_token: str,
        refresh_token: str,
        existing_devices: list[AnovaPrecisionOven] | None = None,
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
                # "Sec-WebSocket-Key": "SeGqdmsI2a91XilH9/lu1w=="
            }
            async with self.session.ws_connect(url, headers=headers) as ws:
                self._ws = ws
                async for msg in ws:
                    attempt = 0
                    if self._shold_stop:
                        break
                    try:
                        _LOGGER.info("Found message %s", msg)
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
                                                    temperature_bulbs=APOSensor.Nodes.TemperatureBulbs(
                                                        mode=bulbs["mode"],
                                                        temperature=bulbs[
                                                            bulbs["mode"]
                                                        ]["current"]["celsius"],
                                                        target_temperature=bulbs[
                                                            bulbs["mode"]
                                                        ]["setpoint"]["celsius"],
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
                                            )
                                        )
                                        device_id = payload["cookerId"]
                                        device = self.devices[device_id]
                                        device.state = state
                                        for l in self._listeners:
                                            await l.on_state(device, state)

                                    case "EVENT_APO_WIFI_LIST":
                                        payload = data.get("payload")
                                        new_devices: typing.List[Tuple[str, str]] = [
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
                                            for l in self._listeners:
                                                await l.on_new_device(oven)

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
                                _LOGGER.info(f"Unknown message type: {msg}")
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

                for l in self._listeners:
                    await l.on_new_token(self.access_token, self.refresh_token)
        except Exception as err:
            _LOGGER.exception("Failed renew token: {err}")
            raise InvalidAuth("Access Token invalid")

    async def get_devices(self) -> typing.List[AnovaPrecisionOven]:
        timeout = time.time() + 5.5  # 5 seconds from now
        while time.time() < timeout:
            if self.devices:
                return list(self.devices.values())
            await asyncio.sleep(1)
        raise NoDevicesFound("Found no devices on the websocket")

    async def send_command(self, command: APOCommand):
        if self._ws:
            data = dict_keys_to_camel_case(to_dict(command))
            logging.info(json.dumps(data))
            self._response_fut = asyncio.Future()
            await self._ws.send_json(data)
            try:
                res = await asyncio.wait_for(self._response_fut, timeout=10)
            finally:
                self._response_fut = None
            if res and res.get("status") == "error":
                raise CommandError(res.get("error", "Unknown error"))


class AnovaOvenUpdateListener(ABC):
    async def on_state(device: AnovaPrecisionOven, state: APOState):
        pass

    async def on_new_device(device: AnovaPrecisionOven):
        pass

    async def on_new_token(access_token: str, refresh_token: str):
        pass
