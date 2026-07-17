-- Staging: сырые данные как есть из CSV
DROP TABLE IF EXISTS stg_orders;
DROP TABLE IF EXISTS stg_products;
DROP TABLE IF EXISTS stg_customers;
DROP TABLE IF EXISTS mart_sales_summary;

CREATE TABLE stg_customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    city TEXT,
    signup_date DATE
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

-- Mart: агрегат выручки по категории и месяцу
CREATE TABLE mart_sales_summary (
    category TEXT NOT NULL,
    sales_month DATE NOT NULL,
    total_revenue NUMERIC(14, 2) NOT NULL,
    order_count INTEGER NOT NULL,
    PRIMARY KEY (category, sales_month)
);
