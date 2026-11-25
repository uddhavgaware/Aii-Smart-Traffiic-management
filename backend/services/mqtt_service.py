"""
MQTT Service for authenticated TLS communication with the ESP32 signal controller.
Runs paho-mqtt loop on a background thread and bridges callbacks to asyncio.
"""

from __future__ import annotations

import asyncio
import json
import ssl
import time
from typing import Any, Callable, Coroutine, Optional

import paho.mqtt.client as mqtt

from core.config import settings
from core.logging import get_logger
from core.redis_client import KEY_ESP32_STATUS, cache_set

logger = get_logger(__name__)


class MQTTService:
    """Handles ESP32 signal command publishing, ACK verification, and heartbeat tracking."""

    def __init__(self) -> None:
        self._client: Optional[mqtt.Client] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.connected: bool = False
        self.esp32_online: bool = False
        self.last_heartbeat: Optional[float] = None
        self.last_command_ts: Optional[float] = None
        self.last_ack_seq: Optional[int] = None
        self.last_error: Optional[str] = None
        self.wifi_rssi: Optional[int] = None
        self._on_status_callback: Optional[Callable[[dict[str, Any]], Coroutine[Any, Any, None]]] = None

    def set_status_callback(
        self, cb: Callable[[dict[str, Any]], Coroutine[Any, Any, None]]
    ) -> None:
        self._on_status_callback = cb

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """Connect to MQTT broker in background network loop."""
        self._loop = loop
        try:
            self._client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"backend_{settings.JUNCTION_ID}",
                protocol=mqtt.MQTTv311,
            )
        except AttributeError:
            self._client = mqtt.Client(client_id=f"backend_{settings.JUNCTION_ID}")

        if settings.MQTT_USERNAME:
            self._client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)

        if settings.MQTT_USE_TLS:
            try:
                self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
            except Exception as exc:
                logger.warning("mqtt_tls_setup_warning", error=str(exc))

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.reconnect_delay_set(min_delay=2, max_delay=30)

        try:
            self._client.connect_async(settings.MQTT_BROKER, settings.MQTT_PORT, settings.MQTT_KEEPALIVE)
            self._client.loop_start()
            logger.info("mqtt_client_started", broker=settings.MQTT_BROKER, port=settings.MQTT_PORT)
        except Exception as exc:
            self.last_error = str(exc)
            logger.warning("mqtt_connect_deferred", error=str(exc))

    def stop(self) -> None:
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
        self.connected = False
        logger.info("mqtt_client_stopped")

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, *args: Any) -> None:
        rc = getattr(reason_code, "value", reason_code)
        if rc == 0:
            self.connected = True
            self.last_error = None
            client.subscribe(settings.mqtt_signal_ack_topic, qos=settings.MQTT_QOS)
            client.subscribe(settings.mqtt_status_topic, qos=settings.MQTT_QOS)
            client.subscribe(settings.mqtt_error_topic, qos=settings.MQTT_QOS)
            logger.info("mqtt_connected_subscribed", prefix=settings.MQTT_TOPIC_PREFIX)
        else:
            self.connected = False
            self.last_error = f"Connect failed code={rc}"
            logger.error("mqtt_connect_failed", code=rc)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, *args: Any) -> None:
        self.connected = False
        logger.warning("mqtt_disconnected")

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        try:
            data = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            logger.warning("mqtt_invalid_json", topic=msg.topic)
            return

        now = time.time()
        if msg.topic == settings.mqtt_signal_ack_topic:
            self.last_ack_seq = data.get("sequence_id")
            if not data.get("ack", True):
                self.last_error = data.get("error", "Command rejected by ESP32")
            else:
                self.last_error = None
            self.esp32_online = True
            self.last_heartbeat = now

        elif msg.topic == settings.mqtt_status_topic:
            state = data.get("state", "online")
            self.esp32_online = state == "online"
            self.wifi_rssi = data.get("wifi_rssi")
            self.last_heartbeat = now if self.esp32_online else self.last_heartbeat

        elif msg.topic == settings.mqtt_error_topic:
            self.last_error = data.get("error", "Unknown ESP32 error")
            logger.error("esp32_error_reported", error=self.last_error)

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._persist_and_notify(), self._loop)

    async def _persist_and_notify(self) -> None:
        status_payload = self.get_status()
        await cache_set(KEY_ESP32_STATUS, status_payload, ttl=120)
        if self._on_status_callback:
            await self._on_status_callback(status_payload)

    async def publish_signal_command(self, command_dict: dict[str, Any]) -> bool:
        """Publish validated signal command to ESP32 via MQTT."""
        self.last_command_ts = time.time()
        if not self._client or not self.connected:
            logger.debug("mqtt_not_connected_skipping_publish", seq=command_dict.get("sequence_id"))
            return False
        try:
            payload = json.dumps(command_dict)
            info = self._client.publish(
                settings.mqtt_signal_command_topic,
                payload,
                qos=settings.MQTT_QOS,
            )
            return info.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as exc:
            self.last_error = str(exc)
            logger.error("mqtt_publish_failed", error=str(exc))
            return False

    async def publish_raw_command(self, subtopic: str, payload: dict[str, Any]) -> bool:
        if not self._client or not self.connected:
            return False
        topic = f"{settings.MQTT_TOPIC_PREFIX}/{subtopic}"
        info = self._client.publish(topic, json.dumps(payload), qos=settings.MQTT_QOS)
        return info.rc == mqtt.MQTT_ERR_SUCCESS

    def get_status(self) -> dict[str, Any]:
        # Mark offline if heartbeat older than 30s
        if self.last_heartbeat and (time.time() - self.last_heartbeat) > 30.0:
            self.esp32_online = False
        return {
            "connected": self.esp32_online,
            "mqtt_connected": self.connected,
            "last_heartbeat": self.last_heartbeat,
            "last_command_ts": self.last_command_ts * 1000 if self.last_command_ts else None,
            "last_ack_seq": self.last_ack_seq,
            "error": self.last_error,
            "wifi_rssi": self.wifi_rssi,
        }


mqtt_service = MQTTService()
