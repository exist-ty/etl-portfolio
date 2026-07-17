-- Staging: сырые данные как есть из CSV
-- CASCADE: репозиторий product-marketing-analytics создаёт поверх этих таблиц
-- свои VIEW (mart_channel_economics и т.д.), а support-triage-llm — таблицы
-- триажа обращений (client_messages ссылается на stg_customers.customer_id)
-- — без CASCADE пересоздание схемы падает с "DependentObjectsStillExist".
-- После пересоздания схемы нужно заново применить sql/marts.sql того
-- репозитория и sql/triage_schema.sql репозитория support-triage-llm.
DROP TABLE IF EXISTS stg_orders CASCADE;
DROP TABLE IF EXISTS stg_products CASCADE;
DROP TABLE IF EXISTS stg_customers CASCADE;
DROP TABLE IF EXISTS stg_marketing_spend CASCADE;
DROP TABLE IF EXISTS mart_sales_summary CASCADE;

CREATE TABLE stg_customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    city TEXT,
    signup_date DATE,
    channel TEXT NOT NULL
);

CREATE TABLE stg_marketing_spend (
    channel TEXT NOT NULL,
    spend_month DATE NOT NULL,
    leads INTEGER NOT NULL,
    spend NUMERIC(12, 2) NOT NULL,
    PRIMARY KEY (channel, spend_month)
);

CREATE TABLE stg_products (
    product_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price NUMERIC(10, 2) NOT NULL
);

CREATE TABLE stg_orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES stg_customers(customer_id),
    product_id INTEGER NOT NULL REFERENCES stg_products(product_id),
    quantity INTEGER NOT NULL,
    order_date DATE NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL
);

-- Postgres НЕ создаёт индекс на стороне FK автоматически (только на
-- PK/UNIQUE, на которые эта FK ссылается) — без явных индексов ниже
-- каждый JOIN stg_orders->stg_customers/stg_products и любая фильтрация
-- по дате уходит в Seq Scan по мере роста таблицы.
CREATE INDEX idx_stg_orders_customer_id ON stg_orders(customer_id);
CREATE INDEX idx_stg_orders_product_id ON stg_orders(product_id);
CREATE INDEX idx_stg_orders_order_date ON stg_orders(order_date);

-- channel — колонка группировки/фильтра почти во всех март-запросах
-- (product-marketing-analytics), signup_date — ключ когортной разбивки
CREATE INDEX idx_stg_customers_channel ON stg_customers(channel);
CREATE INDEX idx_stg_customers_signup_date ON stg_customers(signup_date);

-- Mart: агрегат выручки по категории и месяцу
CREATE TABLE mart_sales_summary (
    category TEXT NOT NULL,
    sales_month DATE NOT NULL,
    total_revenue NUMERIC(14, 2) NOT NULL,
    order_count INTEGER NOT NULL,
    PRIMARY KEY (category, sales_month)
);

-- Аналитические витрины (CAC/CPL/ROMI, LTV, cohort retention) вынесены
-- в отдельный репозиторий product-marketing-analytics: он читает эти же
-- staging-таблицы, но live-in своём sql/marts.sql, не смешиваясь с ETL.
