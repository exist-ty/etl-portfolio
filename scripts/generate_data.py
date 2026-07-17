"""Одноразовый скрипт: генерирует синтетические CSV в data/raw/.
Запуск: python scripts/generate_data.py
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

CITIES = ["Moscow", "Saint Petersburg", "Kazan", "Novosibirsk", "Yekaterinburg"]
CATEGORIES = ["Electronics", "Home & Kitchen", "Sports", "Books", "Toys"]

CHANNELS = ["context_ads", "seo", "social_ads", "referral", "email"]
CHANNEL_WEIGHTS = [0.35, 0.25, 0.20, 0.12, 0.08]

# у.е. за лид и доля лидов, доходящих до регистрации — разная по каналам,
# чтобы витрина CAC/CPL/ROMI показывала реалистичный разброс эффективности
CHANNEL_CPL_BASE = {
    "context_ads": 45,
    "seo": 15,
    "social_ads": 30,
    "referral": 8,
    "email": 5,
}
CHANNEL_CONVERSION = {
    "context_ads": 0.35,
    "seo": 0.22,
    "social_ads": 0.18,
    "referral": 0.50,
    "email": 0.15,
}

PRODUCT_NAMES = {
    "Electronics": ["Wireless Mouse", "USB-C Hub", "Bluetooth Speaker", "Webcam", "Power Bank"],
    "Home & Kitchen": ["Coffee Maker", "Blender", "Cutting Board", "Air Fryer", "Toaster"],
    "Sports": ["Yoga Mat", "Dumbbell Set", "Running Shoes", "Water Bottle", "Resistance Bands"],
    "Books": ["Python Crash Course", "Clean Code", "Atomic Habits", "The Pragmatic Programmer", "Deep Work"],
    "Toys": ["Lego Set", "Puzzle 1000pc", "RC Car", "Board Game", "Building Blocks"],
}


def generate_customers(n=200):
    rows = []
    for i in range(1, n + 1):
        signup = date(2024, 1, 1) + timedelta(days=random.randint(0, 500))
        rows.append({
            "customer_id": i,
            "name": f"Customer {i}",
            "email": f"customer{i}@example.com",
            "city": random.choice(CITIES),
            "signup_date": signup.isoformat(),
            "channel": random.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0],
        })
    return rows


def generate_marketing_spend(customers: list[dict]) -> list[dict]:
    """Расход и лиды по каналу/месяцу, выведенные из фактических регистраций.

    leads = обратный расчёт из signups через CHANNEL_CONVERSION (не все лиды
    доходят до регистрации). Часть месяцев намеренно "неэффективна" (спенд
    завышен при том же числе регистраций) — чтобы витрина ROMI показывала
    кандидатов на отключение кампании, как в реальной маркетинговой аналитике.
    """
    signups_by_channel_month: dict[tuple[str, date], int] = {}
    for c in customers:
        month = date.fromisoformat(c["signup_date"]).replace(day=1)
        key = (c["channel"], month)
        signups_by_channel_month[key] = signups_by_channel_month.get(key, 0) + 1

    rows = []
    for (channel, month), signups in signups_by_channel_month.items():
        conversion = CHANNEL_CONVERSION[channel]
        leads = max(signups, round(signups / conversion * random.uniform(0.85, 1.15)))
        cpl = CHANNEL_CPL_BASE[channel] * random.uniform(0.8, 1.2)
        spend = leads * cpl

        if random.random() < 0.15:  # неэффективный месяц: тот же охват, выше цена
            spend *= random.uniform(1.5, 2.2)

        rows.append({
            "channel": channel,
            "spend_month": month.isoformat(),
            "leads": leads,
            "spend": round(spend, 2),
        })

    rows.sort(key=lambda r: (r["spend_month"], r["channel"]))
    return rows


def generate_products():
    rows = []
    pid = 1
    for category, names in PRODUCT_NAMES.items():
        for name in names:
            rows.append({
                "product_id": pid,
                "name": name,
                "category": category,
                "price": round(random.uniform(5, 300), 2),
            })
            pid += 1
    return rows


def generate_orders(customers, products, n=2000):
    rows = []
    for i in range(1, n + 1):
        order_date = date(2025, 1, 1) + timedelta(days=random.randint(0, 364))
        rows.append({
            "order_id": i,
            "customer_id": random.choice(customers)["customer_id"],
            "product_id": random.choice(products)["product_id"],
            "quantity": random.randint(1, 5),
            "order_date": order_date.isoformat(),
        })

    # намеренно вносим "грязные" данные, чтобы Transform делал реальную работу
    for row in random.sample(rows, 15):
        row["quantity"] = ""  # пропуск

    for row in random.sample(rows, 10):
        rows.append(dict(row))  # дубликаты

    random.shuffle(rows)
    return rows


def write_csv(path: Path, rows: list[dict]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    customers = generate_customers()
    products = generate_products()
    orders = generate_orders(customers, products)
    marketing_spend = generate_marketing_spend(customers)

    write_csv(RAW_DIR / "customers.csv", customers)
    write_csv(RAW_DIR / "products.csv", products)
    write_csv(RAW_DIR / "orders.csv", orders)
    write_csv(RAW_DIR / "marketing_spend.csv", marketing_spend)

    print(f"customers: {len(customers)} rows")
    print(f"products: {len(products)} rows")
    print(f"orders: {len(orders)} rows")
    print(f"marketing_spend: {len(marketing_spend)} rows")
