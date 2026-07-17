import pandas as pd

from src.etl.transform import build_fact_orders, build_sales_summary, clean_orders


def test_clean_orders_drops_missing_quantity_and_duplicates():
    orders = pd.DataFrame([
        {"order_id": 1, "customer_id": 1, "product_id": 1, "quantity": 2, "order_date": "2025-01-05"},
        {"order_id": 2, "customer_id": 1, "product_id": 1, "quantity": None, "order_date": "2025-01-06"},
        {"order_id": 1, "customer_id": 1, "product_id": 1, "quantity": 2, "order_date": "2025-01-05"},
    ])

    cleaned = clean_orders(orders)

    assert len(cleaned) == 1
    assert cleaned.iloc[0]["order_id"] == 1


def test_build_fact_orders_computes_total_amount():
    orders = pd.DataFrame([
        {"order_id": 1, "customer_id": 1, "product_id": 1, "quantity": 3, "order_date": "2025-01-05"},
    ])
    customers = pd.DataFrame([{"customer_id": 1, "name": "Alice"}])
    products = pd.DataFrame([{"product_id": 1, "category": "Books", "price": 10.0}])

    fact = build_fact_orders(orders, customers, products)

    assert fact.iloc[0]["total_amount"] == 30.0
    assert fact.iloc[0]["category"] == "Books"


def test_build_sales_summary_aggregates_by_category_and_month():
    fact_orders = pd.DataFrame([
        {"order_id": 1, "order_date": pd.Timestamp("2025-01-05"), "total_amount": 30.0, "category": "Books"},
        {"order_id": 2, "order_date": pd.Timestamp("2025-01-20"), "total_amount": 20.0, "category": "Books"},
        {"order_id": 3, "order_date": pd.Timestamp("2025-02-01"), "total_amount": 15.0, "category": "Books"},
    ])

    summary = build_sales_summary(fact_orders)

    jan = summary[summary["sales_month"] == pd.Timestamp("2025-01-01")].iloc[0]
    assert jan["total_revenue"] == 50.0
    assert jan["order_count"] == 2
