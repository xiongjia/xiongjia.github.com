"""Generate mock e-commerce raw data into data/raw.duckdb (a standalone "source DB").

Usage:
    uv run python scripts/generate_mock_data.py                  # full: 30 days from 2026-06-01
    uv run python scripts/generate_mock_data.py --days 60        # full: custom day count
    uv run python scripts/generate_mock_data.py --append-days 2  # append: N days after max date
    uv run python scripts/generate_mock_data.py --seed 42        # fixed seed (default 42)

Writes 4 tables in the raw catalog (default main schema): customers /
products / orders / order_items. Full mode deletes and recreates raw.duckdb;
append mode keeps the file and only inserts new-days data with continuous ids
(used to demo dbt incremental runs).
"""

from __future__ import annotations

import argparse
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW_DB = ROOT / "data" / "raw.duckdb"

COUNTRIES = ["CN", "US", "JP", "DE", "FR", "GB", "SG"]
CUSTOMER_COUNT = 200
ORDERS_PER_DAY = (20, 40)
ITEMS_PER_ORDER = (1, 5)
QUANTITY_RANGE = (1, 3)
STATUS_WEIGHTS = [("placed", 60), ("completed", 32), ("cancelled", 8)]

PRODUCT_NAMES = [
    (
        "Electronics",
        [
            "Wireless Mouse",
            "Mechanical Keyboard",
            "USB-C Hub",
            "Monitor Stand",
            "Webcam Pro",
            "Noise-Cancelling Headphones",
            "Smart Speaker",
            "Portable SSD 1TB",
            "Desk Lamp",
            "Bluetooth Earbuds",
        ],
    ),
    (
        "Clothing",
        [
            "Cotton Tee",
            "Hoodie",
            "Denim Jacket",
            "Running Shorts",
            "Wool Sweater",
            "Cargo Pants",
            "Windbreaker",
            "Baseball Cap",
        ],
    ),
    (
        "Books",
        [
            "The Pragmatic Programmer",
            "Clean Code",
            "Designing Data-Intensive Applications",
            "System Design Interview",
            "A Philosophy of Software Design",
            "SQL Antipatterns",
        ],
    ),
    (
        "Home",
        [
            "Coffee Maker",
            "Air Fryer",
            "Standing Desk",
            "Ergonomic Chair",
            "Smart Bulb (4-pack)",
            "Robot Vacuum",
            "Storage Box (Set of 5)",
        ],
    ),
    (
        "Sports",
        ["Yoga Mat", "Adjustable Dumbbells", "Jump Rope", "Resistance Bands", "Water Bottle 1L"],
    ),
    ("Toys", ["Wooden Blocks", "Puzzle 1000pcs", "RC Car", "Building Blocks Set"]),
]

FIRST_NAMES = [
    "Alice",
    "Bob",
    "Carol",
    "Dave",
    "Eve",
    "Frank",
    "Grace",
    "Hank",
    "Ivy",
    "Jack",
    "Kate",
    "Leo",
    "Mia",
    "Nick",
    "Olivia",
    "Paul",
    "Quinn",
    "Rita",
    "Sam",
    "Tina",
    "Uma",
    "Victor",
    "Wendy",
    "Xander",
    "Yuki",
    "Zoe",
    "Aaron",
    "Beth",
    "Cindy",
    "Dan",
]
LAST_NAMES = [
    "Adams",
    "Brown",
    "Chen",
    "Davis",
    "Evans",
    "Foster",
    "Green",
    "Hill",
    "Ivanov",
    "Jones",
    "Kim",
    "Lee",
    "Miller",
    "Navarro",
    "Okafor",
    "Parker",
    "Quinn",
    "Rossi",
    "Smith",
    "Tanaka",
    "Ueda",
    "Vogel",
    "Wang",
    "Xu",
    "Young",
    "Zhang",
    "Bennett",
    "Cole",
    "Diaz",
    "Grant",
]


def _make_products(rng: random.Random) -> list[dict]:
    products = []
    pid = 1
    for category, names in PRODUCT_NAMES:
        for name in names:
            products.append(
                {
                    "id": pid,
                    "name": name,
                    "category": category,
                    "price": round(rng.uniform(9.99, 499.99), 2),
                    "created_at": datetime(2026, 1, 1)
                    + timedelta(days=rng.randint(0, 150), hours=rng.randint(0, 23)),
                }
            )
            pid += 1
    return products


def _make_customers(rng: random.Random) -> list[dict]:
    customers = []
    for i in range(1, CUSTOMER_COUNT + 1):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        name = f"{first} {last}"
        customers.append(
            {
                "id": i,
                "name": name,
                "email": f"{first.lower()}.{last.lower()}{i}@example.com",
                "country": rng.choice(COUNTRIES),
                "created_at": datetime(2026, 1, 1)
                + timedelta(
                    days=rng.randint(0, 150), hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
                ),
            }
        )
    return customers


def _make_orders_and_items(
    rng: random.Random,
    start: date,
    days: int,
    products: list[dict],
    start_oid: int = 1,
    start_iid: int = 1,
) -> tuple[list[dict], list[dict]]:
    orders: list[dict] = []
    items: list[dict] = []
    oid = start_oid
    iid = start_iid
    for offset in range(days):
        day = start + timedelta(days=offset)
        num_orders = rng.randint(*ORDERS_PER_DAY)
        for _ in range(num_orders):
            created_at = datetime.combine(day, datetime.min.time()) + timedelta(
                hours=rng.randint(8, 22), minutes=rng.randint(0, 59)
            )
            status = rng.choices(
                [s for s, _ in STATUS_WEIGHTS], weights=[w for _, w in STATUS_WEIGHTS]
            )[0]
            orders.append(
                {
                    "id": oid,
                    "customer_id": rng.randint(1, CUSTOMER_COUNT),
                    "order_date": day,
                    "status": status,
                    "updated_at": created_at + timedelta(hours=rng.randint(0, 12)),
                }
            )
            for _ in range(rng.randint(*ITEMS_PER_ORDER)):
                product = rng.choice(products)
                unit_price = round(product["price"] * rng.uniform(0.9, 1.1), 2)
                items.append(
                    {
                        "id": iid,
                        "order_id": oid,
                        "product_id": product["id"],
                        "quantity": rng.randint(*QUANTITY_RANGE),
                        "unit_price": unit_price,
                        "discount": rng.choice([0.0, 0.0, 0.05, 0.1]),
                    }
                )
                iid += 1
            oid += 1
    return orders, items


def _current_catalog(con: duckdb.DuckDBPyConnection) -> str:
    """DuckDB 1.5 names the catalog after the file name; probe it dynamically
    instead of hard-coding it (keeps the script usable if the file is renamed)."""
    return con.execute("SELECT current_database()").fetchone()[0]


def _max_order_date(con: duckdb.DuckDBPyConnection) -> date | None:
    try:
        row = con.execute(
            f"SELECT max(order_date) FROM {_current_catalog(con)}.main.orders"
        ).fetchone()
    except Exception:
        return None
    return row[0] if row and row[0] else None


def _load(con: duckdb.DuckDBPyConnection, table: str, rows: list[dict], cols: list[str]) -> None:
    con.executemany(
        f"INSERT INTO {table} VALUES ({','.join('?' * len(cols))})",
        [[r[c] for c in cols] for r in rows],
    )


def _values(rows: list[dict]) -> str:
    """Serialize a small row set as a VALUES tuple list, used by append-mode insert."""
    cols = list(rows[0].keys())
    out = []
    for r in rows:
        vals = []
        for c in cols:
            v = r[c]
            if isinstance(v, datetime):
                vals.append(f"TIMESTAMP '{v}'")
            elif isinstance(v, date):
                vals.append(f"DATE '{v}'")
            elif isinstance(v, str):
                vals.append(f"'{v}'")
            else:
                vals.append(str(v))
        out.append("(" + ", ".join(vals) + ")")
    return ", ".join(out)


def generate(args: argparse.Namespace) -> None:
    RAW_DB.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)

    products = _make_products(rng)
    customers = _make_customers(rng)

    if args.append_days:
        # Incremental append: open the existing file, find the max order date,
        # then generate the next N days and insert only those.
        if not RAW_DB.exists():
            raise SystemExit(
                f"error: {RAW_DB} does not exist; run full mode (without --append-days) first"
            )
        con = duckdb.connect(str(RAW_DB))
        catalog = _current_catalog(con)
        base = _max_order_date(con)
        if base is None:
            raise SystemExit(
                "error: cannot append: orders table is missing or empty in the existing database"
            )
        # Continue id sequences from the current max so appended rows never
        # collide with existing primary keys.
        max_oid = con.execute(f"SELECT coalesce(max(id), 0) FROM {catalog}.main.orders").fetchone()[
            0
        ]
        max_iid = con.execute(
            f"SELECT coalesce(max(id), 0) FROM {catalog}.main.order_items"
        ).fetchone()[0]
        orders, items = _make_orders_and_items(
            rng, base + timedelta(days=1), args.append_days, products, max_oid + 1, max_iid + 1
        )
        con.execute(
            f"INSERT INTO {catalog}.main.orders SELECT * FROM (VALUES {_values(orders)}) "
            "t(id, customer_id, order_date, status, updated_at)"
        )
        con.execute(
            f"INSERT INTO {catalog}.main.order_items SELECT * FROM (VALUES {_values(items)}) "
            "t(id, order_id, product_id, quantity, unit_price, discount)"
        )
        new_min = min(o["order_date"] for o in orders)
        new_max = max(o["order_date"] for o in orders)
        print(
            f"[append] added {len(orders)} orders / {len(items)} items over {new_min} ~ {new_max}"
        )
    else:
        # Full rebuild
        if RAW_DB.exists():
            RAW_DB.unlink()
            wal = RAW_DB.with_suffix(RAW_DB.suffix + ".wal")
            if wal.exists():
                wal.unlink()
        orders, items = _make_orders_and_items(rng, args.start_date, args.days, products)
        con = duckdb.connect(str(RAW_DB))
        catalog = _current_catalog(con)
        con.execute(
            f"CREATE TABLE {catalog}.main.customers (id INTEGER, name VARCHAR, email VARCHAR, "
            "country VARCHAR, created_at TIMESTAMP)"
        )
        con.execute(
            f"CREATE TABLE {catalog}.main.products (id INTEGER, name VARCHAR, category VARCHAR, "
            "price DOUBLE, created_at TIMESTAMP)"
        )
        con.execute(
            f"CREATE TABLE {catalog}.main.orders (id INTEGER, customer_id INTEGER, "
            "order_date DATE, status VARCHAR, updated_at TIMESTAMP)"
        )
        con.execute(
            f"CREATE TABLE {catalog}.main.order_items (id INTEGER, order_id INTEGER, "
            "product_id INTEGER, quantity INTEGER, unit_price DOUBLE, discount DOUBLE)"
        )
        _load(
            con,
            f"{catalog}.main.customers",
            customers,
            ["id", "name", "email", "country", "created_at"],
        )
        _load(
            con,
            f"{catalog}.main.products",
            products,
            ["id", "name", "category", "price", "created_at"],
        )
        _load(
            con,
            f"{catalog}.main.orders",
            orders,
            ["id", "customer_id", "order_date", "status", "updated_at"],
        )
        _load(
            con,
            f"{catalog}.main.order_items",
            items,
            ["id", "order_id", "product_id", "quantity", "unit_price", "discount"],
        )
        day_min = min(o["order_date"] for o in orders)
        day_max = max(o["order_date"] for o in orders)
        print(
            f"[full] rebuilt {RAW_DB.name}: {len(customers)} customers / "
            f"{len(products)} products / {len(orders)} orders / "
            f"{len(items)} items over {day_min} ~ {day_max}"
        )

    counts = {
        t: con.execute(f"SELECT count(*) FROM {_current_catalog(con)}.main.{t}").fetchone()[0]
        for t in ("customers", "products", "orders", "order_items")
    }
    print("[stats]", counts)
    con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2026, 6, 1))
    parser.add_argument("--seed", type=int, default=42)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--days", type=int, default=30, help="days to generate in full mode (default 30)"
    )
    mode.add_argument(
        "--append-days",
        type=int,
        default=0,
        help="incrementally append N days after the current max order date",
    )
    args = parser.parse_args()
    generate(args)


if __name__ == "__main__":
    main()
