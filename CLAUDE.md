# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`pypolestar` is an async Python client library for the Polestar EV API (used by the Home Assistant Polestar integration, among others). It is not affiliated with or supported by Polestar. It combines two backends:

- **GraphQL** (`pypolestar/graphql.py`) against `pc-api.polestar.com` for account/vehicle info, telematics (battery/odometer/health), and car images.
- **gRPC** (`pypolestar/grpc_client.py`) against Polestar/Volvo's connected-car services, for data not available via GraphQL (charger connection status, live charging power/current/voltage, target SOC/charge limit). The gRPC protocol was reconstructed from the Polestar Android app and talks to two separate channels: a discovered "C3" host (`cnepmob.volvocars.com`, Volvo-side battery service) and a fixed PCCS host (`api.pccs-prod.plstr.io`, Polestar-side target SOC/chronos service).

Authentication (`pypolestar/auth.py`) is OAuth2/OIDC (PKCE) against `polestarid.eu.polestar.com`, screen-scraping a login form flow, with automatic access-token refresh.

## Commands

Uses `uv` for dependency management.

```bash
make lint       # ruff check pypolestar tests
make reformat   # ruff --fix (isort) + ruff format
make test       # pytest --ruff --ruff-format pypolestar tests
make proto      # regenerate *_pb2.py / *_pb2_grpc.py from pypolestar/proto/*.proto via grpc_tools.protoc
```

Run a single test:

```bash
uv run pytest tests/test_models.py::test_car_information -v
uv run pytest tests/test_grpc_models.py -k target_soc
```

CI (`.github/workflows/test.yml`) runs `ruff check` + `ruff format --check`, then `make test` across Python 3.11–3.14.

## Architecture

- **`api.py` — `PolestarApi`**: the main entry point. Holds one `httpx.AsyncClient`, one `PolestarAuth`, one `PolestarGrpcClient`, and a `data_by_vin` dict keyed by VIN that caches raw responses under keys defined in `const.py` (`CAR_INFO_DATA`, `TELEMATICS_DATA`, `CAR_IMAGES_DATA`, `GRPC_BATTERY_DATA`, `GRPC_TARGET_SOC_DATA`). `async_init()` discovers vehicles and populates the cache; `update_latest_data(vin, ...)` refreshes it per-VIN under an `asyncio.Lock` (one lock per VIN, updates for a VIN in progress are skipped rather than queued). Public `get_*` methods convert cached raw dicts into typed dataclasses on demand — they raise `KeyError` if the VIN is unknown and `ValueError` if conversion fails.
- **`auth.py` — `PolestarAuth`**: implements the OIDC authorization-code (PKCE) flow by POSTing the login form to `polestarid.eu.polestar.com`, extracting the resulting `code`, and exchanging it for tokens. Handles the "accept terms and conditions" interstitial and refresh-token renewal. Token refresh is gated by `TOKEN_REFRESH_WINDOW_MIN`/`need_token_refresh()` and serialized with a lock.
- **`graphql.py`**: builds a `gql` `Client` over a custom `httpx`-backed transport (reuses the shared `AsyncClient` rather than opening its own), with `backoff`-based retry for connect and execute. Also defines the three GraphQL query documents used by the API.
- **`grpc_client.py` — `PolestarGrpcClient`**: opens two `grpc.aio` channels (`connect()` discovers the C3 host via an HTTP call, then opens both channels) and exposes `get_battery()` / `get_target_soc()`. Both are called manually via `channel.unary_unary`/`unary_stream` with explicit protobuf serializers rather than generated stub classes. `get_target_soc` is a server-streaming RPC; only the first message is consumed. Module-level `_parse_battery`/`_parse_target_soc` convert protobuf messages to the `grpc_models.py` dataclasses, mapping proto enum ints to `StrEnumOptional` values via `.Name()` lookups with `.get(name, ...UNSPECIFIED)` fallback for unknown enum values.
- **`pypolestar/proto/`**: `.proto` sources plus generated `*_pb2.py`/`*_pb2_grpc.py` (regenerate with `make proto`, which also patches generated imports to be package-relative — see the `sed` step in the `Makefile`). Excluded from ruff lint via `extend-exclude`.
- **`models.py`**: frozen dataclasses for GraphQL-derived data (`CarInformationData`, `CarTelematicsData`, `CarBatteryData`, `CarOdometerData`, `CarHealthData`, `CarImagesData`) built with `from_dict()` classmethods, plus shared `StrEnumOptional` string enums (`ChargingStatus`, `ChargingConnectionStatus`, warning types, etc.) reused by `grpc_models.py`. Field extraction from the loosely-typed GraphQL JSON goes through helpers in `utils.py` (`get_field_name_str`/`_int`/`_timestamp`, `GqlDict`) to tolerate missing/null fields.
- **`grpc_models.py`**: frozen dataclasses for gRPC-derived data (`GrpcBatteryData`, `GrpcTargetSocData`) and gRPC-only enums (`ChargingType`, `ChargeTargetLevelSettingType`); imports the shared status enums from `models.py`.
- **`cli.py`**: `polestar` console-script entry point for manual/interactive use against a real account.

## Testing conventions

- `tests/test_models.py` exercises `from_dict()` conversions against real (sanitized) GraphQL JSON fixtures in `tests/data/polestar{2,3,4}.json` — one fixture per Polestar model, since field availability differs by model.
- `tests/test_grpc_models.py` exercises `_parse_battery`/`_parse_target_soc` against real captured-and-anonymized protobuf wire bytes in `tests/data/*.bin`. These fixtures are regenerated by running `tests/capture_grpc_fixtures.py` against a real account (`POLESTAR_USERNAME`/`POLESTAR_PASSWORD`/`POLESTAR_VIN` env vars) — it anonymizes identifying fields (VIN, ids, source, timestamps) in memory before writing to disk, so only the fixed `ANON_VIN`/`ANON_ID`/`ANON_TIMESTAMP` values (defined at the top of `test_grpc_models.py`) should ever appear in committed fixtures.
- Both test modules `pytest.skip()` when fixture files are missing rather than failing, so new fixtures are opt-in.
