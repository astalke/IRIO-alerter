from typing import Optional
import asyncio
import httpx
from httpx import TimeoutException
from pydantic import BaseModel

from monitor_service.types import MonitorId, MonitoredServiceInfo
from .alerter import Alerter
from .utils import get_time, time_difference_in_ms


class ServiceMonitorConfiguration(BaseModel):
    monitor_id: MonitorId


class ServiceMonitor:
    config: ServiceMonitorConfiguration
    info: MonitoredServiceInfo
    _alerter: Alerter
    last_response_time: Optional[float]

    def __init__(
        self,
        config: ServiceMonitorConfiguration,
        info: MonitoredServiceInfo,
        *,
        alerter: Alerter
    ):
        self.config = config
        self.info = info
        self.last_response_time = None
        self._alerter = alerter

    async def monitor(self):
        self.last_response_time = get_time()  # fake first response time

        sleep_time = self.info.frequency

        while True:
            await asyncio.gather(
                self._check_service_heartbeat(), asyncio.sleep(sleep_time)
            )

    async def _check_service_heartbeat(self):
        """

        Should finish in time < monitoring frequency #TODO: add metric
        """
        timeout = self.info.frequency / 2000  # TODO: set sensible timeout
        async with httpx.AsyncClient() as client:
            try:
                r = await client.get(self.info.url, timeout=timeout)
                self.last_response_time = get_time()
            except TimeoutException:
                should_send = self._should_send_alert()
                if should_send:
                    await self._send_alert()

    def _should_send_alert(self) -> bool:
        current_time = get_time()
        time_since_last_response = time_difference_in_ms(
            self.last_response_time, current_time
        )
        return time_since_last_response > self.info.alertingWindow

    async def _send_alert(self):
        await self._alerter.send_alert()
