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
        })
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

    write_csv(RAW_DIR / "customers.csv", customers)
    write_csv(RAW_DIR / "products.csv", products)
    write_csv(RAW_DIR / "orders.csv", orders)

    print(f"customers: {len(customers)} rows")
    print(f"products: {len(products)} rows")
    print(f"orders: {len(orders)} rows")
