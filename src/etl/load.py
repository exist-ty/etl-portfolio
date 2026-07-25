import logging
from datetime import date

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


def upsert_orders(engine: Engine, fact_orders: pd.DataFrame) -> int:
    """INSERT ... ON CONFLICT (order_id) DO UPDATE — в отличие от load_orders()
    (TRUNCATE + append), не трогает строки вне переданного батча. Это то, что
    делает повторный прогон одного и того же дня безопасным: он либо не
    меняет ничего (тот же батч), либо обновляет ровно те order_id, что
    реально изменились — но никогда не удаляет и не дублирует соседние дни."""
    if fact_orders.empty:
        return 0

    cols = ["order_id", "customer_id", "product_id", "quantity", "order_date", "total_amount"]
    rows = fact_orders[cols].to_dict("records")

    stmt = text(
        """
        INSERT INTO stg_orders (order_id, customer_id, product_id, quantity, order_date, total_amount)
        VALUES (:order_id, :customer_id, :product_id, :quantity, :order_date, :total_amount)
        ON CONFLICT (order_id) DO UPDATE SET
            customer_id = EXCLUDED.customer_id,
            product_id = EXCLUDED.product_id,
            quantity = EXCLUDED.quantity,
            order_date = EXCLUDED.order_date,
            total_amount = EXCLUDED.total_amount
        """
    )
    with engine.begin() as conn:
        conn.execute(stmt, rows)

    logger.info("Upserted %d rows into stg_orders", len(rows))
    return len(rows)


def record_load(
    engine: Engine,
    data_interval_start: date,
    data_interval_end: date,
    rows_extracted: int,
    rows_loaded: int,
) -> None:
    """Пишет/обновляет запись в etl_load_log (sql/schema.sql) — ON CONFLICT
    на паре границ окна, чтобы повторный прогон того же дня обновил ту же
    строку лога, а не добавил ещё одну — реестр остаётся 1 строка = 1 окно,
    даже после N повторных прогонов."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO etl_load_log
                    (data_interval_start, data_interval_end, rows_extracted, rows_loaded)
                VALUES (:start, :end, :extracted, :loaded)
                ON CONFLICT (data_interval_start, data_interval_end) DO UPDATE SET
                    rows_extracted = EXCLUDED.rows_extracted,
                    rows_loaded = EXCLUDED.rows_loaded,
                    loaded_at = now()
                """
            ),
            {
                "start": data_interval_start,
                "end": data_interval_end,
                "extracted": rows_extracted,
                "loaded": rows_loaded,
            },
        )
    logger.info("Recorded load [%s, %s): %d/%d rows", data_interval_start, data_interval_end, rows_loaded, rows_extracted)
