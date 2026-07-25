import logging
from datetime import date

from . import extract, load, transform
from .db import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run() -> None:
    """Полная перезаливка всех таблиц — режим "дать всё целиком", как раньше.
    Используется существующими вызовами (Airflow DAG хаба, тесты) без
    изменений. Для инкрементального backfill по дням см. run_incremental()."""
    logger.info("ETL pipeline started")

    raw = extract.extract_all()

    clean_customers = transform.clean_customers(raw["customers"])
    fact_orders = transform.build_fact_orders(raw["orders"], clean_customers, raw["products"])
    summary = transform.build_sales_summary(fact_orders)

    engine = get_engine()
    load.load_customers(engine, clean_customers)
    load.load_products(engine, raw["products"])
    load.load_orders(engine, fact_orders)
    load.load_sales_summary(engine, summary)
    load.load_marketing_spend(engine, raw["marketing_spend"])

    logger.info("ETL pipeline finished successfully")


def bootstrap_dimensions() -> None:
    """Полная перезаливка customers/products/marketing_spend — вызывается РОВНО
    ОДИН РАЗ перед серией run_incremental(), не внутри дневного цикла:
    load_customers()/load_products() делают TRUNCATE ... CASCADE, а у
    stg_orders на них FK — повторный вызов посреди backfill стёр бы всю уже
    загруженную историю заказов. SCD Type 2 для customers (следующий пункт
    роадмапа) со временем уберёт и это ограничение; сейчас дименшены не
    партиционированы по дате, поэтому им не нужен watermark — только orders."""
    raw = extract.extract_all()
    clean_customers = transform.clean_customers(raw["customers"])

    engine = get_engine()
    load.load_customers(engine, clean_customers)
    load.load_products(engine, raw["products"])
    load.load_marketing_spend(engine, raw["marketing_spend"])
    logger.info("Dimensions bootstrapped (customers/products/marketing_spend)")


def run_incremental(data_interval_start: date, data_interval_end: date) -> dict:
    """Watermark-инкремент: забирает и грузит ТОЛЬКО заказы с order_date в
    [data_interval_start, data_interval_end) — upsert по order_id
    (load.upsert_orders), а не TRUNCATE. Повторный прогон одного и того же
    окна не создаёт дублей и не трогает другие окна — это и проверяется
    tests/test_incremental_load.py, а не только заявляется в README.

    Дименшены не перезагружаются здесь — см. bootstrap_dimensions(), вызови
    её один раз перед первым запуском. mart_sales_summary тоже не
    пересчитывается: инкрементальное обновление агрегата — отдельная
    задача, не входящая в этот пункт роадмапа (сейчас это ответственность
    run(), который считает summary по ПОЛНОМУ набору заказов)."""
    logger.info("Incremental ETL run: [%s, %s)", data_interval_start, data_interval_end)

    raw = extract.extract_all()
    clean_customers = transform.clean_customers(raw["customers"])

    orders_window = extract.extract_orders_window(data_interval_start, data_interval_end)
    fact_orders = transform.build_fact_orders(orders_window, clean_customers, raw["products"])

    engine = get_engine()
    rows_loaded = load.upsert_orders(engine, fact_orders)
    load.record_load(engine, data_interval_start, data_interval_end, len(orders_window), rows_loaded)

    logger.info("Incremental ETL run finished: %d orders upserted", rows_loaded)
    return {"rows_extracted": len(orders_window), "rows_loaded": rows_loaded}


if __name__ == "__main__":
    run()
