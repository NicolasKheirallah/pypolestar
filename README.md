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
# availability, pre-cleaning and location added in this fork -- see CHANGELOG.md
grpc_battery = api.get_grpc_battery(vin=VIN)
grpc_exterior = api.get_grpc_exterior(vin=VIN)  # doors/windows/locks, best-effort
```


## Scope of this fork

The gRPC services added here are **read-only telemetry only** -- no remote/write commands
(lock, climate start, charge target, etc.) are implemented. Their message field layout was
cross-referenced from public reverse-engineering projects rather than decompiled directly by
this fork's author. All seven have been spot-checked against one real Polestar 2 in a parked,
idle state (odometer cross-verified byte-for-byte against the existing GraphQL field; GPS
correctly placed the car in Gothenburg) -- see [CHANGELOG.md](CHANGELOG.md) for the full
validation notes, what's still unverified (active charging/climate, other models), and the
full list of what was and wasn't implemented, and why.
