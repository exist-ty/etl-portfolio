# ETL Portfolio — E-commerce Sales & Marketing Ingestion

![Tests](https://github.com/exist-ty/etl-portfolio/actions/workflows/test.yml/badge.svg)

Пет-проект уровня Data Engineer: пайплайн, который приводит "грязные" сырые данные
интернет-магазина (заказы, клиенты, товары, маркетинговый спенд) в надёжный
staging-слой PostgreSQL — с индексами, идемпотентной загрузкой и тестами на
transform-логику.

Аналитический слой поверх этих таблиц (CAC/CPL/ROMI, LTV, cohort retention,
дашборд, а также ClickHouse OLAP-слой поверх той же `stg_orders`/`stg_customers`)
сознательно вынесен в отдельный репозиторий —
[`product-marketing-analytics`](https://github.com/exist-ty/product-marketing-analytics): здесь только
инжиниринг данных, там — их использование. Ещё один репозиторий,
[`support-triage-llm`](https://github.com/exist-ty/support-triage-llm),
переиспользует ту же БД для триажа обращений клиентов через локальную LLM
(RAG поверх Ollama). Ещё один —
[`n8n-business-automation`](https://github.com/exist-ty/n8n-business-automation),
читает те же staging-таблицы и витрины под собственными, специально
ограниченными read-only ролями (алерты, дайджесты, разговорный доступ к
аналитике через Telegram-бота).

## Стек

Python, pandas, SQLAlchemy, PostgreSQL, pytest.

## Структура

- `data/raw/` — исходные CSV (customers, products, orders, marketing_spend)
- `sql/schema.sql` — DDL: staging-таблицы, индексы, витрина `mart_sales_summary`,
  реестр загрузок `etl_load_log`
- `src/etl/` — extract / transform / load модули и `pipeline.py` (entrypoint:
  `run()` — полная перезаливка, `run_incremental()` — watermark-инкремент по
  заказам, см. «Инкрементальная загрузка и backfill»)
- `tests/` — pytest-тесты для transform-логики и идемпотентности инкремента
- `scripts/backfill_2025.py` — настоящий backfill за весь 2025 год по дням
- `scripts/generate_scale_data.py` — нагрузочный тест индексов на 150k заказов
  (см. «Индексы и почему они здесь»)

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

## Инкрементальная загрузка и backfill

`run()` (шаг 5 выше) — режим "дать всё целиком": полная перезаливка каждой
таблицы на каждый запуск. Он остаётся как есть — это то, что использует
Airflow DAG хаба и существующие тесты. Отдельно, дополнительно —
watermark-инкремент по `order_date`:

```python
from datetime import date
from src.etl.pipeline import bootstrap_dimensions, run_incremental

bootstrap_dimensions()                                    # один раз, до первого окна
run_incremental(date(2025, 1, 1), date(2025, 1, 2))        # только заказы этого дня, upsert
```

**Почему дименшены грузятся отдельно.** `load_customers()`/`load_products()`
делают `TRUNCATE ... CASCADE`, а у `stg_orders` на них FK — повторный вызов
посреди backfill стёр бы всю уже загруженную историю заказов. Поэтому
`bootstrap_dimensions()` вызывается РОВНО ОДИН РАЗ, а `run_incremental()` в
цикле трогает только `stg_orders` (через `upsert_orders` — `INSERT ... ON
CONFLICT (order_id) DO UPDATE`, не `TRUNCATE`).

**Настоящий backfill за 2025 год:**

```
python scripts/backfill_2025.py
```

Реально прогнан на этом датасете: **365 дней, 1985 заказов через upsert**
(2018 сырых строк минус дубли/грязные — та же очистка, что и в `run()`), в
`etl_load_log` — ровно 365 строк, по одной на день, независимо от того,
сколько раз какой-то день перезапускался (проверено `tests/test_incremental_load.py`:
повторный прогон одного окна не меняет ни количество строк в `stg_orders`,
ни количество записей лога для этого окна).

**Во что упирается.** Датасет заморожен — `order_date` строго в границах
2025 года (см. «Источники данных» ниже), поэтому backfill здесь исторический,
а не живой поток: "сегодняшних" данных не появится, сколько окон ни грузи.
`mart_sales_summary` инкрементально не обновляется — агрегат по-прежнему
считается `run()` по полному набору заказов; инкрементальное обновление
агрегата — отдельная задача, не входящая в этот пункт. Тест на идемпотентность
требует живую БД и в CI не запускается (см. «CI с живой БД» в роадмапе хаба —
отдельный, ещё не сделанный пункт) — в CI он пропускается (`pytest.skip`),
а не падает.

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
задел на рост объёма.

**Проверено на реальном масштабе.** `scripts/generate_scale_data.py` грузит
150 000 заказов на 5 000 клиентов в отдельную одноразовую базу
(`etl_portfolio_scale` — основной `etl_portfolio` не трогается, на него
завязаны числа в `product-marketing-analytics`/`support-triage-llm`) и
прогоняет те же запросы через `EXPLAIN ANALYZE`. План действительно
переключается на `Bitmap Index Scan` по всем трём индексам:

```
SELECT * FROM stg_orders WHERE customer_id = 604
Bitmap Heap Scan on stg_orders  (actual time=0.550..0.582 rows=39 loops=1)
  ->  Bitmap Index Scan on idx_stg_orders_customer_id  (actual time=0.325..0.325 rows=39 loops=1)
Execution Time: 0.872 ms

SELECT * FROM stg_orders WHERE product_id = 20
Bitmap Heap Scan on stg_orders  (actual time=0.400..1.776 rows=6104 loops=1)
  ->  Bitmap Index Scan on idx_stg_orders_product_id  (actual time=0.273..0.274 rows=6104 loops=1)
Execution Time: 1.929 ms

SELECT * FROM stg_orders WHERE order_date BETWEEN '2025-03-01' AND '2025-03-31'
Bitmap Heap Scan on stg_orders  (actual time=0.633..2.759 rows=12799 loops=1)
  ->  Bitmap Index Scan on idx_stg_orders_order_date  (actual time=0.492..0.492 rows=12799 loops=1)
Execution Time: 3.062 ms
```

Итого: на 2000 строк Seq Scan честно дешевле, на 150 000 планировщик сам
переходит на индекс — ровно то поведение, ради которого индексы добавлены
заранее, а не когда JOIN'ы в аналитическом слое станут медленными.

## Data Quality и грязные данные

`scripts/generate_data.py` намеренно вносит в синтетические данные ряд
дефектов — не ради тестового покрытия самого по себе, а чтобы Transform-слой
решал реальные задачи очистки, а не работал на идеальном input'е:

| Дефект | Где вносится | Кто фильтрует |
|---|---|---|
| Пропуск `quantity` | `orders.csv`, ~15 строк из исходных 2000 | `clean_orders()` — `dropna` |
| Дубли `order_id` | `orders.csv`, ~10 строк | `clean_orders()` — `drop_duplicates` |
| Отрицательное `quantity` | `orders.csv`, +8 доп. строк с новыми `order_id` (эмулирует ошибку ввода/возврат) | `clean_orders()` — `quantity > 0` |
| Дубли `customer_id` | `customers.csv`, +3 доп. строки (повторная отправка формы) | `clean_customers()` — `drop_duplicates` |
| Пустой/битый `email` | `customers.csv`, +4 доп. строки с новыми `customer_id` | `clean_customers()` — regex `EMAIL_RE` |
| Orphan FK (`customer_id`/`product_id` без родителя) | не генерируется намеренно, но `build_fact_orders()` фильтрует через `inner join` в любом случае | `build_fact_orders()` |

Дубли и битые email **добавляются** поверх валидных 200 клиентов /
2000 заказов новыми `id`, а не портят существующие строки — иначе
регенерация данных сдвинула бы состав `stg_customers`/`stg_orders` и вместе
с ним все производные числа в `product-marketing-analytics` (churn-модель,
LTV, A/B-тест на клиентах) и `support-triage-llm`. Реальный прогон пайплайна
подтверждает это: после очистки в БД попадает ровно 200 клиентов и 1985
заказов — то же число, что было бы без этих тестовых дефектов.

`tests/test_data_quality.py` проверяет это на **реальном** сгенерированном
датасете (`data/raw/*.csv`), не на игрушечных DataFrame: сначала убеждается,
что дефекты вообще присутствуют в фикстуре (`test_raw_fixtures_actually_contain_the_defects_below`
— иначе остальные тесты ничего не гарантируют), затем — что после
`clean_customers()`/`build_fact_orders()` в выходных данных нет дублей
`order_id`, все email проходят regex, все `total_amount > 0`, и все
FK-ссылки в `stg_orders` существуют в `stg_customers`/`stg_products`.

## Декларативные контракты данных (Soda Core)

`sql/schema.sql` ловит структурные нарушения (NOT NULL, PK, FK) на уровне
самой БД. Но часть находок из `product-marketing-analytics/metrics/README.md`
constraint'ами не покрывается — например, `NULL` в nullable `signup_date`
(завышает CAC) и заказы с `order_date < signup_date` (три витрины трактуют их
по-разному). Раньше эти проверки жили постфактум, SQL-ом внутри воркфлоу
`n8n-business-automation/sql/data_quality_checks.sql` — вне контроля версий
и ПОСЛЕ того, как данные уже доехали до витрин.

`soda/checks.yml` — та же проверка, но декларативно, в контроле версий и
fail-fast ДО построения витрин: в Airflow DAG (`Nikolay-Kolesnikov-portfolio-hub`)
задача `data_contracts` стоит между `etl_pipeline` и `refresh_marts`/
`load_to_clickhouse`/`build_features`/`generate_messages`, а не после них.
`scripts/run_data_contracts.py` запускает скан и решает по самому JSON
результата, а не по exit-коду `soda` (тот падает и на WARN, не только на
FAIL): настоящий FAIL/ошибка сканирования — ненулевой код и витрины не
строятся; WARN (заказы раньше регистрации — свойство синтетического
генератора, а не поломка) печатается в лог, но не блокирует пайплайн.

Проверено на живых данных: 96 из 1985 заказов (4.8%) действительно раньше
регистрации клиента — цифра, которую `metrics/README.md` раньше
документировал как открытый вопрос без измерения.

```bash
pip install soda-core-postgres
python scripts/run_data_contracts.py
```

## Что показывает витрина

`mart_sales_summary` — суммарная выручка и количество заказов по категории
товара и месяцу, посчитанные из "грязных" исходных данных (пропуски и дубликаты
в `orders.csv` намеренно оставлены и обрабатываются на этапе Transform).
