"""Data models for the Polestar gRPC API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .enum import ChargeTargetLevelSettingType, ChargingConnectionStatus, ChargingStatus, ChargingType


class GrpcBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class GrpcBatteryData(GrpcBaseModel):
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


class GrpcTargetSocData(GrpcBaseModel):
    """Target SOC (charge limit) from the gRPC API."""

    battery_charge_target_level: int | None
    charge_target_level_setting_type: ChargeTargetLevelSettingType
    pending_battery_charge_target_level: int | None
    pending_charge_target_level_setting_type: ChargeTargetLevelSettingType
