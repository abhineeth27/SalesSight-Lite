from __future__ import annotations

import io
import math
import re
import uuid
from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd
from fastapi import HTTPException, UploadFile
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error

from schemas import (
    AnalysisResponse,
    DailyRevenuePoint,
    ForecastEvaluation,
    ForecastPoint,
    ForecastResult,
    KPIValues,
    ProductRevenuePoint,
)

MAX_FILE_BYTES = 5 * 1024 * 1024
REQUIRED_COLUMNS = ["date", "order_id", "product", "quantity", "unit_price"]
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
INTEGER_PATTERN = re.compile(r"^[+]?[0-9]+$")
FORECAST_ASSUMPTION = (
    "Missing calendar dates between the first and last sale are treated as zero-revenue days."
)
FORECAST_LIMITATION = (
    "This basic linear trend does not model seasonality, holidays, promotions, or external factors."
)


def _round_money(value: float) -> float:
    return round(float(value), 2)


def _validation_error(issues: dict[str, list[int] | str]) -> HTTPException:
    examples: list[dict[str, Any]] = []
    for issue, rows in issues.items():
        if isinstance(rows, str):
            examples.append({"issue": issue, "detail": rows})
        else:
            examples.append({"issue": issue, "example_rows": rows[:5]})
    return HTTPException(
        status_code=422,
        detail={
            "message": "The CSV could not be validated. Fix the listed values and try again.",
            "errors": examples,
        },
    )


async def read_and_validate_csv(upload: UploadFile) -> pd.DataFrame:
    filename = upload.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Please upload a file with a .csv extension.")

    raw = await upload.read(MAX_FILE_BYTES + 1)
    await upload.close()
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="CSV files must be 5 MB or smaller.")
    if not raw:
        raise HTTPException(status_code=422, detail="The uploaded CSV file is empty.")

    try:
        frame = pd.read_csv(
            io.BytesIO(raw),
            dtype=str,
            keep_default_na=False,
            encoding="utf-8-sig",
        )
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="The CSV must use UTF-8 text encoding.") from exc
    except pd.errors.ParserError as exc:
        raise HTTPException(status_code=422, detail=f"The CSV structure is invalid: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail="The CSV could not be read.") from exc

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise _validation_error({"Missing required columns": ", ".join(missing)})
    if frame.empty:
        raise HTTPException(status_code=422, detail="The CSV contains headers but no data rows.")

    # Extra columns are intentionally ignored; identical rows remain untouched.
    frame = frame[REQUIRED_COLUMNS].copy()
    issues: dict[str, list[int]] = defaultdict(list)
    parsed_dates: list[pd.Timestamp | None] = []
    parsed_quantities: list[int | None] = []
    parsed_prices: list[float | None] = []

    for index, row in frame.iterrows():
        csv_row = int(index) + 2
        date_text = str(row["date"]).strip()
        parsed_date: pd.Timestamp | None = None
        if DATE_PATTERN.fullmatch(date_text):
            candidate = pd.to_datetime(date_text, format="%Y-%m-%d", errors="coerce")
            if not pd.isna(candidate):
                parsed_date = candidate
        if parsed_date is None:
            issues["date must be a valid YYYY-MM-DD value"].append(csv_row)
        parsed_dates.append(parsed_date)

        order_id = str(row["order_id"]).strip()
        product = str(row["product"]).strip()
        if not order_id:
            issues["order_id must not be empty"].append(csv_row)
        if not product:
            issues["product must not be empty"].append(csv_row)
        frame.at[index, "order_id"] = order_id
        frame.at[index, "product"] = product

        quantity_text = str(row["quantity"]).strip()
        quantity: int | None = None
        if INTEGER_PATTERN.fullmatch(quantity_text):
            candidate_quantity = int(quantity_text)
            if candidate_quantity > 0:
                quantity = candidate_quantity
        if quantity is None:
            issues["quantity must be a positive integer"].append(csv_row)
        parsed_quantities.append(quantity)

        price_text = str(row["unit_price"]).strip()
        price: float | None = None
        try:
            candidate_price = float(price_text)
            if math.isfinite(candidate_price) and candidate_price >= 0:
                price = candidate_price
        except (TypeError, ValueError):
            pass
        if price is None:
            issues["unit_price must be a finite, nonnegative number"].append(csv_row)
        parsed_prices.append(price)

    if issues:
        raise _validation_error(issues)

    frame["date"] = pd.to_datetime(parsed_dates)
    frame["quantity"] = pd.Series(parsed_quantities, dtype="int64")
    frame["unit_price"] = pd.Series(parsed_prices, dtype="float64")

    conflicting_orders = frame.groupby("order_id", sort=False)["date"].nunique()
    conflicting_ids = set(conflicting_orders[conflicting_orders > 1].index)
    if conflicting_ids:
        rows = [
            int(index) + 2
            for index, order_id in frame["order_id"].items()
            if order_id in conflicting_ids
        ]
        raise _validation_error({"all rows for an order_id must use the same date": rows})

    return frame


def analyze_frame(frame: pd.DataFrame, filename: str) -> tuple[AnalysisResponse, dict[str, Any]]:
    data = frame.copy()
    data["revenue"] = data["quantity"] * data["unit_price"]

    total_revenue = float(data["revenue"].sum())
    total_orders = int(data["order_id"].nunique())
    average_order_value = total_revenue / total_orders if total_orders else 0.0
    units_sold = int(data["quantity"].sum())

    first_date = data["date"].min()
    last_date = data["date"].max()
    calendar_index = pd.date_range(first_date, last_date, freq="D")
    daily_series = (
        data.groupby("date")["revenue"].sum().reindex(calendar_index, fill_value=0.0).astype(float)
    )
    daily_points = [
        DailyRevenuePoint(date=index.strftime("%Y-%m-%d"), revenue=_round_money(value))
        for index, value in daily_series.items()
    ]

    product_series = data.groupby("product")["revenue"].sum().sort_values(ascending=False).head(5)
    top_products = [
        ProductRevenuePoint(product=str(product), revenue=_round_money(value))
        for product, value in product_series.items()
    ]

    forecast = _build_forecast(daily_series)
    analysis_id = uuid.uuid4().hex
    kpis = KPIValues(
        total_revenue=_round_money(total_revenue),
        total_orders=total_orders,
        average_order_value=_round_money(average_order_value),
        units_sold=units_sold,
    )
    response = AnalysisResponse(
        analysis_id=analysis_id,
        filename=filename,
        row_count=len(data),
        date_start=first_date.strftime("%Y-%m-%d"),
        date_end=last_date.strftime("%Y-%m-%d"),
        calendar_days=len(daily_series),
        kpis=kpis,
        daily_revenue=daily_points,
        top_products=top_products,
        forecast=forecast,
    )
    summary = _build_llm_summary(response, daily_series)
    return response, summary


def _build_forecast(daily: pd.Series) -> ForecastResult:
    if len(daily) < 30:
        return ForecastResult(
            available=False,
            reason=f"At least 30 calendar days are required; this dataset has {len(daily)}.",
            assumption=FORECAST_ASSUMPTION,
            limitation=FORECAST_LIMITATION,
        )

    x = np.arange(len(daily), dtype=float).reshape(-1, 1)
    y = daily.to_numpy(dtype=float)
    split_index = len(daily) - 7

    evaluation_model = LinearRegression().fit(x[:split_index], y[:split_index])
    holdout_predictions = np.maximum(evaluation_model.predict(x[split_index:]), 0.0)
    mae = float(mean_absolute_error(y[split_index:], holdout_predictions))
    baseline_predictions = np.full(7, float(y[:split_index].mean()))
    baseline_mae = float(mean_absolute_error(y[split_index:], baseline_predictions))

    final_model = LinearRegression().fit(x, y)
    future_x = np.arange(len(daily), len(daily) + 7, dtype=float).reshape(-1, 1)
    future_values = np.maximum(final_model.predict(future_x), 0.0)
    future_dates = pd.date_range(daily.index[-1] + pd.Timedelta(days=1), periods=7, freq="D")
    predictions = [
        ForecastPoint(date=date.strftime("%Y-%m-%d"), predicted_revenue=_round_money(value))
        for date, value in zip(future_dates, future_values, strict=True)
    ]

    return ForecastResult(
        available=True,
        assumption=FORECAST_ASSUMPTION,
        limitation=FORECAST_LIMITATION,
        predictions=predictions,
        evaluation=ForecastEvaluation(
            holdout_days=7,
            mae=_round_money(mae),
            baseline_mae=_round_money(baseline_mae),
            model_better_than_baseline=mae < baseline_mae,
            explanation="MAE is the average absolute prediction error on the last 7 historical days; lower is better.",
        ),
    )


def _build_llm_summary(response: AnalysisResponse, daily: pd.Series) -> dict[str, Any]:
    recent_comparison: dict[str, float] | None = None
    if len(daily) >= 14:
        recent_comparison = {
            "recent_7_day_revenue": _round_money(daily.iloc[-7:].sum()),
            "preceding_7_day_revenue": _round_money(daily.iloc[-14:-7].sum()),
        }

    forecast_summary: dict[str, Any] | None = None
    if response.forecast.available and response.forecast.evaluation:
        forecast_summary = {
            "predicted_next_7_day_total": _round_money(
                sum(item.predicted_revenue for item in response.forecast.predictions)
            ),
            "holdout_mae": response.forecast.evaluation.mae,
            "baseline_mae": response.forecast.evaluation.baseline_mae,
            "model_better_than_baseline": response.forecast.evaluation.model_better_than_baseline,
        }

    return {
        "currency": "INR",
        "date_range": {"start": response.date_start, "end": response.date_end},
        "kpis": response.kpis.model_dump(),
        "top_products": [item.model_dump() for item in response.top_products],
        "recent_period_comparison": recent_comparison,
        "basic_trend_forecast": forecast_summary,
    }

