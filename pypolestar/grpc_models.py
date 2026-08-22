"""Data models for the Polestar gRPC API."""

from dataclasses import dataclass, field
from datetime import datetime

from .models import (
    BrakeFluidLevelWarning,
    ChargingConnectionStatus,
    ChargingStatus,
    EngineCoolantLevelWarning,
    OilLevelWarning,
    ServiceWarning,
    StrEnumOptional,
)


class ChargingType(StrEnumOptional):
    CHARGING_TYPE_UNSPECIFIED = "Unspecified"
    CHARGING_TYPE_NONE = "None"
    CHARGING_TYPE_AC = "AC"
    CHARGING_TYPE_DC = "DC"
    CHARGING_TYPE_WIRELESS = "Wireless"


class ChargeTargetLevelSettingType(StrEnumOptional):
    CHARGE_TARGET_LEVEL_SETTING_TYPE_UNSPECIFIED = "Unspecified"
    DAILY = "Daily"
    LONG_TRIP = "Long Trip"
    CUSTOM = "Custom"


@dataclass(frozen=True)
class GrpcBatteryData:
    """Battery data from the gRPC API (richer than GraphQL)."""

    charger_connection_status: ChargingConnectionStatus
    charging_status: ChargingStatus
    battery_charge_level_percentage: float | None
    estimated_distance_to_empty_km: int | None
    estimated_charging_time_to_full_minutes: int | None
    charging_power_watts: int | None
    charging_current_amps: int | None
    charging_voltage_volts: int | None
    charging_type: ChargingType
    average_energy_consumption_kwh_per_100km: float | None
    estimated_charging_time_minutes_to_target_distance: int | None
    estimated_charging_time_minutes_to_minimum_soc: int | None
    timestamp: datetime | None


@dataclass(frozen=True)
class GrpcTargetSocData:
    """Target SOC (charge limit) from the gRPC API."""

    battery_charge_target_level: int | None
    charge_target_level_setting_type: ChargeTargetLevelSettingType
    pending_battery_charge_target_level: int | None
    pending_charge_target_level_setting_type: ChargeTargetLevelSettingType


# --------------------------------------------------------------------------
# Everything below is best-effort: field layout cross-referenced from public
# reverse-engineering projects rather than pypolestar's own decompilation.
# Not yet validated against a live vehicle. See CHANGELOG.md for sources.
# --------------------------------------------------------------------------


class LockStatus(StrEnumOptional):
    LOCK_STATUS_UNSPECIFIED = "Unspecified"
    LOCK_STATUS_UNLOCKED = "Unlocked"
    LOCK_STATUS_LOCKED = "Locked"


class OpenStatus(StrEnumOptional):
    OPEN_STATUS_UNSPECIFIED = "Unspecified"
    OPEN_STATUS_OPEN = "Open"
    OPEN_STATUS_CLOSED = "Closed"
    OPEN_STATUS_AJAR = "Ajar"


class AlarmStatus(StrEnumOptional):
    ALARM_STATUS_UNSPECIFIED = "Unspecified"
    ALARM_STATUS_IDLE = "Idle"
    ALARM_STATUS_TRIGGERED = "Triggered"


@dataclass(frozen=True)
class GrpcExteriorData:
    """Doors, windows, locks and related exterior state from the gRPC API.

    Not available through GraphQL at all today.
    """

    central_lock: LockStatus
    tailgate_lock: LockStatus
    front_left_door: OpenStatus
    front_right_door: OpenStatus
    rear_left_door: OpenStatus
    rear_right_door: OpenStatus
    front_left_window: OpenStatus
    front_right_window: OpenStatus
    rear_left_window: OpenStatus
    rear_right_window: OpenStatus
    hood: OpenStatus
    tailgate: OpenStatus
    tank_lid: OpenStatus
    sunroof: OpenStatus
    alarm: AlarmStatus
    timestamp: datetime | None


class TyrePressureWarning(StrEnumOptional):
    TYRE_PRESSURE_WARNING_UNSPECIFIED = "Unspecified"
    TYRE_PRESSURE_WARNING_NO_WARNING = "No Warning"
    TYRE_PRESSURE_WARNING_VERY_LOW_PRESSURE = "Very Low Pressure"
    TYRE_PRESSURE_WARNING_LOW_PRESSURE = "Low Pressure"
    TYRE_PRESSURE_WARNING_HIGH_PRESSURE = "High Pressure"


class ExteriorLightWarning(StrEnumOptional):
    EXTERIOR_LIGHT_WARNING_UNSPECIFIED = "Unspecified"
    EXTERIOR_LIGHT_WARNING_NO_WARNING = "No Warning"
    EXTERIOR_LIGHT_WARNING_FAILURE = "Failure"


class WasherFluidLevelWarning(StrEnumOptional):
    WASHER_FLUID_LEVEL_WARNING_UNSPECIFIED = "Unspecified"
    WASHER_FLUID_LEVEL_WARNING_NO_WARNING = "No Warning"
    WASHER_FLUID_LEVEL_WARNING_TOO_LOW = "Too Low"


class LowVoltageBatteryWarning(StrEnumOptional):
    LOW_VOLTAGE_BATTERY_WARNING_UNSPECIFIED = "Unspecified"
    LOW_VOLTAGE_BATTERY_WARNING_NO_WARNING = "No Warning"
    LOW_VOLTAGE_BATTERY_WARNING_TOO_LOW = "Too Low"


@dataclass(frozen=True)
class GrpcHealthData:
    """Per-tyre pressure and light-failure warnings from the gRPC HealthService.

    Richer than the GraphQL carTelematicsV2.health query, which only reports
    brake fluid / coolant / oil / overall service warnings. The four
    overlapping warning types reuse pypolestar.models' GraphQL enums
    (extended with the extra values gRPC reports) rather than duplicating
    them.
    """

    days_to_service: int | None
    distance_to_service_km: int | None
    engine_hours_to_service: int | None
    service_warning: ServiceWarning
    brake_fluid_level_warning: BrakeFluidLevelWarning
    engine_coolant_level_warning: EngineCoolantLevelWarning
    oil_level_warning: OilLevelWarning
    washer_fluid_level_warning: WasherFluidLevelWarning
    low_voltage_battery_warning: LowVoltageBatteryWarning
    front_left_tyre_pressure_warning: TyrePressureWarning
    front_right_tyre_pressure_warning: TyrePressureWarning
    rear_left_tyre_pressure_warning: TyrePressureWarning
    rear_right_tyre_pressure_warning: TyrePressureWarning
    front_left_tyre_pressure_kpa: float | None
    front_right_tyre_pressure_kpa: float | None
    rear_left_tyre_pressure_kpa: float | None
    rear_right_tyre_pressure_kpa: float | None
    front_tyres_reference_pressure_kpa: float | None
    rear_tyres_reference_pressure_kpa: float | None
    exterior_light_warnings: dict[str, ExteriorLightWarning] = field(default_factory=dict)
    timestamp: datetime | None = None


@dataclass(frozen=True)
class GrpcOdometerData:
    """Trip meters and average speed from the gRPC OdometerService.

    Not available through GraphQL: CarOdometerData has fields for these but
    they are always None there today.
    """

    odometer_meters: int | None
    trip_meter_manual_km: float | None
    trip_meter_automatic_km: float | None
    trip_meter_since_charge_km: float | None
    average_speed_km_per_hour: int | None
    average_speed_km_per_hour_automatic: int | None
    average_speed_km_per_hour_since_charge: int | None
    timestamp: datetime | None


class ClimateRunningStatus(StrEnumOptional):
    RUNNING_STATUS_UNSPECIFIED = "Unspecified"
    RUNNING_STATUS_ON = "On"
    RUNNING_STATUS_OFF = "Off"
    RUNNING_STATUS_PENDING = "Pending"


class MainClimateRunningStatus(StrEnumOptional):
    MAIN_CLIMATE_RUNNING_STATUS_UNSPECIFIED = "Unspecified"
    MAIN_CLIMATE_RUNNING_STATUS_ON = "On"
    MAIN_CLIMATE_RUNNING_STATUS_OFF = "Off"


class HeatingIntensity(StrEnumOptional):
    HEATING_INTENSITY_UNSPECIFIED = "Unspecified"
    HEATING_INTENSITY_OFF = "Off"
    HEATING_INTENSITY_LOW = "Low"
    HEATING_INTENSITY_MEDIUM = "Medium"
    HEATING_INTENSITY_HIGH = "High"


class Ventilation(StrEnumOptional):
    VENTILATION_UNSPECIFIED = "Unspecified"
    VENTILATION_COOLING = "Cooling"
    VENTILATION_HEATING = "Heating"
    VENTILATION_NEUTRAL = "Neutral"


@dataclass(frozen=True)
class GrpcClimateData:
    """Parking climatization status from the gRPC ParkingClimatizationService.

    Not available through GraphQL at all today.
    """

    running_status: ClimateRunningStatus
    main_climate_running_status: MainClimateRunningStatus
    ventilation: Ventilation
    runtime_left_minutes: int | None
    current_compartment_temperature_celsius: float | None
    requested_compartment_temperature_celsius: float | None
    requested_front_left_seat: HeatingIntensity
    requested_front_right_seat: HeatingIntensity
    requested_rear_left_seat: HeatingIntensity
    requested_rear_right_seat: HeatingIntensity
    requested_steering_wheel_heating: HeatingIntensity
    started_at: datetime | None
    ending_at: datetime | None
    timestamp: datetime | None


class AvailabilityStatus(StrEnumOptional):
    AVAILABILITY_STATUS_UNSPECIFIED = "Unspecified"
    AVAILABILITY_STATUS_AVAILABLE = "Available"
    AVAILABILITY_STATUS_UNAVAILABLE = "Unavailable"


class UnavailableReason(StrEnumOptional):
    UNAVAILABLE_REASON_UNSPECIFIED = "Unspecified"
    UNAVAILABLE_REASON_NO_INTERNET = "No Internet"
    UNAVAILABLE_REASON_POWER_SAVING_MODE = "Power Saving Mode"
    UNAVAILABLE_REASON_CAR_IN_USE = "Car In Use"
    UNAVAILABLE_REASON_OTA_INSTALLATION_IN_PROGRESS = "OTA Installation In Progress"
    UNAVAILABLE_REASON_STOLEN_VEHICLE_TRACKING_IN_PROGRESS = "Stolen Vehicle Tracking In Progress"
    UNAVAILABLE_REASON_SERVICE_MODE_ACTIVE = "Service Mode Active"


class UsageMode(StrEnumOptional):
    USAGE_MODE_UNSPECIFIED = "Unspecified"
    USAGE_MODE_ABANDONED = "Abandoned"
    USAGE_MODE_INACTIVE = "Inactive"
    USAGE_MODE_CONVENIENCE = "Convenience"
    USAGE_MODE_ACTIVE = "Active"
    USAGE_MODE_DRIVING = "Driving"
    USAGE_MODE_ENGINE_ON = "Engine On"
    USAGE_MODE_ENGINE_OFF = "Engine Off"


@dataclass(frozen=True)
class GrpcAvailabilityData:
    """Online/awake state from the gRPC AvailabilityService.

    Reflects whether the vehicle's connectivity currently allows fresh data
    or commands to reach it -- not whether it is locked, charging, etc.
    """

    availability_status: AvailabilityStatus
    unavailable_reason: UnavailableReason
    usage_mode: UsageMode
    timestamp: datetime | None


class PreCleaningRunningStatus(StrEnumOptional):
    RUNNING_STATUS_UNSPECIFIED = "Unspecified"
    RUNNING_STATUS_ON = "On"
    RUNNING_STATUS_OFF = "Off"
    RUNNING_STATUS_PENDING = "Pending"


@dataclass(frozen=True)
class GrpcPreCleaningData:
    """Cabin air pre-cleaning ("CleanZone") status from the gRPC PreCleaningService."""

    running_status: PreCleaningRunningStatus
    runtime_left_minutes: int | None
    measured_air_quality_index: int | None
    measured_particulate_matter_25: int | None
    last_cycle_valid: bool | None
    started_at: datetime | None
    ending_at: datetime | None
    timestamp: datetime | None


@dataclass(frozen=True)
class GrpcLocationData:
    """Last known GPS location from the gRPC DtlInternetService.

    Not available through GraphQL at all today. `stale` reflects the
    backend's own freshness flag, not an age computed by pypolestar.
    """

    latitude: float | None
    longitude: float | None
    stale: bool | None
    timestamp: datetime | None
