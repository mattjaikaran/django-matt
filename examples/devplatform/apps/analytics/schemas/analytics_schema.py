from datetime import date, datetime

from pydantic import BaseModel


class DailyMetricSchema(BaseModel):
    date: date
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time_ms: float
    p95_response_time_ms: float
    total_bandwidth_bytes: int
    unique_ips: int

    model_config = {"from_attributes": True}


class UsageSummarySchema(BaseModel):
    total_requests: int
    total_bandwidth: int
    avg_response_time: float
    error_rate: float
    period_start: datetime
    period_end: datetime


class TimeSeriesPointSchema(BaseModel):
    timestamp: str
    value: float


class TimeSeriesSchema(BaseModel):
    metric: str
    data: list[TimeSeriesPointSchema]
