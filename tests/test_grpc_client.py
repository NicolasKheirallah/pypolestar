"""Tests for gRPC client error handling."""

import asyncio

import grpc
import grpc.aio
import httpx
import pytest

from pypolestar.grpc_client import PolestarGrpcClient

VIN = "YSMYKEAE7RB000000"
TOKEN = "token"

# Status codes the client must read as "this vehicle will never serve this data"
PERMANENT_STATUS_CODES = [
    grpc.StatusCode.PERMISSION_DENIED,
    grpc.StatusCode.UNIMPLEMENTED,
    grpc.StatusCode.NOT_FOUND,
]


def _rpc_error(code: grpc.StatusCode) -> grpc.aio.AioRpcError:
    return grpc.aio.AioRpcError(
        code=code,
        initial_metadata=grpc.aio.Metadata(),
        trailing_metadata=grpc.aio.Metadata(),
        details=f'Status(StatusCode="{code.name}", Detail="")',
    )


class FailingChannel:
    """Channel stub where every call raises, counting the attempts."""

    def __init__(self, error: grpc.aio.AioRpcError):
        self.error = error
        self.calls = 0

    def _fail(self, *args, **kwargs):
        self.calls += 1
        raise self.error

    def unary_unary(self, *args, **kwargs):
        return self._fail

    def unary_stream(self, *args, **kwargs):
        return self._fail


def _client(**channels) -> PolestarGrpcClient:
    client = PolestarGrpcClient(client_session=None)  # type: ignore[arg-type]
    for name, channel in channels.items():
        setattr(client, name, channel)
    return client


@pytest.mark.parametrize("code", PERMANENT_STATUS_CODES)
def test_target_soc_permanent_error_is_not_retried(code):
    """A Polestar 2 is not provisioned in PCCS: refuse once, then stop asking."""
    channel = FailingChannel(_rpc_error(code))
    client = _client(pccs_channel=channel)

    assert asyncio.run(client.get_target_soc(VIN, TOKEN)) is None
    assert client.is_target_soc_supported(VIN) is False
    assert channel.calls == 1

    assert asyncio.run(client.get_target_soc(VIN, TOKEN)) is None
    assert channel.calls == 1, "unsupported vehicle should not hit the network again"


def test_target_soc_transient_error_is_raised_and_retried():
    channel = FailingChannel(_rpc_error(grpc.StatusCode.UNAVAILABLE))
    client = _client(pccs_channel=channel)

    for _ in range(2):
        with pytest.raises(grpc.aio.AioRpcError):
            asyncio.run(client.get_target_soc(VIN, TOKEN))

    assert client.is_target_soc_supported(VIN) is True
    assert channel.calls == 2


@pytest.mark.parametrize("code", PERMANENT_STATUS_CODES)
def test_battery_permanent_error_is_not_retried(code):
    channel = FailingChannel(_rpc_error(code))
    client = _client(c3_channel=channel)

    assert asyncio.run(client.get_battery(VIN, TOKEN)) is None
    assert client.is_battery_supported(VIN) is False
    assert channel.calls == 1

    assert asyncio.run(client.get_battery(VIN, TOKEN)) is None
    assert channel.calls == 1


def test_battery_transient_error_is_raised():
    channel = FailingChannel(_rpc_error(grpc.StatusCode.INTERNAL))
    client = _client(c3_channel=channel)

    with pytest.raises(grpc.aio.AioRpcError):
        asyncio.run(client.get_battery(VIN, TOKEN))

    assert client.is_battery_supported(VIN) is True


def test_failed_reconnect_keeps_unsupported_vehicles():
    """The old channels survive a failed reconnect, so what we learned must too."""

    class FailingSession:
        async def get(self, *args, **kwargs):
            raise httpx.ConnectError("discovery unreachable")

    channel = FailingChannel(_rpc_error(grpc.StatusCode.PERMISSION_DENIED))
    client = PolestarGrpcClient(client_session=FailingSession())  # type: ignore[arg-type]
    client.pccs_channel = channel

    assert asyncio.run(client.get_target_soc(VIN, TOKEN)) is None
    assert client.is_target_soc_supported(VIN) is False

    with pytest.raises(httpx.ConnectError):
        asyncio.run(client.connect())

    assert client.is_target_soc_supported(VIN) is False
    assert asyncio.run(client.get_target_soc(VIN, TOKEN)) is None
    assert channel.calls == 1, "a failed reconnect must not resurrect refused calls"
