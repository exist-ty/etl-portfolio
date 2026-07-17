"""Разовый эксперимент: доказать, что индексы из sql/schema.sql не декоративные.

На ~2000 заказов (основной демо-датасет) планировщик Postgres честно выбирает
Seq Scan — это видно в README. Этот скрипт создаёт ОТДЕЛЬНУЮ базу
etl_portfolio_scale (основной etl_portfolio не трогает — на неё завязаны числа
в product-marketing-analytics и support-triage-llm), грузит в неё 150 000
заказов на 5 000 клиентов и прогоняет EXPLAIN ANALYZE на тех же трёх запросах,
что и в README, чтобы честно посмотреть, меняется ли план на Index Scan.

Запуск: python scripts/generate_scale_data.py
"""
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent))
from generate_data import generate_customers, generate_orders, generate_products  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.etl.config import load_db_config  # noqa: E402
from src.etl.transform import clean_orders  # noqa: E402

SCALE_DB = "etl_portfolio_scale"
SCHEMA_SQL = Path(__file__).parent.parent / "sql" / "schema.sql"

N_CUSTOMERS = 5000
N_ORDERS = 150_000


def recreate_scale_database(config) -> None:
    conn = psycopg2.connect(
        host=config.host, port=config.port, user=config.user,
        password=config.password, dbname="postgres",
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {SCALE_DB}")
        cur.execute(f"CREATE DATABASE {SCALE_DB}")
    conn.close()


def build_orders_with_total(orders: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    # generate_orders() marks dirty rows with "" (mirrors the CSV round-trip
    # in the real pipeline, where pandas would read an empty field as NaN)
    orders = orders.replace({"quantity": ""}, pd.NA)
    orders = clean_orders(orders)
    fact = orders.merge(products[["product_id", "price"]], on="product_id", how="inner")
    fact["total_amount"] = (fact["quantity"] * fact["price"]).round(2)
    return fact[["order_id", "customer_id", "product_id", "quantity", "order_date", "total_amount"]]


def explain(conn, label: str, query: str) -> None:
    result = conn.execute(text(f"EXPLAIN ANALYZE {query}")).fetchall()
    print(f"\n--- {label} ---\n{query}")
    for row in result:
        print(row[0])


def main() -> None:
    config = load_db_config()

    print(f"Generating {N_CUSTOMERS} customers and {N_ORDERS} orders...")
    customers = pd.DataFrame(generate_customers(n=N_CUSTOMERS))
    products = pd.DataFrame(generate_products())
    orders = pd.DataFrame(generate_orders(customers.to_dict("records"), products.to_dict("records"), n=N_ORDERS))
    orders = build_orders_with_total(orders, products)

    print(f"Recreating database {SCALE_DB}...")
    recreate_scale_database(config)

    scale_url = (
        f"postgresql+psycopg2://{config.user}:{config.password}"
        f"@{config.host}:{config.port}/{SCALE_DB}"
    )
    engine = create_engine(scale_url)

    with engine.begin() as conn:
        conn.execute(text(SCHEMA_SQL.read_text(encoding="utf-8")))

    print("Loading data (this takes a minute or two)...")
    customers.to_sql("stg_customers", engine, if_exists="append", index=False, method="multi", chunksize=5000)
    products.to_sql("stg_products", engine, if_exists="append", index=False, method="multi", chunksize=5000)
    orders.to_sql("stg_orders", engine, if_exists="append", index=False, method="multi", chunksize=5000)

    sample_customer_id = int(orders["customer_id"].iloc[0])
    sample_product_id = int(orders["product_id"].iloc[0])

    with engine.begin() as conn:
        conn.execute(text("ANALYZE stg_orders"))
        conn.execute(text("ANALYZE stg_customers"))

        explain(conn, "filter by customer_id (idx_stg_orders_customer_id)",
                f"SELECT * FROM stg_orders WHERE customer_id = {sample_customer_id}")
        explain(conn, "filter by product_id (idx_stg_orders_product_id)",
                f"SELECT * FROM stg_orders WHERE product_id = {sample_product_id}")
        explain(conn, "filter by order_date range (idx_stg_orders_order_date)",
                "SELECT * FROM stg_orders WHERE order_date BETWEEN '2025-03-01' AND '2025-03-31'")

    print(f"\nDone. {SCALE_DB} is a disposable database, safe to drop:"
          f"\n  dropdb -U {config.user} {SCALE_DB}")


if __name__ == "__main__":
    main()
