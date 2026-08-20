"""gRPC client for Polestar Connected Car Services (PCCS).

This module communicates with the Volvo/Polestar gRPC API (cnepmob.volvocars.com)
to retrieve data not available through the GraphQL API, including:
- Charger connection status (connected/disconnected)
- Charging power, current, voltage
- Target SOC (charge limit)

Protocol definitions reconstructed from Polestar Android app v5.5.0.
"""

import logging
import uuid
from datetime import datetime, timezone

import grpc
import grpc.aio
import httpx

from .grpc_models import (
    ChargeTargetLevelSettingType,
    ChargingConnectionStatus,
    ChargingStatus,
    ChargingType,
    GrpcBatteryData,
    GrpcTargetSocData,
)
from .proto import (
    polestar_battery_pb2,
    polestar_battery_service_pb2,
    polestar_chronos_request_pb2,
    polestar_target_soc_pb2,
)

_LOGGER = logging.getLogger(__name__)

# Discovery endpoint for C3 gRPC host (returns dynamic host/port)
C3_DISCOVERY_URL = "https://cnepmob.volvocars.com"
# Target SOC/charge timers come from Polestar's own PCCS platform
GRPC_PCCS_HOST = "api.pccs-prod.plstr.io"
GRPC_PORT = 443
GRPC_TIMEOUT = 30

# gRPC status codes that mean "this vehicle will never serve this data".
#
# Not all vehicles are provisioned in every backend: the Polestar 2 is a Volvo
# CMA-platform car and is not registered in Polestar's own PCCS/chronos
# platform, so TargetSocService returns PERMISSION_DENIED for it even though
# the access token is perfectly valid (an unauthenticated call is rejected
# earlier, at the gateway, with UNAUTHENTICATED). Retrying such a call on every
# poll only produces log noise, so we remember the VIN and stop asking.
UNSUPPORTED_STATUS_CODES = frozenset(
    {
        grpc.StatusCode.PERMISSION_DENIED,
        grpc.StatusCode.UNIMPLEMENTED,
        grpc.StatusCode.NOT_FOUND,
    }
)


def _connection_status(value: int) -> ChargingConnectionStatus:
    name = polestar_battery_pb2.ChargerConnectionStatus.Name(value)
    return ChargingConnectionStatus.get(name, ChargingConnectionStatus.CHARGER_CONNECTION_STATUS_UNSPECIFIED)


def _charging_status(value: int) -> ChargingStatus:
    name = polestar_battery_pb2.ChargingStatus.Name(value)
    return ChargingStatus.get(name, ChargingStatus.CHARGING_STATUS_UNSPECIFIED)


def _charging_type(value: int) -> ChargingType:
    name = polestar_battery_pb2.ChargingType.Name(value)
    return ChargingType.get(name, ChargingType.CHARGING_TYPE_UNSPECIFIED)


def _target_soc_setting_type(value: int) -> ChargeTargetLevelSettingType:
    name = polestar_target_soc_pb2.ChargeTargetLevelSettingType.Name(value)
    return ChargeTargetLevelSettingType.get(
        name, ChargeTargetLevelSettingType.CHARGE_TARGET_LEVEL_SETTING_TYPE_UNSPECIFIED
    )


class PolestarGrpcClient:
    """Client for the Polestar gRPC API (cnepmob.volvocars.com)."""

    def __init__(self, client_session: httpx.AsyncClient, unique_id: str | None = None):
        self.client_session = client_session
        self.c3_channel: grpc.aio.Channel | None = None
        self.pccs_channel: grpc.aio.Channel | None = None
        self.unsupported_battery: set[str] = set()
        self.unsupported_target_soc: set[str] = set()
        self.logger = _LOGGER.getChild(unique_id) if unique_id else _LOGGER

    async def connect(self) -> None:
        """Connect to both gRPC servers."""
        creds = grpc.ssl_channel_credentials()

        # Discover C3 gRPC host dynamically
        c3_host, c3_port = await self._discover_c3_host()
        c3_target = f"{c3_host}:{c3_port}"
        self.c3_channel = grpc.aio.secure_channel(c3_target, creds)
        self.logger.debug("gRPC C3 channel created for %s", c3_target)

        pccs_target = f"{GRPC_PCCS_HOST}:{GRPC_PORT}"
        self.pccs_channel = grpc.aio.secure_channel(pccs_target, creds)
        self.logger.debug("gRPC PCCS channel created for %s", pccs_target)

        # Only now that fresh channels are in place is it worth re-evaluating
        # per-vehicle support; a failed reconnect keeps the old channels, and
        # with them what we already learned about these vehicles.
        self.unsupported_battery.clear()
        self.unsupported_target_soc.clear()

    async def _discover_c3_host(self) -> tuple[str, int]:
        """Discover the C3 gRPC host via the cnepmob discovery endpoint."""
        resp = await self.client_session.get(
            C3_DISCOVERY_URL,
            headers={"Accept": "application/volvo.cloud.cnepmob.v1+json"},
        )
        resp.raise_for_status()
        data = resp.json()
        c3 = data["c3"]
        host = c3["grpcHost"]
        port = c3["grpcPort"]
        self.logger.debug("C3 gRPC discovered: %s:%d", host, port)
        return host, port

    async def close(self) -> None:
        """Close the gRPC channels."""
        if self.c3_channel:
            await self.c3_channel.close()
            self.c3_channel = None
        if self.pccs_channel:
            await self.pccs_channel.close()
            self.pccs_channel = None

    def _metadata(self, access_token: str, vin: str) -> list[tuple[str, str]]:
        return [
            ("authorization", f"Bearer {access_token}"),
            ("vin", vin),
        ]

    def _mark_unsupported(self, unsupported: set[str], vin: str, what: str, exc: grpc.aio.AioRpcError) -> bool:
        """Remember that a vehicle does not provide this data, if the error says so permanently."""
        if exc.code() not in UNSUPPORTED_STATUS_CODES:
            return False
        unsupported.add(vin)
        self.logger.info(
            "gRPC %s not available for this vehicle (%s), not retrying",
            what,
            exc.code().name,
        )
        return True

    def is_battery_supported(self, vin: str) -> bool:
        """Whether the C3 battery service is known to serve data for this vehicle."""
        return vin not in self.unsupported_battery

    def is_target_soc_supported(self, vin: str) -> bool:
        """Whether the PCCS target SOC service is known to serve data for this vehicle."""
        return vin not in self.unsupported_target_soc

    async def get_battery(self, vin: str, access_token: str) -> GrpcBatteryData | None:
        """Get battery status including charger connection status via gRPC (C3/Volvo endpoint)."""
        if not self.c3_channel:
            raise RuntimeError("gRPC C3 channel not connected")

        if vin in self.unsupported_battery:
            return None

        request = polestar_battery_service_pb2.GetBatteryRequest(
            id=str(uuid.uuid4()),
            vin=vin,
        )

        try:
            # Battery service lives on C3 (cnepmob.volvocars.com) with shorter service path
            response = await self.c3_channel.unary_unary(
                "/services.vehiclestates.battery.BatteryService/GetLatestBattery",
                request_serializer=polestar_battery_service_pb2.GetBatteryRequest.SerializeToString,
                response_deserializer=polestar_battery_service_pb2.GetBatteryResponse.FromString,
            )(request, metadata=self._metadata(access_token, vin), timeout=GRPC_TIMEOUT)

            self.logger.debug("gRPC GetLatestBattery response: %s", response)

            if not response.HasField("battery"):
                self.logger.warning("gRPC GetLatestBattery: no battery field in response")
                return None

            return _parse_battery(response.battery)

        except grpc.aio.AioRpcError as exc:
            if self._mark_unsupported(self.unsupported_battery, vin, "battery data", exc):
                return None
            self.logger.error("gRPC GetLatestBattery failed: %s (code=%s)", exc.details(), exc.code())
            raise

    async def get_target_soc(self, vin: str, access_token: str) -> GrpcTargetSocData | None:
        """Get target SOC (charge limit) via gRPC (PCCS/Polestar endpoint)."""
        if not self.pccs_channel:
            raise RuntimeError("gRPC PCCS channel not connected")

        if vin in self.unsupported_target_soc:
            return None

        chronos_req = polestar_chronos_request_pb2.ChronosRequest(
            id=str(uuid.uuid4()),
            vin=vin,
            source="mobile",
        )
        request = polestar_target_soc_pb2.GetTargetSocRequest(request=chronos_req)

        try:
            # TargetSocService.GetTargetSoc is server-streaming; read first response
            call = self.pccs_channel.unary_stream(
                "/pccs.chronos.services.v1.TargetSocService/GetTargetSoc",
                request_serializer=polestar_target_soc_pb2.GetTargetSocRequest.SerializeToString,
                response_deserializer=polestar_target_soc_pb2.GetTargetSocResponse.FromString,
            )(request, metadata=self._metadata(access_token, vin), timeout=GRPC_TIMEOUT)

            response = None
            async for msg in call:
                response = msg
                break  # We only need the first response

            if response is None:
                self.logger.warning("gRPC GetTargetSoc: empty stream")
                return None

            self.logger.debug("gRPC GetTargetSoc response: %s", response)

            return _parse_target_soc(response)

        except grpc.aio.AioRpcError as exc:
            if self._mark_unsupported(self.unsupported_target_soc, vin, "target SOC", exc):
                return None
            self.logger.error("gRPC GetTargetSoc failed: %s (code=%s)", exc.details(), exc.code())
            raise


def _parse_battery(b: polestar_battery_pb2.Battery) -> GrpcBatteryData:
    """Parse a Battery protobuf message into GrpcBatteryData."""
    ts: datetime | None = None
    if b.HasField("timestamp"):
        ts = datetime.fromtimestamp(b.timestamp.seconds, tz=timezone.utc)

    return GrpcBatteryData(
        charger_connection_status=_connection_status(b.charger_connection_status),
        charging_status=_charging_status(b.charging_status),
        battery_charge_level_percentage=b.battery_charge_level_percentage,
        estimated_distance_to_empty_km=b.estimated_distance_to_empty_km,
        estimated_charging_time_to_full_minutes=b.estimated_charging_time_to_full_minutes,
        charging_power_watts=b.charging_power_watts,
        charging_current_amps=b.charging_current_amps,
        charging_voltage_volts=b.charging_voltage_volts,
        charging_type=_charging_type(b.charging_type),
        average_energy_consumption_kwh_per_100km=b.average_energy_consumption_kwh_per_100_km,
        estimated_charging_time_minutes_to_target_distance=b.estimated_charging_time_minutes_to_target_distance,
        estimated_charging_time_minutes_to_minimum_soc=b.estimated_charging_time_minutes_to_minimum_soc,
        timestamp=ts,
    )


def _parse_target_soc(response: polestar_target_soc_pb2.GetTargetSocResponse) -> GrpcTargetSocData:
    """Parse a GetTargetSocResponse into GrpcTargetSocData."""
    target_level: int | None = None
    target_type = ChargeTargetLevelSettingType.CHARGE_TARGET_LEVEL_SETTING_TYPE_UNSPECIFIED
    pending_level: int | None = None
    pending_type = ChargeTargetLevelSettingType.CHARGE_TARGET_LEVEL_SETTING_TYPE_UNSPECIFIED

    if response.HasField("target_soc"):
        ts = response.target_soc
        target_level = ts.battery_charge_target_level
        target_type = _target_soc_setting_type(ts.charge_target_level_setting_type)

    if response.HasField("pending_target_soc"):
        pts = response.pending_target_soc
        pending_level = pts.battery_charge_target_level
        pending_type = _target_soc_setting_type(pts.charge_target_level_setting_type)

    return GrpcTargetSocData(
        battery_charge_target_level=target_level,
        charge_target_level_setting_type=target_type,
        pending_battery_charge_target_level=pending_level,
        pending_charge_target_level_setting_type=pending_type,
    )
