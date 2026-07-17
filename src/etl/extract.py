import logging
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
