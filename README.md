# ETL Portfolio — E-commerce Sales & Marketing Ingestion

Пет-проект уровня Data Engineer: пайплайн, который приводит "грязные" сырые данные
интернет-магазина (заказы, клиенты, товары, маркетинговый спенд) в надёжный
staging-слой PostgreSQL — с индексами, идемпотентной загрузкой и тестами на
transform-логику.

Аналитический слой поверх этих таблиц (CAC/CPL/ROMI, LTV, cohort retention,
дашборд) сознательно вынесен в отдельный репозиторий —
[`product-marketing-analytics`](../product-marketing-analytics): здесь только
инжиниринг данных, там — их использование. Ещё один репозиторий,
[`support-triage-llm`](https://github.com/exist-ty/support-triage-llm),
переиспользует ту же БД для триажа обращений клиентов через локальную LLM
(RAG поверх Ollama).

## Стек

Python, pandas, SQLAlchemy, PostgreSQL, pytest.

## Структура

- `data/raw/` — исходные CSV (customers, products, orders, marketing_spend)
- `sql/schema.sql` — DDL: staging-таблицы, индексы, витрина `mart_sales_summary`
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

> Если `product-marketing-analytics` или `support-triage-llm` уже применили
> свои таблицы/VIEW поверх этих данных, пересоздание схемы (шаг 3) потребует
> заново применить `sql/marts.sql` и `sql/triage_schema.sql` соответствующих
> репозиториев — `schema.sql` дропает таблицы через `CASCADE`.

## Источники данных

| Источник | Что несёт | Особенность |
|---|---|---|
| `customers.csv` | клиент, город, дата регистрации, канал привлечения | — |
| `products.csv` | товар, категория, цена | — |
| `orders.csv` | заказы | намеренно с пропусками в `quantity` и дублями `order_id` — Transform должен их отловить |
| `marketing_spend.csv` | расход и лиды по каналу/месяцу | выведен из фактических регистраций через разную конверсию по каналам |

## Индексы и почему они здесь

PostgreSQL **не** индексирует колонки внешних ключей автоматически — индекс
появляется только на стороне PK/UNIQUE, на который эта FK ссылается. Без явных
индексов на `stg_orders.customer_id` / `stg_orders.product_id` каждый JOIN
уходил бы в Seq Scan по мере роста таблицы. Добавлены:

```sql
CREATE INDEX idx_stg_orders_customer_id ON stg_orders(customer_id);
CREATE INDEX idx_stg_orders_product_id ON stg_orders(product_id);
CREATE INDEX idx_stg_orders_order_date ON stg_orders(order_date);
CREATE INDEX idx_stg_customers_channel ON stg_customers(channel);
CREATE INDEX idx_stg_customers_signup_date ON stg_customers(signup_date);
```

Честная проверка `EXPLAIN ANALYZE` на текущем объёме (~2000 заказов) показывает,
что планировщик всё ещё выбирает `Seq Scan` — и это **правильное** решение
оптимизатора: при такой малой таблице последовательное чтение дешевле, чем поиск
по индексу. Индексы здесь не ради красивого плана на игрушечных данных, а
задел на рост объёма (когда `orders` перевалит за десятки/сотни тысяч строк,
`Seq Scan` начнёт проигрывать) и обязательное покрытие FK-колонок, по которым
строятся JOIN'ы в аналитическом слое.

## Что показывает витрина

`mart_sales_summary` — суммарная выручка и количество заказов по категории
товара и месяцу, посчитанные из "грязных" исходных данных (пропуски и дубликаты
в `orders.csv` намеренно оставлены и обрабатываются на этапе Transform).
