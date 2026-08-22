# Changelog

## Unreleased (this fork)

### Added

- `CarInformationData.pno34` and `CarInformationData.structure_week`. Both were
  already being fetched by `QUERY_GET_CONSUMER_CARS_V2` (they're required
  internally to call `GetCarImages`) but silently dropped instead of being
  exposed. No new API calls; existing `getConsumerCarsV2` response data was
  parsed further.

- Seven new **best-effort, read-only** gRPC services, all on the existing C3
  channel (`cnepmob.volvocars.com`), following the exact pattern already used
  by `get_battery`/`get_target_soc` (capability tracking via
  `is_<x>_supported`, non-fatal per-vehicle backoff on
  `PERMISSION_DENIED`/`UNIMPLEMENTED`/`NOT_FOUND`):

  | Method | Data | New in `pypolestar` |
  | --- | --- | --- |
  | `get_exterior` | Doors, windows, central/tailgate lock, hood, tank lid, sunroof, alarm | Not available via GraphQL at all |
  | `get_health` | Per-tyre pressure (kPa) + warning level, exterior light failures | GraphQL's `health` query only has brake/coolant/oil/service warnings |
  | `get_odometer` | Trip meters (manual/automatic), average speed | `CarOdometerData` has fields for these but they're always `None` today |
  | `get_climate` | Parking climatization: running status, cabin temp, seat + steering-wheel heating levels | Not available via GraphQL at all |
  | `get_availability` | Online/awake state, usage mode | Not available via GraphQL at all |
  | `get_precleaning` | Cabin air pre-cleaning ("CleanZone") status | Not available via GraphQL at all |
  | `get_location` | Last known GPS position | Not available via GraphQL at all |

  New enum values `BRAKE_FLUID_LEVEL_WARNING_CRITICALLY_LOW` and four
  `SERVICE_WARNING_ENGINE_HOURS_*` / `SERVICE_WARNING_UNKNOWN_WARNING`
  members were added to the existing GraphQL-facing enums in `models.py`
  (rather than duplicating them in `grpc_models.py`) since gRPC's `Health`
  message reports a superset of the same warning types GraphQL does.

### Explicitly not implemented

These were identified as gaps against a third-party client but **no public
protobuf schema could be found** for them from any source below, so they were
not guessed at:

- `ota_mobcache.OtaDiscoveryService/GetSoftwareInfo` (installed/available
  software version, update state)
- `car_information.CarInformation/GetMyCars` (OTA capability flags,
  authoritative installed version)
- `pccs.chronos.services.v1.AmpLimitService/GetAmpLimit` (charging current
  limit, read)
- `weather.WeatherService/GetWeatherReport` (vehicle-reported local weather —
  distinct from calling a third-party weather API with the vehicle's
  coordinates, which needs no Polestar schema at all)
- `services.vehiclestates.airquality.AirQualityService` (cabin air quality)
- `chronos.services.v1.ErrorService/GetErrors` (vehicle fault/error codes)
- `pccs.chronos.services.v1.ChargeLocationService` /
  `GlobalChargeTimerService` / `ParkingClimateTimerService` (saved charge
  locations, charging schedules, climate schedules)

Only the gRPC method *paths* for these are publicly known (see sources
below); the message field layout is not, and guessing field numbers risks
silently misreporting real vehicle state rather than just failing loudly.
Contributions with a verified schema (e.g. from your own captured traffic
against a real vehicle) are welcome.

No remote/write commands (lock, unlock, climate start/stop, charge target,
etc.) were implemented in this pass — this fork is read-only telemetry only.

### Field layout provenance and confidence

Unlike the original `polestar_battery`/`polestar_target_soc` definitions
(reconstructed from decompiling the Polestar Android APK directly), the
seven services above were **not decompiled by this fork's author**. Their
field layout was cross-referenced from multiple independent public
reverse-engineering projects and treated as unverified until it can be
checked against a real vehicle:

- [`NicolasKheirallah/Hisingen`](https://github.com/NicolasKheirallah/Hisingen) —
  confirmed the gRPC service *paths* (e.g. `ExteriorService/GetLatestExterior`)
  used to call each service, and which run on the C3 vs. PCCS host. Does not
  publish message field layouts by design (its own docs explicitly keep
  reverse-engineering notes out of the public repo).
- [`melosbot/xiaowo-remote`](https://github.com/melosbot/xiaowo-remote) —
  primary source for message field names/numbers/enum values, extracted from
  official `cn.volvo.vcc` app reflection metadata (APK SHA-256 recorded in
  each `.proto` file in that repo). No license was declared on that repo, so
  its files were not copied directly; field facts were used to independently
  author the `.proto` sources in `pypolestar/proto/`.
- [`Yeetusbleetus/hass-polestar-pccs`](https://github.com/Yeetusbleetus/hass-polestar-pccs)
  (MIT) and [`idreamshen/hass-volvooncall-cn`](https://github.com/idreamshen/hass-volvooncall-cn) —
  independent corroboration for `ExteriorService`, `ParkingClimatizationService`,
  `AvailabilityService` and `PreCleaningService` field layouts.
- [`Greg-Boyles/NorthStar.Api`](https://github.com/Greg-Boyles/NorthStar.Api),
  [`kildahldev/unofficial-polestar-api`](https://github.com/kildahldev/unofficial-polestar-api),
  [`2ndalpha/polestar-home-assistant`](https://github.com/2ndalpha/polestar-home-assistant) —
  further corroboration for service paths and the C3/PCCS host split.

Where only one method of a service was confirmed (e.g. `ExteriorService`'s
streaming `GetExterior`), a `GetLatest<X>` unary sibling was added by analogy
with `BatteryService`'s confirmed `GetBattery`/`GetLatestBattery` pairing —
called out per-service in the `.proto` file's comments. `is_<x>_supported()`
returning `False` after a `PERMISSION_DENIED`/`UNIMPLEMENTED`/`NOT_FOUND`
response means either the vehicle genuinely doesn't serve that data, or the
guessed method/field layout is wrong for it — these two cases cannot be told
apart without a live vehicle to test against.
