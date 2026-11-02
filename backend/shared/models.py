from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False, strict=True)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False, strict=True)]
Accuracy = Annotated[float, Field(ge=0, le=10000, allow_inf_nan=False, strict=True)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionRequest(StrictModel):
    installation_id: UUID


class RelatoRequest(StrictModel):
    id: UUID
    tipo: Literal["alagamento", "obstrucao"]
    gravidade: Literal["baixa", "media", "alta"]
    latitude: Latitude
    longitude: Longitude
    descricao: str = Field(default="", max_length=500)
    occurred_at: AwareDatetime
    position_source: Literal["gps", "manual", "demo"] = "manual"
    accuracy_m: Accuracy | None = None
    is_demo: bool = Field(default=False, strict=True)

    @field_validator("occurred_at", mode="before")
    @classmethod
    def timestamp_with_timezone(cls, value):
        if not isinstance(value, (str, datetime)):
            raise ValueError("Informe a data ISO 8601 com fuso horário")
        return value

    @field_validator("occurred_at")
    @classmethod
    def utc(cls, value):
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def demo_source(self):
        if self.position_source == "demo" and not self.is_demo:
            raise ValueError("Posição de demonstração deve ter is_demo=true")
        return self


class Point(StrictModel):
    latitude: Latitude
    longitude: Longitude


class RouteRequest(StrictModel):
    origem: Point
    destino: Point
    perfil: Literal["driving-car", "foot-walking"] = "driving-car"


class PositionRequest(Point):
    accuracy_m: Accuracy | None = None
    position_at: AwareDatetime
    radius_m: int = Field(default=1000, ge=100, le=10000)

    @field_validator("position_at", mode="before")
    @classmethod
    def valid_time(cls, value):
        if not isinstance(value, (str, datetime)):
            raise ValueError("Informe a data ISO 8601 com fuso horário")
        return value

    @field_validator("position_at")
    @classmethod
    def utc(cls, value):
        return value.astimezone(timezone.utc)


class PushRequest(StrictModel):
    token: str = Field(min_length=20, max_length=4096)
    platform: Literal["android", "ios", "web"]
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    position_at: AwareDatetime | None = None
    radius_m: int = Field(default=1000, ge=100, le=10000)

    @field_validator("position_at", mode="before")
    @classmethod
    def valid_time(cls, value):
        if value is not None and not isinstance(value, (str, datetime)):
            raise ValueError("Informe a data ISO 8601 com fuso horário")
        return value

    @field_validator("position_at")
    @classmethod
    def utc(cls, value):
        return value.astimezone(timezone.utc) if value else None

    @model_validator(mode="after")
    def complete_position(self):
        if any(v is not None for v in (self.latitude, self.longitude, self.position_at)) and any(v is None for v in (self.latitude, self.longitude, self.position_at)):
            raise ValueError("Posição exige latitude, longitude e position_at juntos")
        return self


class Subscription(Point):
    type: Literal["subscribe"]
    radius_m: int = Field(default=1000, ge=100, le=10000)


class Event(StrictModel):
    event_id: UUID
    schema_version: Literal[1] = 1
    tipo: Literal["relato.criado", "incidente.criado", "incidente.atualizado", "incidente.expirado"]
    aggregate_id: UUID
    aggregate_version: int = Field(ge=1)
    occurred_at: AwareDatetime
    region_id: str = Field(min_length=1, max_length=12)
    trace_id: UUID
    payload: dict
