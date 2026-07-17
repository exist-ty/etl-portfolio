import logging

import pandas as pd

logger = logging.getLogger(__name__)


def clean_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Drop rows with missing quantity and duplicate order_id rows."""
    before = len(orders)

    cleaned = orders.dropna(subset=["quantity"]).copy()
    cleaned["quantity"] = cleaned["quantity"].astype(int)
    cleaned = cleaned.drop_duplicates(subset=["order_id"])

    dropped = before - len(cleaned)
    if dropped:
        logger.info("Dropped %d dirty/duplicate order rows", dropped)

    return cleaned


def build_fact_orders(
    orders: pd.DataFrame, customers: pd.DataFrame, products: pd.DataFrame
) -> pd.DataFrame:
    """Join orders with customers/products and compute total_amount per order."""
    orders = clean_orders(orders)

    fact = orders.merge(products[["product_id", "category", "price"]], on="product_id", how="inner")
    fact = fact.merge(customers[["customer_id"]], on="customer_id", how="inner")

    fact["total_amount"] = (fact["quantity"] * fact["price"]).round(2)
    fact["order_date"] = pd.to_datetime(fact["order_date"])

    return fact[
        ["order_id", "customer_id", "product_id", "quantity", "order_date", "total_amount", "category"]
    ]


def build_sales_summary(fact_orders: pd.DataFrame) -> pd.DataFrame:
    """Aggregate revenue and order count by category and month."""
    df = fact_orders.copy()
    df["sales_month"] = df["order_date"].values.astype("datetime64[M]")

    summary = (
        df.groupby(["category", "sales_month"], as_index=False)
        .agg(total_revenue=("total_amount", "sum"), order_count=("order_id", "count"))
    )
    summary["total_revenue"] = summary["total_revenue"].round(2)

    return summary
