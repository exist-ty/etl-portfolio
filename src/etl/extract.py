import logging
from datetime import date
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

REQUIRED_COLUMNS = {
    "customers": {"customer_id", "name", "email", "city", "signup_date", "channel"},
    "products": {"product_id", "name", "category", "price"},
    "orders": {"order_id", "customer_id", "product_id", "quantity", "order_date"},
    "marketing_spend": {"channel", "spend_month", "leads", "spend"},
}


def _read_csv(name: str) -> pd.DataFrame:
    path = RAW_DIR / f"{name}.csv"
    df = pd.read_csv(path)

    missing = REQUIRED_COLUMNS[name] - set(df.columns)
    if missing:
        raise ValueError(f"{name}.csv missing required columns: {missing}")

    logger.info("Extracted %s: %d rows", name, len(df))
    return df


def extract_all() -> dict[str, pd.DataFrame]:
    return {
        "customers": _read_csv("customers"),
        "products": _read_csv("products"),
        "orders": _read_csv("orders"),
        "marketing_spend": _read_csv("marketing_spend"),
    }


def extract_orders_window(data_interval_start: date, data_interval_end: date) -> pd.DataFrame:
    """Забирает только заказы с order_date в [data_interval_start, data_interval_end)
    — имитирует `WHERE order_date >= {{ data_interval_start }} AND order_date <
    {{ data_interval_end }}` против живого источника. Реальный источник здесь —
    статичный orders.csv (весь 2025 год заморожен, см. README), но фильтрация
    по этому же условию воспроизводит ровно то поведение, которое проверяет
    watermark-логику в src/etl/pipeline.py::run_incremental — иначе backfill
    был бы неотличим от полной перезаливки одним большим окном."""
    df = _read_csv("orders")
    order_date = pd.to_datetime(df["order_date"])
    mask = (order_date >= pd.Timestamp(data_interval_start)) & (order_date < pd.Timestamp(data_interval_end))
    windowed = df[mask].copy()
    logger.info(
        "Extracted orders window [%s, %s): %d rows", data_interval_start, data_interval_end, len(windowed)
    )
    return windowed
