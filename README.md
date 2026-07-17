# ETL Portfolio — E-commerce Sales

Учебный ETL-пайплайн: читает CSV с заказами интернет-магазина, очищает и агрегирует данные, загружает в PostgreSQL.

## Стек

Python, pandas, SQLAlchemy, PostgreSQL, pytest.

## Структура

- `data/raw/` — исходные CSV (customers, products, orders)
- `sql/schema.sql` — DDL: staging-таблицы + витрина `mart_sales_summary`
- `src/etl/` — extract / transform / load модули и `pipeline.py` (entrypoint)
- `tests/` — pytest-тесты для transform-логики

## Как запустить

1. Создать и активировать venv:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Скопировать `.env.example` в `.env` и указать пароль от своего PostgreSQL.
3. Создать базу и применить схему:
   ```
   createdb -U postgres etl_portfolio
   psql -U postgres -d etl_portfolio -f sql/schema.sql
   ```
4. Сгенерировать тестовые данные (один раз):
   ```
   python scripts/generate_data.py
   ```
5. Запустить пайплайн:
   ```
   python -m src.etl.pipeline
   ```
6. Прогнать тесты:
   ```
   pytest
   ```

## Что показывает витрина

`mart_sales_summary` — суммарная выручка и количество заказов по категории товара и месяцу, посчитанные из "грязных" исходных данных (пропуски и дубликаты в `orders.csv` намеренно оставлены и обрабатываются на этапе Transform).
