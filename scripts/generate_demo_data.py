"""Generate the reproducible synthetic CSV bundled with SalesSight Lite."""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20261105
DAYS = 120
START_DATE = date(2026, 1, 1)
PRODUCTS = [
    ("Wireless Mouse", 899.0, 18),
    ("Mechanical Keyboard", 2499.0, 11),
    ("USB-C Hub", 1799.0, 13),
    ("Laptop Stand", 1299.0, 15),
    ("Webcam HD", 2199.0, 9),
    ("Desk Lamp", 1099.0, 12),
    ("Noise-Cancelling Headphones", 4499.0, 7),
]


def generate(output_path: Path) -> None:
    random.seed(SEED)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str | int | float]] = []
    order_counter = 10001

    product_names = [item[0] for item in PRODUCTS]
    product_weights = [item[2] for item in PRODUCTS]
    price_by_product = {item[0]: item[1] for item in PRODUCTS}

    for day_number in range(DAYS):
        current_date = START_DATE + timedelta(days=day_number)
        weekend_adjustment = -1 if current_date.weekday() >= 5 else 0
        mild_trend = day_number // 30
        order_count = max(5, 7 + mild_trend + weekend_adjustment + random.randint(0, 3))

        for _ in range(order_count):
            order_id = f"ORD-{order_counter:05d}"
            order_counter += 1
            line_count = random.choices([1, 2, 3], weights=[52, 36, 12], k=1)[0]
            chosen = random.sample(product_names, k=line_count)
            for product in chosen:
                quantity = random.choices([1, 2, 3, 4], weights=[55, 29, 12, 4], k=1)[0]
                base_price = price_by_product[product]
                price_factor = random.choices([1.0, 0.95, 0.9], weights=[72, 20, 8], k=1)[0]
                rows.append(
                    {
                        "date": current_date.isoformat(),
                        "order_id": order_id,
                        "product": product,
                        "quantity": quantity,
                        "unit_price": f"{base_price * price_factor:.2f}",
                    }
                )

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "order_id", "product", "quantity", "unit_price"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} synthetic order lines across {DAYS} days to {output_path}")


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    generate(project_root / "frontend" / "public" / "sample_sales.csv")

