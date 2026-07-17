import logging

from . import extract, load, transform
from .db import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run() -> None:
    logger.info("ETL pipeline started")

    raw = extract.extract_all()

    fact_orders = transform.build_fact_orders(raw["orders"], raw["customers"], raw["products"])
    summary = transform.build_sales_summary(fact_orders)

    engine = get_engine()
    load.load_customers(engine, raw["customers"])
    load.load_products(engine, raw["products"])
    load.load_orders(engine, fact_orders)
    load.load_sales_summary(engine, summary)
    load.load_marketing_spend(engine, raw["marketing_spend"])

    logger.info("ETL pipeline finished successfully")


if __name__ == "__main__":
    run()
