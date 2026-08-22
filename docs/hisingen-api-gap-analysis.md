# Hisingen &harr; pypolestar API gap analysis

Comparison of [Hisingen](https://github.com/NicolasKheirallah/Hisingen) (a macOS menu-bar app,
Swift, reverse-engineered Polestar + Volvo client) against pypolestar's current `main`/
`pr/grpc-telemetry` branch, restricted to the **Polestar** side of Hisingen (its Volvo-specific
files -- `VolvoAPI*.swift`, `VolvoModels.swift`, `BuiltinVolvoSecrets.swift` -- are out of scope;
pypolestar does not support Volvo).

Produced by reading, in full: `PolestarGRPC.swift` (767 lines), `PolestarGRPCCapabilities.swift`
(1221 lines), `PolestarGRPCRemote.swift` (546 lines), `PolestarAPI.swift` (1040 lines),
`PolestarAPI+Telemetry.swift` (360), `PolestarAPI+Capabilities.swift` (84),
`PolestarAPI+Authentication.swift` (167), `PolestarAPI+Transport.swift` (51),
`PolestarAPI+Commands.swift` (60), `GraphQLModels.swift` (330), `PolestarServiceError.swift` (134),
`VehicleServiceError.swift` (116), `ServiceErrorPolicy.swift` (20), plus `docs/api/*.md`
(excluding `volvo.md`), against pypolestar's `api.py`, `auth.py`, `graphql.py`, `grpc_client.py`,
`grpc_models.py`, `models.py`, `const.py`, `exceptions.py`.

## How to read the "Confidence" column

- **Verified** &mdash; observed working in production against a real account/vehicle (live capture,
  or a documented server error message that confirms the mechanism).
- **Strongly inferred** &mdash; a specific, detailed field-by-field schema exists in the source
  (decompiled or cross-referenced), with no live-test citation for this exact field, but internally
  consistent and specific enough to trust.
- **Corroborated** &mdash; cross-checked against a second, independent open-source implementation
  (e.g. `kildahldev/unofficial-polestar-api`).
- **Experimental** &mdash; heuristic/probing code in Hisingen itself (multiple candidate RPC paths,
  guessed field offsets, plausibility-range scanning). Hisingen's own comments flag these as
  unverified.
- **Unsupported** &mdash; a command/RPC that Hisingen explicitly does not implement for Polestar
  (Volvo-only or ICE-only).
- **Unknown** &mdash; referenced (e.g. by a capability flag) but the concrete RPC/schema was not
  present in the files read.

"Action" is one of: **Ported** (already in pypolestar before this analysis), **Implement**
(this pass), **Propose** (worth doing, deferred), **Experimental** (implement behind a clear
"unverified" label), **Exclude** (do not port, with reason).

---

## 1. Baseline already in pypolestar (preserve, do not regress)

| Capability | Backend | Service/RPC | Confidence | Action |
|---|---|---|---|---|
| Vehicle discovery, info, images | GraphQL | `getConsumerCarsV2`, `getCarImages` | Verified | Ported |
| Telematics (battery %, range, odometer, health) | GraphQL | `carTelematicsV2` | Verified | Ported |
| Battery incl. charger status/power/current/voltage | C3 gRPC | `BatteryService/GetLatestBattery` | Verified | Ported |
| Target SOC (read) | PCCS/Chronos | `TargetSocService/GetTargetSoc` | Verified | Ported |
| Exterior (doors/windows/locks/hood/tailgate/tank lid/sunroof/alarm) | C3 gRPC | `ExteriorService/GetLatestExterior` | Strongly inferred, spot-checked live | Ported |
| Health (tyre pressure + warnings, 21 light failures, fluids, service due) | C3 gRPC | `HealthService/GetHealth` | Strongly inferred, spot-checked live | Ported |
| Odometer + trip meters | C3 gRPC | `OdometerService/GetOdometer` | Strongly inferred, live-matched to GraphQL | Ported |
| Parking climate status | C3 gRPC | `ParkingClimatizationService/GetLatestParkingClimatization` | Strongly inferred | Ported |
| Availability (online/awake) | C3 gRPC | `AvailabilityService/GetLatestAvailability` | Strongly inferred | Ported |
| Pre-cleaning / CleanZone status | C3 gRPC | `PreCleaningService/GetPreCleaning` | Strongly inferred | Ported |
| Location (last parked) | C3 gRPC | `DtlInternetService/GetLastParkedLocation` | Verified (live GPS match) | Ported |
| Vehicle identity + installed SW version | C3 gRPC | `car_information.CarInformation/GetMyCars` | Verified (matched VIN/model/plate) | Ported |
| Charging current limit (read) | PCCS/Chronos | `AmpLimitService/GetAmpLimit` | Strongly inferred | Ported |
| Overnight charge schedule (read, hour-only) | PCCS/Chronos | `GlobalChargeTimerService/GetGlobalChargeTimerStream` | Strongly inferred, live-matched | Ported |

## 2. Capability discovery

| Capability | Hisingen | pypolestar | Backend | Service/RPC | Confidence | Action |
|---|---|---|---|---|---|---|
| Typed per-VIN capability model | Generic probe-and-cache wrapper over every gRPC call, plus a static model-derived fallback table; `GetMyCars` used *only* for OTA capability flags | `is_<x>_supported(vin)` per service (probe + permanent-refusal cache) already exists, matches Hisingen's runtime-probe layer | -- | -- | -- | Ported (architecturally equivalent) |
| Backend-reported capability flags: window/trunk/sunroof control, trunk unlock, charging functions, target-charge-level support, global amp-limit support, charge-now override, plug&charge, air-purification remote start, honk/flash type &rarr; honk/flash support | Parses `Car.Locks{5,6,7,10}`, `Car.Charging{1,8,9,15,29}`, `Car.AirPurification{1}`, `Car.honk_flash_type(16)` from the **same `GetMyCars` response** pypolestar already fetches for `get_mycars` | Not parsed; `GrpcMyCarsData`'s own docstring says "~80 more fields... not confidently namable" | C3 gRPC | `car_information.CarInformation/GetMyCars` (no new RPC call) | Strongly inferred (detailed field-by-field schema in Hisingen, no live-test citation for this exact response, no second-source cross-check) | **Implement** &mdash; zero extra network cost, directly answers "does this vehicle support command X" |
| OTA capability flags: `supportsUpdateStatus`, `supportsRemoteOtaInstallSchedule`, `supportsFullOtaUpdates`, `supportsCloudBasedOtaDownloadConsent`, `hasPerformanceSoftwareUpgrade` | `Car{32,33,57,62,70}`, same `GetMyCars` response | Not parsed | C3 gRPC | same as above | Strongly inferred | **Implement**, folded into the same capability model |
| Numeric charging bounds (amp min/max, target-SOC min) | `Charging` sub-message, used to validate command inputs client-side before sending | Not parsed | C3 gRPC | same as above | Strongly inferred | **Implement** &mdash; needed to validate `set_amp_limit`/`set_target_soc` inputs client-side per spec &sect;11/&sect;19 |

## 3. Software / OTA

| Capability | Hisingen | pypolestar | Backend | Service/RPC | Confidence | Action |
|---|---|---|---|---|---|---|
| Installed + advertised software version, update state, install duration, scheduled time | `fetchSoftware`/`parseSoftware`; state enum 0-15 pinned by two named unit tests, field 5 nested-message shape explicitly unit-tested | Only `installed_software_version` (via `GetMyCars`, not `GetSoftwareInfo`) | C3 gRPC | `ota_mobcache.OtaDiscoveryService/GetSoftwareInfo` | Strongly inferred (two cited unit tests) | **Implement** |
| Scheduled-install id/time as a second software-id source | `fetchSchedule`/`parseSchedule` | None | C3 gRPC | `ota_mobcache.SchedulerService/GetSchedule` | Strongly inferred (field layout given verbatim in comment) | **Implement** |
| Schedule OTA install | `minutes` bounds-checked client-side 2..10080, **verified live** (backend rejects out-of-range with an exact quoted `grpc-status 3` message); requires a fresh installable `software_id` (also live-verified rejection behavior) | None | C3 gRPC | `ota_mobcache.SchedulerService/Schedule` | Verified | **Implement**, capability-gated on `supportsRemoteOtaInstallSchedule` |
| Install OTA now | Same installability precondition as Schedule | None | C3 gRPC | `ota_mobcache.SchedulerService/InstallNow` | Verified precondition, request shape strongly inferred | **Implement**, capability-gated, flagged as high-impact/destructive |
| Cancel scheduled OTA | No installability precondition (can cancel from any state) | None | C3 gRPC | `ota_mobcache.SchedulerService/CancelSchedule` | Strongly inferred | **Implement** |
| OTA download consent | Referenced only via a capability flag (`supportsCloudBasedOtaDownloadConsent`); no request/response shape found in the files read | None | Unknown | Unknown | Unknown | **Exclude** &mdash; no evidence of the actual RPC, per &sect;14 do not invent one |

## 4. Charging

| Capability | Hisingen | pypolestar | Backend | Service/RPC | Confidence | Action |
|---|---|---|---|---|---|---|
| Set target SOC | Client-side floor `max(40, backend min)`; **explicit live-tested finding**: must send `ChargeTargetLevelSettingType.CUSTOM` not `DAILY`, or the backend accepts the request (`SYNCED`) but silently does not change the target | Not implemented; **proto for this RPC already exists in pypolestar** (`polestar_target_soc.proto`, `SetTargetSocRequest`/`SetTargetSocResponse`/`rpc SetTargetSoc`, predates this backport, reconstructed from APK decompilation) | PCCS/Chronos | `TargetSocService/SetTargetSoc` | Verified (the DAILY/CUSTOM finding), proto strongly inferred | **Implement** &mdash; primary access token, no new auth |
| Set charging current limit | Client-side bounds from `GetMyCars` (fallback 1..64A) | Not implemented | PCCS/Chronos | `AmpLimitService/SetAmpLimit` | Strongly inferred (same envelope as proven `GetAmpLimit`) | **Implement** |
| Charge-now override start/stop | Response parsing has an **undocumented asymmetric shape** (checks top-level field 1 before falling back to the standard envelope) | Not implemented | PCCS/Chronos | `ChargeNowService/StartOverrideChargeTimer`, `.../StopOverrideChargeTimer` | Strongly inferred, response shape only partially confirmed | **Implement**, flagged as lower-confidence response parsing |
| Set global (overnight) charge timer | Timezone offset uses the **caller's local timezone**, not the vehicle's &mdash; a real correctness issue for a server-side Python client running in a different timezone than the car | Not implemented (read-only today) | PCCS/Chronos | `GlobalChargeTimerService/SetGlobalChargeTimer` | Strongly inferred | **Implement**, must accept an explicit timezone/UTC offset parameter rather than assuming the host's local zone |
| Saved charge locations (read: id, alias, coordinates, amp limit, min SOC, optimised flag, type) | **Corroborated against `kildahldev/unofficial-polestar-api`** for fields 2,3,4,5,6,7,12 | Not implemented | PCCS/Chronos | `ChargeLocationService/GetChargeLocations` | Corroborated | **Implement** |
| Per-location charge/departure timers (fields 9,10,11) | Undocumented in Hisingen's own schema comment, inferred purely from code | Not implemented | PCCS/Chronos | same RPC, different sub-fields | Strongly inferred (weaker than the core location fields) | Propose &mdash; implement location core fields now, leave per-location timer sub-fields for a follow-up once corroborated |
| Create/rename/delete charge location, set its amp limit / min SOC / optimised flag | **Corroborated against kildahldev** for the shared per-location write shape | Not implemented | PCCS/Chronos | `ChargeLocationService/{CreateAtTheCarLocation,UpdateAlias,UpdateAmpLimit,UpdateMinimumSoc,UpdateOptimizedSetting,DeleteLocation}` | Corroborated | **Implement** |

## 5. Climate

| Capability | Hisingen | pypolestar | Backend | Service/RPC | Confidence | Action |
|---|---|---|---|---|---|---|
| Parking climate status, seat/steering-wheel heating, ventilation | Two wire shapes exist ("digital twin" vs "legacy"); pypolestar's single-shape parser was live-verified against a real Polestar 2 | Ported | C3 gRPC | `ParkingClimatizationService/GetLatestParkingClimatization` | Ported already works for the tested vehicle | Ported (no change) &mdash; note the alternate "legacy" shape as a documented risk, not implemented speculatively (&sect;44) |
| Climate timers (read: id, index, time, active, weekdays) | Ambiguous duplicate field numbers (3 **or** 4 both treated as the timer list, unexplained) | Not implemented | PCCS/Chronos | `ParkingClimateTimerService/GetTimers` | Strongly inferred, one documented ambiguity | **Implement**, both field numbers handled per Hisingen's own tolerant parsing |
| Set / delete climate timer | Delete uses a **different, undocumented response shape** (raw top-level field 1, not the standard envelope) than every other Chronos write in the file | Not implemented | PCCS/Chronos | `ParkingClimateTimerService/{SetTimers,DeleteTimer}` | Strongly inferred | **Implement**, delete flagged destructive |
| Start/stop climate remotely, seat/steering-wheel heating levels | Client-side temperature validation (16-30&deg;C, 0.5&deg; steps, or 0=auto); requires **command-token** auth (invocation-backed) | Not implemented | C3 gRPC (`invocation.InvocationService`) | `ClimatizationStart`, `ClimatizationStop` | Strongly inferred (wire shape confirmed by Hisingen unit test; semantic confirmation not annotated) | **Implement** as Tier 2 (needs new command-auth subsystem, see &sect;9) |

## 6. Exterior / vehicle state (write)

| Capability | Hisingen | pypolestar | Backend | Confidence | Action |
|---|---|---|---|---|---|
| Lock | field 2 always 0 | Not implemented | C3 (`invocation.InvocationService/Lock`) | Strongly inferred, no explicit live-verification comment for this specific command | **Implement**, Tier 2 |
| Unlock (full) / Unlock trunk only | field 2 = 0 (full) / 1 (trunk); wire shape **confirmed by Hisingen unit test** | Not implemented | C3 (`.../Unlock`) | Strongly inferred (wire-format test only, not server-semantics) | **Implement**, Tier 2 |
| Open/close tailgate | Enum `TailgateControlType` with explicit numeric values in a comment (transcribed, not live-verified) | Not implemented | C3 (`.../TailgateControl`) | Strongly inferred | **Implement**, Tier 2 |
| Open/close windows | Bare integers (1=open, 2=close), **no decompilation comment, no live-verification** &mdash; the weakest-evidenced action-code mapping in the whole command set | Not implemented | C3 (`.../WindowControl`) | Strongly inferred but explicitly flagged lower-confidence by the research agent | **Implement**, Tier 2, labeled experimental in docstrings |
| Flash / honk+flash / honk only | Bare integers, same caveat as windows | Not implemented | C3 (`.../HonkFlash`) | Strongly inferred, lower-confidence action codes | **Implement**, Tier 2, labeled experimental |
| Start/stop pre-cleaning | field 2 = 1/0 | Not implemented | C3 (`.../PreCleaning`) | Strongly inferred | **Implement**, Tier 2 |

## 7. GraphQL

| Finding | Detail | Action |
|---|---|---|
| `chargingStatusV2` numeric fallback | Hisingen defensively maps raw digit-strings `"0"`-`"6"` to the same enum in addition to the named-string form; pypolestar's `CarBatteryData.from_dict` only matches two literal strings (`CHARGING_STATUS_V2_IDLE`/`_CHARGING`) and silently returns `None` for anything else, including a bare digit | **Implement** &mdash; small, safe, well-evidenced fix |
| `carTelematicsV2.health` sub-object (service/fluid warnings) | Present in Hisingen's query | Already requested and parsed by pypolestar's `QUERY_TELEMATICS_V2` | Ported (no change) |
| Second discovery source: `vdms { getVehiclesInformation }` (trim/color/interior/wheels/packages) | Separate GraphQL host (`app-backend`, not `mystar-v2`), separate auth header scheme (`X-PolestarId-Authorization` + Apollo-Kotlin client-identification headers spoofing the Android app) | pypolestar has no equivalent; `getConsumerCarsV2` doesn't return trim/color data at all | **Propose**, deferred &mdash; genuinely new transport surface (different host + header scheme), not just a new query; out of scope for this pass given time budget, revisit separately |
| `getCarImages` `interior` field | Hisingen's own query never requests it despite probing for it in the response &mdash; looks like dead/vestigial code in Hisingen itself | N/A | **Exclude** &mdash; nothing to port, flagged only for completeness |
| GraphQL mutations | None exist in Hisingen; all writes are gRPC-only | N/A | N/A |

## 8. Location, connectivity, weather, vehicle errors

| Capability | Hisingen | pypolestar | Confidence | Action |
|---|---|---|---|---|
| Location (last parked) | 5 candidate RPC paths probed in order, response field offsets guessed (6 candidates tried per path), coordinate scale (E6 vs E7) guessed by magnitude, heading/speed/altitude/accuracy/gear all guessed by plausibility-range scanning across candidate field numbers | pypolestar's own `DtlInternetService/GetLastParkedLocation` (a *different* RPC than Hisingen's primary candidate) was live-tested and matched the real GPS position exactly | pypolestar: Verified. Hisingen: Experimental | Ported (pypolestar's own version); **Exclude** Hisingen's heading/speed/altitude/accuracy/gear fields &mdash; explicitly heuristic per &sect;15, no confirmed field for any of them |
| Connectivity diagnostics (network type, signal, wake reason) | Reuses `DashboardService/GetLatestDashboard`; no schema-provenance comment at all | Not implemented | Experimental (no confidence annotation in source) | **Exclude** for this pass &mdash; no defensible evidence bar met; revisit if/when corroborated |
| Weather | Primary path is a **non-Polestar third-party REST API** (Open-Meteo); gRPC candidates are explicitly described by Hisingen as vestigial fallback | Not implemented | Experimental / non-Polestar | **Exclude** &mdash; out of scope per &sect;17 (external weather-provider data explicitly excluded) |
| Vehicle/Chronos errors | RPC path has an internal contradiction in Hisingen itself (comment says PCCS host, code calls C3 host) | Not implemented | Experimental (self-contradictory in source) | **Exclude** for this pass, flagged as remaining research |

## 9. Authentication for remote commands

Hisingen requires a **second OAuth2/PKCE client** for every `invocation.InvocationService`-backed
command (lock, unlock, tailgate, windows, honk/flash, climate start/stop, pre-cleaning):

- Client ID `lp8dyrd_10` (vs. the normal `l3oopkc_10` pypolestar already uses for everything else),
  redirect URI `polestar-explore://explore.polestar.com` (a custom URL scheme, not the HTTPS
  callback pypolestar's scripted login uses today).
- **Verified live**: the backend refuses invocation commands from the primary client with an exact
  quoted error (`Client id l3oopkc_10 is not a required client id: [... lp8dyrd_10 ...]`) &mdash;
  this is gating by client-ID allowlist, not by OAuth scope.
- Obtained via a real system-browser consent flow (not the scripted PingFederate form-fill
  pypolestar's `auth.py` uses), because the app deliberately never sees the password for this flow.
- Independent refresh-token lifecycle, single-flight guarded against refresh-token-rotation races
  (a live-observed bug in Hisingen's own history).
- **OTA and Chronos/PCCS commands (target SOC, amp limit, charge-now, global timer, climate
  timers, charge locations) do NOT need this second token** &mdash; they work with the ordinary
  access token pypolestar already has.

**Action:** Implement a new, explicitly opt-in `PolestarCommandAuth` flow mirroring Hisingen's
two-step dance (`get_authorization_url()` returning a URL for the *caller* to open in a real
browser, `complete_authorization(callback_url)` to exchange the resulting code) so a consuming
application (e.g. Home Assistant, via its own OAuth external-step / application-credentials
plumbing) can drive it. Until a caller completes this flow, every invocation-backed command method
raises a dedicated `PolestarCommandAuthorizationRequiredError` rather than silently failing or
attempting the scripted-login path against it (which would not work &mdash; this flow is
architecturally different, not just a second password).

## 10. Error model

Hisingen distinguishes (see `PolestarServiceError.swift` + gRPC `commandError` status mapping):

| gRPC status | Hisingen category | Proposed pypolestar exception |
|---|---|---|
| `PERMISSION_DENIED` / `UNIMPLEMENTED` / `NOT_FOUND` (read) | permanently unsupported for this vehicle | `PolestarUnsupportedError` (pypolestar already caches this via `unsupported_*` sets; formalize as a raised type where callers need a signal rather than `None`) |
| `INVALID_ARGUMENT` / `FAILED_PRECONDITION` (write) | command rejected | `PolestarCommandRejectedError` |
| `UNAUTHENTICATED` (write, invocation) | needs command-client auth | `PolestarCommandAuthorizationRequiredError` |
| `UNAUTHENTICATED` (read) / HTTP 401 | session expired | existing `PolestarNotAuthorizedException` |
| `RESOURCE_EXHAUSTED` / HTTP 429 | rate limited | `PolestarRateLimitError` (new; pypolestar has no equivalent today) |
| `DEADLINE_EXCEEDED` / timeout | timeout, not a command failure | `PolestarTimeoutError` (new) |
| malformed/undecodable response | protocol error | `PolestarProtocolError` (new) |

**Action:** Implement this hierarchy in `exceptions.py`, all inheriting `PolestarApiException`,
each wrapping the original `grpc.aio.AioRpcError`/`httpx` exception via `raise ... from exc`
(exception chaining) rather than replacing pypolestar's existing exceptions (backward compatible).

## 11. Priority summary

1. **Capability discovery** (&sect;2) &mdash; zero new network calls, highest value.
2. **Exception hierarchy** (&sect;10) &mdash; needed before commands can report status sanely.
3. **OTA read** (&sect;3, read parts).
4. **Charging writes usable today**: `SetTargetSoc`, `SetAmpLimit`, charge-now override, global
   charge timer write (&sect;4) &mdash; primary token, no new auth.
5. **Charge locations** (read + CRUD) and **climate timers** (read + set/delete) (&sect;4, &sect;5)
   &mdash; primary token, no new auth.
6. **OTA writes**: schedule/install-now/cancel (&sect;3) &mdash; primary token, `InstallNow` flagged
   destructive.
7. **Command-client OAuth subsystem** (&sect;9) &mdash; prerequisite for everything in Tier 2.
8. **Invocation commands**: lock/unlock/tailgate/windows/honk-flash/climate-start-stop/pre-cleaning
   (&sect;6, &sect;5 write part) &mdash; highest risk (control real hardware), gated on 7.
9. **GraphQL `chargingStatusV2` fix** (&sect;7) &mdash; small, safe, do opportunistically.
10. Deferred: VDMS discovery query (&sect;7), connectivity diagnostics, vehicle errors, OTA
    download consent (all &sect;8/&sect;3 exclusions) &mdash; insufficient evidence or disproportionate
    new transport surface for the value, revisit if better evidence emerges.
