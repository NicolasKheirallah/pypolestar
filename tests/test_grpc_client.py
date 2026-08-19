"""Tests for gRPC client error handling."""

import asyncio

import grpc
import grpc.aio
import pytest

from pypolestar.grpc_client import PolestarGrpcClient

VIN = "YSMYKEAE7RB000000"
TOKEN = "token"


def _rpc_error(code: grpc.StatusCode) -> grpc.aio.AioRpcError:
    return grpc.aio.AioRpcError(
        code=code,
        initial_metadata=grpc.aio.Metadata(),
        trailing_metadata=grpc.aio.Metadata(),
        details='Status(StatusCode="PermissionDenied", Detail="")',
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


def test_target_soc_permission_denied_is_not_retried():
    """A Polestar 2 is not provisioned in PCCS: refuse once, then stop asking."""
    channel = FailingChannel(_rpc_error(grpc.StatusCode.PERMISSION_DENIED))
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


def test_battery_permission_denied_is_not_retried():
    channel = FailingChannel(_rpc_error(grpc.StatusCode.PERMISSION_DENIED))
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
