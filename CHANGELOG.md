# Changelog

## Unreleased (this fork)

### Investigated, no further progress (2026-08-22)

A follow-up investigation pass, in order of what was tried:

- **gRPC server reflection** (`grpc.reflection.v1alpha.ServerReflection` and
  the newer `v1`) -- tried against both C3 and PCCS, with and without auth
  metadata. Cleanly `UNIMPLEMENTED` every time; disabled server-side. Would
  have been the single best way to settle every remaining schema question
  at once (enumerate every service + get real `FileDescriptorProto` bytes),
  but it's not available.
- **`services.vehiclestates.dashboard.DashboardService/GetLatestDashboard`**
  (a path referenced by third-party clients, never tried before this fork) --
  `UNIMPLEMENTED`, "Method not found". Doesn't exist at this path/name.
- **`ota_mobcache.SchedulerService/GetSchedule`** (OTA install scheduling,
  companion to `GetSoftwareInfo`) -- same `UNAUTHENTICATED`/"Authorization
  failed" as `GetSoftwareInfo` got in the previous pass. Root cause found
  this time: Hisingen's source comments explain the OIDC client `pypolestar`
  authenticates as (`l3oopkc_10`) only requests scope
  `"openid profile email customer:attributes"`, but `ota_mobcache.*`
  requires `customer:attributes:write` in addition -- confirmed by
  Hisingen's own comment that this scope exists specifically for
  `SchedulerService`'s *write* RPCs. **Not pursued further**: requesting a
  write-capable OAuth scope changes what the resulting token is technically
  capable of even if `pypolestar`'s code only ever calls read methods with
  it, which is a real trust-boundary change adjacent to the remote/write
  commands this fork has deliberately stayed out of. Separately, Hisingen
  also uses a *second* OIDC client (`lp8dyrd_10`) purely to satisfy a
  client-ID allowlist gate on C3's invoke (write) RPCs -- unrelated to scope,
  and also not pursued for the same reason.
- **`GetVDMSCars`** (the app-backend GraphQL query for exterior colour,
  upholstery, wheels, factory packages -- a different endpoint,
  `pc-api.polestar.com/eu-north-1/app-backend/api/graphql`, from the
  `mystar-v2`/`mystar-public` ones `pypolestar` already uses) -- reachable,
  but every request was rejected at the edge (Cloudflare Worker in front of
  it) with an empty-body `428` then `426` response, unchanged by adding
  Hisingen's exact header set or switching to HTTP/2. Reads as
  bot/fingerprint-based edge protection rather than a GraphQL-level or
  auth-level rejection (those return JSON error bodies, not an empty
  transport-level status). **Deliberately not pursued further**: getting
  past this would mean specifically working around anti-automation
  protection rather than reverse-engineering an API contract, which this
  fork has not done anywhere else and shouldn't start here.

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

- Three more gRPC services, reverse-engineered directly from a real
  account/vehicle rather than cross-referenced from other projects -- see
  "Live schema discovery" below:

  | Method | Data | New in `pypolestar` |
  | --- | --- | --- |
  | `get_mycars` | Vehicle identity, installed software version | GraphQL has no installed-software-version field at all |
  | `get_amp_limit` | Charging current limit (read) | Not available via GraphQL at all |
  | `get_charge_schedule` | Overnight charging window (start/end hour) | Not available via GraphQL at all |

### Explicitly not implemented

- No remote/write commands (lock, unlock, climate start/stop, charge target,
  etc.) were implemented in this pass — this fork is read-only telemetry
  only.
- `weather.WeatherService/GetWeatherReport`, `services.vehiclestates.weather.WeatherService/GetLatestWeather`,
  `services.vehiclestates.airquality.AirQualityService/{GetLatestAirQuality,GetAirQuality}` —
  live-tested against a real account (see below); every method name tried
  returned `UNIMPLEMENTED`/"Method not found" on both C3 and PCCS. Either
  these aren't real endpoints, or the real method name differs from every
  variant tried.
- `ota_mobcache.OtaDiscoveryService/GetSoftwareInfo` — live-tested; returned
  `UNAUTHENTICATED` ("Authorization failed"), not `UNIMPLEMENTED`/`NOT_FOUND`,
  meaning the endpoint exists but this account's token doesn't have whatever
  scope it needs. `get_mycars` (below) already covers the same underlying
  need (installed software version) via a working endpoint, so this wasn't
  pursued further.
- `chronos.services.v1.ErrorService/GetErrors` and `pccs.chronos.services.v1.ErrorService/GetErrors` —
  the bare `chronos.*` path is `UNIMPLEMENTED`; the `pccs.chronos.*` path
  accepts the request (no error) but never emitted a message before a 15s
  deadline, on a vehicle with no active faults. Plausibly a "subscribe and
  wait" stream with nothing to report right now, or the wrong service --
  can't be told apart without either a longer-lived test or an account
  currently showing a fault.
- `pccs.chronos.services.v1.ChargeLocationService/GetChargeLocations` —
  live-tested; the request succeeds and returns the id/vin envelope with no
  entries, because this account has no saved charge locations. The outer
  envelope is confirmed but there's no populated example to reverse-engineer
  a per-location entry's fields from (alias, amp limit, minimum SoC, etc.).
- `pccs.chronos.services.v1.ParkingClimateTimerService/GetTimers` —
  live-tested; returned a real, structurally similar entry to
  `GlobalChargeTimerService`'s, but for what looks like a disabled/default
  timer (mostly-zero fields, one raw sub-field this fork's decoder couldn't
  parse as a coherent scalar -- possibly a packed-repeated field, e.g.
  days-of-week). Lower confidence than `GlobalChargeTimerService`, where two
  clearly-different, clearly-sane hour values (23 and 6) gave a strong
  signal; here there wasn't an equivalent signal to confirm field meaning
  against, so it wasn't implemented.

Contributions with a verified schema for any of the above (e.g. your own
captured traffic against a real vehicle with saved charge locations, an
active fault, or a configured climate timer) are welcome.

### Live validation (2026-08-22, Polestar 2, MY2023)

All seven new services were exercised against a real account and vehicle
(`get_exterior`/`get_health`/`get_odometer`/`get_climate`/`get_availability`/
`get_precleaning`/`get_location`, plus the `pno34`/`structure_week` fix).
Every call succeeded (`is_<x>_supported() == True`, no
`PERMISSION_DENIED`/`UNIMPLEMENTED` for any of them) and returned data that
cross-checks as correct:

- **`get_exterior`**: reported the car fully locked and closed while parked —
  consistent with its actual state.
- **`get_odometer`**: `odometer_meters` matched the existing, already-trusted
  GraphQL `carTelematicsV2.odometer.odometerMeters` value *exactly* (both
  121516496), on the same call. Trip meters and average speed (new; GraphQL
  never populates these) came back as plausible, distinct values.
- **`get_location`**: returned coordinates that plot in Gothenburg, Sweden —
  correct for this account, and rules out the latitude/longitude fields
  being swapped.
- **`get_health`**: days/distance-to-service and all warning enums (brake
  fluid, coolant, oil, service, low-voltage battery, 21 individual exterior
  lights) came back as real, non-default `NO_WARNING`/`OFF` values rather
  than falling through to `UNSPECIFIED` -- confirms those field numbers are
  right. The four tyre-pressure-kPa and four tyre-pressure-warning fields
  came back as zero/`UNSPECIFIED` on this vehicle specifically; given every
  *other* field in the same message decoded correctly, this looks like this
  Polestar 2's TPMS not reporting precise pressure (known to vary by model
  year/hardware) rather than a wrong field number, but it's only confirmed
  absent, not confirmed present-and-correct elsewhere.
- **`get_climate`** / **`get_availability`** / **`get_precleaning`**:
  returned internally consistent idle/off state for a parked, unoccupied car
  (nothing running to exercise the active-state fields against).

This is one vehicle, one model, one state (parked, idle, not charging, not
climatizing). Active-charging, active-climate, and any-warning-present states
are still unverified, as is behavior on Polestar 3/4/5.

### Live schema discovery (2026-08-22, same account/vehicle as above)

`get_mycars`, `get_amp_limit` and `get_charge_schedule` were reverse-engineered
directly, not cross-referenced from another project: the known gRPC *path*
for each (from the same public sources as above, which publish paths but not
schemas) was called with a real access token and a generic
`{id: uuid, vin: VIN}` or `ChronosRequest{id, vin, source="mobile"}` request
(the shape every other confirmed service in this fork uses), and the raw
response bytes were decoded with a throwaway generic protobuf wire-format
reader (field number + wire type + value, recursively) -- effectively
`protoc --decode_raw` against a live endpoint. This is the same kind of
interoperability reverse-engineering `pypolestar` already does by decompiling
the Polestar app; the only difference is reading it from the wire instead of
from the app binary.

- **`get_mycars`**: the response decoded cleanly into `vin`, `model_name`,
  `model_year`, `market` and `registration_no` that matched this account's
  already-known values exactly, plus `installed_software_version` ("4.2.13")
  -- which appeared *twice*, in two unrelated-looking parts of the same
  message, strengthening confidence it's really the software version and not
  a coincidence. The full response has ~80 more fields (capability flags,
  factory option codes) visible on the wire but not confidently namable from
  one account's data; they're left unmapped rather than guessed (protobuf
  quietly preserves undefined fields as "unknown", it doesn't error).
- **`get_amp_limit`**: the response envelope
  (`id`/`vin`/`reading{value,updated_at,source,id}`/`updated_at`) is
  structurally identical to the already-proven `GetTargetSocResponse`,
  strongly suggesting PCCS chronos services share one settings-envelope
  convention. `value` came back `20`, a plausible AC current in amps, but was
  not cross-checked against this account's actual configured limit. The call
  also revealed this service is long-lived/server-streaming in practice (one
  message, then the connection stays open past a 15s deadline rather than
  closing) -- read the same way as `get_target_soc`: first message only.
- **`get_charge_schedule`**: returned a real schedule,
  `start.hour=23, end.hour=6` -- a plain, ordinary overnight/off-peak
  charging window. No explicit minute field was present in either
  `ScheduleTime`; proto3 omits zero-valued scalar fields on the wire, so
  this is consistent with (but doesn't prove) a round-hour schedule. A
  same-valued nested sub-field (120) appeared identically in both `start`
  and `end`; a plausible read is a timezone-offset-in-minutes wrapper
  (120 = UTC+2, correct for Swedish summer time) shared by the whole
  message rather than varying per-field, but this wasn't confirmed and was
  deliberately left unmapped instead of named.

A one-line raw-decode fix was needed mid-investigation: the initial probe
guessed `source` at field 4 of `ChronosRequest` instead of field 3 (field 4
is actually a `TimeZone` submessage), which the server rejected server-side
("Exception was thrown by handler") for every PCCS chronos service tried.
Checking pypolestar's own already-working `polestar_chronos_request.proto`
instead of re-guessing resolved it immediately -- worth remembering that the
existing proven schemas are a better source of truth than fresh guessing
even when investigating unrelated services.

### Field layout provenance and confidence (the first seven services)

Unlike the original `polestar_battery`/`polestar_target_soc` definitions
(reconstructed from decompiling the Polestar Android APK directly), and
unlike `get_mycars`/`get_amp_limit`/`get_charge_schedule` above (discovered
live, see previous section), the seven services in "Added" above were **not
decompiled by this fork's author**. Their field layout was cross-referenced
from multiple independent public reverse-engineering projects, then
spot-checked live (see "Live validation" above):

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
