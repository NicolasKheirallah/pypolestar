# Python for Polestar

This library is not affiliated with nor supported by [Polestar](https://www.polestar.com).

> **This is a fork** ([pypolestar/pypolestar](https://github.com/pypolestar/pypolestar) is
> upstream) adding several best-effort, read-only gRPC services beyond battery and target SOC.
> See [CHANGELOG.md](CHANGELOG.md) for what's new, what's deliberately not included, and where
> the new field layouts came from.


## Data Models

Data models for returned information are described in [`pypolestar/models.py`](pypolestar/models.py)
(GraphQL) and [`pypolestar/grpc_models.py`](pypolestar/grpc_models.py) (gRPC).


## Example

```python
from pypolestar import PolestarApi

api = PolestarApi(username=USERNAME, password=PASSWORD, vins=[VIN])

# initialize API
await api.async_init()

# fetch latest telematics (contains both battery and odometer) for VIN
await api.update_latest_data(vin=VIN, update_telematics=True)

# get specific data for VIN
car_information = api.get_car_information(vin=VIN)
car_telematics = api.get_car_telematics(vin=VIN)

# gRPC: battery/target SOC (upstream) plus exterior, health, odometer, climate,
# availability, pre-cleaning, location, mycars, amp limit and charge schedule
# added in this fork -- see CHANGELOG.md
grpc_battery = api.get_grpc_battery(vin=VIN)
grpc_exterior = api.get_grpc_exterior(vin=VIN)  # doors/windows/locks, best-effort
grpc_mycars = api.get_grpc_mycars(vin=VIN)  # installed software version, live-verified
```


## Scope of this fork

The gRPC services added here are **read-only telemetry only** -- no remote/write commands
(lock, climate start, charge target, etc.) are implemented. Ten new services were added in
two ways:

- Seven (exterior, health, odometer, climate, availability, pre-cleaning, location) had their
  message field layout cross-referenced from public reverse-engineering projects rather than
  decompiled directly by this fork's author, then spot-checked live.
- Three (mycars, amp limit, charge schedule) were reverse-engineered directly against a real
  account by calling the known endpoint and decoding the raw response -- no external schema
  source existed for these.

All ten have been validated against one real Polestar 2 in a parked, idle state: odometer
cross-verified byte-for-byte against the existing GraphQL field, GPS correctly placed the car
in Gothenburg, `get_mycars` matched known VIN/model/plate exactly and surfaced the installed
software version (not available via GraphQL at all), and `get_charge_schedule` returned a real
23:00-06:00 overnight charging window. See [CHANGELOG.md](CHANGELOG.md) for the full validation
notes, what's still unverified (active charging/climate, other models, populated charge
locations), and the full list of what was investigated but deliberately not implemented, and
why.
