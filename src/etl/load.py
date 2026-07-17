import logging

import pandas as pd
from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)


def _truncate(engine: Engine, table: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))


def load_customers(engine: Engine, customers: pd.DataFrame) -> None:
    _truncate(engine, "stg_customers")
    customers.to_sql("stg_customers", engine, if_exists="append", index=False)
    logger.info("Loaded %d rows into stg_customers", len(customers))


def load_products(engine: Engine, products: pd.DataFrame) -> None:
    _truncate(engine, "stg_products")
    products.to_sql("stg_products", engine, if_exists="append", index=False)
    logger.info("Loaded %d rows into stg_products", len(products))


def load_orders(engine: Engine, fact_orders: pd.DataFrame) -> None:
    _truncate(engine, "stg_orders")
    cols = ["order_id", "customer_id", "product_id", "quantity", "order_date", "total_amount"]
    fact_orders[cols].to_sql("stg_orders", engine, if_exists="append", index=False)
    logger.info("Loaded %d rows into stg_orders", len(fact_orders))


def load_sales_summary(engine: Engine, summary: pd.DataFrame) -> None:
    _truncate(engine, "mart_sales_summary")
    summary.to_sql("mart_sales_summary", engine, if_exists="append", index=False)
    logger.info("Loaded %d rows into mart_sales_summary", len(summary))


def load_marketing_spend(engine: Engine, marketing_spend: pd.DataFrame) -> None:
    _truncate(engine, "stg_marketing_spend")
    marketing_spend.to_sql("stg_marketing_spend", engine, if_exists="append", index=False)
    logger.info("Loaded %d rows into stg_marketing_spend", len(marketing_spend))
