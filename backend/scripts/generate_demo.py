"""Generate the demo dataset datasets/demo/customer.csv.

Realistic customer data with deliberately injected quality problems:
- phone format inconsistencies (138-1234-5678, +86 13812345678, ...)
- email anomalies (abc@qq, no domain, missing)
- duplicate customer_id
- whitespace in name
- mixed date formats
- outliers in age/amount
"""

import random
from pathlib import Path

import pandas as pd

random.seed(42)
N = 500
OUT = Path(__file__).resolve().parent.parent / "datasets" / "demo" / "customer.csv"

SURNAMES = list("王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾")

FIRST_NAMES = ["伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋", "勇", "艳", "杰", "娟", "涛", "明", "超", "秀", "兰", "霞", "平", "刚", "桂", "英"]


def rand_name() -> str:
    return random.choice(SURNAMES) + random.choice(FIRST_NAMES) + random.choice(["", random.choice(FIRST_NAMES)])


def rand_phone() -> str:
    r = random.random()
    digits = f"1{random.choice('3456789')}{random.randint(100000000, 999999999)}"
    if r < 0.80:
        return digits
    if r < 0.90:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    if r < 0.96:
        return f"+86 {digits}"
    return f"{digits[:3]} {digits[3:7]} {digits[7:]}"


def rand_email(i: int) -> str:
    r = random.random()
    base = f"user{i:04d}@example.com"
    if r < 0.90:
        return base
    if r < 0.95:
        return f"user{i:04d}@qq"  # missing TLD
    if r < 0.97:
        return f"user{i:04d}@example"  # missing domain
    return ""  # missing email


def rand_date() -> str:
    r = random.random()
    y, m, d = random.randint(2019, 2024), random.randint(1, 12), random.randint(1, 28)
    if r < 0.90:
        return f"{y:04d}-{m:02d}-{d:02d}"
    if r < 0.95:
        return f"{y}/{m}/{d}"
    return f"{d:02d}-{m:02d}-{y}"


rows = []
for i in range(1, N + 1):
    cid = f"C{i:04d}"
    name = rand_name()
    if i % 25 == 0:
        name = f"  {name} "  # whitespace
    phone = rand_phone()
    email = rand_email(i)
    age = random.randint(18, 65)
    if i % 50 == 0:
        age = random.choice([-5, 150])  # outlier
    reg = rand_date()
    amount = round(random.uniform(10, 9000), 2)
    if i % 40 == 0:
        amount = round(random.uniform(50000, 200000), 2)  # outlier
    rows.append(
        {
            "customer_id": cid,
            "name": name,
            "phone": phone,
            "email": email,
            "age": age,
            "register_date": reg,
            "amount": amount,
        }
    )

# inject duplicate customer_id rows
for _ in range(4):
    dup = random.choice(rows)
    rows.append(
        {
            "customer_id": dup["customer_id"],
            "name": dup["name"],
            "phone": dup["phone"],
            "email": dup["email"],
            "age": dup["age"],
            "register_date": dup["register_date"],
            "amount": dup["amount"],
        }
    )

df = pd.DataFrame(rows)
OUT.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUT, index=False, encoding="utf-8-sig")
print(f"demo dataset written: {OUT} ({len(df)} rows, {df.shape[1]} columns)")
