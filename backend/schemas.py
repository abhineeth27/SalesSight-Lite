from typing import Literal

from pydantic import BaseModel, Field


class KPIValues(BaseModel):
    total_revenue: float
    total_orders: int
    average_order_value: float
    units_sold: int


class DailyRevenuePoint(BaseModel):
    date: str
    revenue: float


class ProductRevenuePoint(BaseModel):
    product: str
    revenue: float


class ForecastPoint(BaseModel):
    date: str
    predicted_revenue: float


class ForecastEvaluation(BaseModel):
    holdout_days: int
    mae: float
    baseline_mae: float
    model_better_than_baseline: bool
    explanation: str


class ForecastResult(BaseModel):
    available: bool
    label: Literal["Basic trend forecast"] = "Basic trend forecast"
    reason: str | None = None
    assumption: str
    limitation: str
    predictions: list[ForecastPoint] = Field(default_factory=list)
    evaluation: ForecastEvaluation | None = None


class AnalysisResponse(BaseModel):
    analysis_id: str
    filename: str
    row_count: int
    date_start: str
    date_end: str
    calendar_days: int
    kpis: KPIValues
    daily_revenue: list[DailyRevenuePoint]
    top_products: list[ProductRevenuePoint]
    forecast: ForecastResult


class InsightRequest(BaseModel):
    analysis_id: str = Field(min_length=1, max_length=64)


class InsightResponse(BaseModel):
    analysis_id: str
    insight: str
    cached: bool


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"

