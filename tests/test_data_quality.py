"""Data quality тесты на реальном сгенерированном датасете (data/raw/), а не
на игрушечных DataFrame — проверяют, что clean_customers()/clean_orders()
(src/etl/transform.py) действительно фильтруют "грязные" записи, намеренно
внесённые scripts/generate_data.py (см. README, "Data Quality и грязные
данные")."""
import pytest

from src.etl import extract, transform


@pytest.fixture(scope="module")
def raw():
    return extract.extract_all()


@pytest.fixture(scope="module")
def clean_customers(raw):
    return transform.clean_customers(raw["customers"])


@pytest.fixture(scope="module")
def fact_orders(raw, clean_customers):
    return transform.build_fact_orders(raw["orders"], clean_customers, raw["products"])


def test_raw_fixtures_actually_contain_the_defects_below():
    """Если этот тест падает — generate_data.py перестал вносить грязные
    данные, и остальные тесты в этом файле ничего не проверяют."""
    raw_data = extract.extract_all()
    assert raw_data["orders"]["quantity"].isna().any()
    assert raw_data["orders"]["order_id"].duplicated().any()
    assert (raw_data["orders"]["quantity"].dropna().astype(int) < 0).any()
    assert (raw_data["customers"]["email"].fillna("") == "").any()
    assert raw_data["customers"]["customer_id"].duplicated().any()


def test_no_duplicate_orders(fact_orders):
    assert not fact_orders["order_id"].duplicated().any()


def test_email_format(clean_customers):
    assert clean_customers["email"].str.match(transform.EMAIL_RE).all()


def test_amount_positive(fact_orders):
    assert (fact_orders["total_amount"] > 0).all()


def test_foreign_key_integrity(fact_orders, clean_customers, raw):
    assert set(fact_orders["customer_id"]).issubset(set(clean_customers["customer_id"]))
    assert set(fact_orders["product_id"]).issubset(set(raw["products"]["product_id"]))
