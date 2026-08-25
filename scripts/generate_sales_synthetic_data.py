# -*- coding: utf-8 -*-
"""
ERP_Sales_Data_Full.xlsx(원본, 2025-01~2026-06 약 1.4년치)를 그대로 보존한 채,
2021-08-05~2026-08-04(5년) 범위로 합성 데이터를 추가 생성한다.

원본 행은 단 하나도 값이 바뀌지 않는다 (PK 보존, UPSERT 안전).
새로 만드는 행은 원본에서 실측한 컬럼 구조·타입·계산 공식·범주형 분포를 그대로 따른다.

설계 근거(전부 원본 파일을 직접 열어 실측):
- 라인합계 = ROUND(수량 * 단가 * (1 - 할인율/100), 2)
- 라인세금 = ROUND(라인합계 * 0.16, 2)                (요르단 부가세 16% 고정)
- 헤더 소계 = SUM(라인합계), 헤더 세금 = SUM(라인세금) (오차 0으로 실측 확인)
- 헤더 총액 = 소계 + 세금  (Discount_Amount는 별도 표시만 되고 총액에 반영 안 됨 — 원본 버그, 그대로 재현)
- 담당자류 ID(Sales_Rep_ID 등) 풀은 원본에서 1~70 정수를 공유
- 품목(Item_ID)은 98개, 설명이 전 시트에서 100% 일관

이번 확장에서 반영하는 사업적 결정(PM 승인):
- 기간 2021-08-05~2026-08-04, 총 주문 800건(원본 70건 포함)
- 주문 "건수"는 시간이 지날수록 증가, "총 매출"은 오히려 감소(건당 단가가 작아지는 구조)
- 담당자 ID 풀을 70->100명으로 확장하되, 과거일수록 100명 전체를 쓰고
  원본 데이터가 시작되는 2025-01-16 시점부터는 원본과 동일하게 1~70만 사용
- 고객은 시간이 지날수록 이탈(Is_Active=False) 비율이 누적되도록 생성
- Sales Forecasts/Sales Reports의 Company_ID 1/2 혼재(원본 데이터 오염)는 이번에 1로 통일

실행:
    python scripts/generate_sales_synthetic_data.py
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

import numpy as np
import openpyxl
import pandas as pd

# ---------------------------------------------------------------------------
# 0. 전역 설정
# ---------------------------------------------------------------------------

SEED = 42
RNG = np.random.default_rng(SEED)
random.seed(SEED)

SRC_PATH = "data/raw/source_data/ERP_Sales_Data_Full.xlsx"
OUT_PATH = "data/raw/source_data/ERP_Sales_Data_Full_5y.xlsx"

DATE_START = date(2021, 8, 5)
DATE_END = date(2026, 8, 4)
# 원본 보존 구간의 시작일. 이 시점부터는 담당자 풀이 원본과 동일하게 1~70으로 좁혀진다.
PRESERVED_MIN_DATE = date(2025, 1, 16)

TOTAL_ORDERS = 800
NEW_CUSTOMERS = 90  # 원본 40명 + 90명 = 130명

REP_POOL_MIN = 70
REP_POOL_MAX = 100

TAX_RATE = 0.16


def days_between(d1: date, d2: date) -> int:
    return (d2 - d1).days


TOTAL_SPAN_DAYS = days_between(DATE_START, DATE_END)
TAPER_SPAN_DAYS = days_between(DATE_START, PRESERVED_MIN_DATE)


def recency(d: date) -> float:
    """0(가장 과거) ~ 1(가장 최근)."""
    return days_between(DATE_START, d) / TOTAL_SPAN_DAYS


def rep_pool_max(d: date) -> int:
    """해당 날짜에 쓸 수 있는 담당자 ID 상한. 2025-01-16 이후로는 70으로 고정."""
    if d >= PRESERVED_MIN_DATE:
        return REP_POOL_MIN
    frac = days_between(DATE_START, d) / TAPER_SPAN_DAYS
    return int(round(REP_POOL_MAX - (REP_POOL_MAX - REP_POOL_MIN) * frac))


def random_time_of_day() -> tuple[int, int]:
    """15분 단위로 스냅된 업무시간대 시:분."""
    hour = int(RNG.integers(8, 19))
    minute = int(RNG.choice([0, 15, 30, 45]))
    return hour, minute


def combine(d: date, hour: int | None = None, minute: int | None = None) -> datetime:
    if hour is None:
        hour, minute = random_time_of_day()
    return datetime(d.year, d.month, d.day, hour, minute)


def random_date(start: date, end: date, weight_fn=None) -> date:
    """start~end 사이 날짜를 weight_fn(recency)로 가중 샘플링."""
    span = days_between(start, end)
    if weight_fn is None:
        offset = int(RNG.integers(0, span + 1))
        return start + timedelta(days=offset)
    days = np.arange(span + 1)
    fracs = days / max(span, 1)
    weights = np.array([weight_fn(f) for f in fracs])
    weights = weights / weights.sum()
    offset = int(RNG.choice(days, p=weights))
    return start + timedelta(days=offset)


# "연도별" 질문은 결국 캘린더 연도(YEAR(order_date)) 기준으로 물어보게 되므로,
# 회계연도가 아니라 캘린더 연도 슬라이스로 목표를 만든다. 하루 단위 가중치를
# 먼저 만들고(건수 가중치는 과거->현재로 증가, 매출 단가 가중치는 감소),
# 그걸 캘린더 연도별로 합산해 연도별 목표 건수·목표 매출을 역산한다.
# 이렇게 하면 800건/목표 매출 합계가 반올림 오차 외엔 정확히 맞아떨어진다.
COUNT_DENSITY_END_START_RATIO = 3.0  # 가장 최근 날짜의 "건수 밀도"가 가장 과거의 약 3배
REVENUE_RATE_END_START_RATIO = (
    1 / 3.5
)  # 가장 최근 날짜의 "건당 단가 밀도"가 가장 과거의 약 1/3.5
TARGET_TOTAL_REVENUE_ALL = 26_000_000  # 5년 합계 매출 목표(전체 주문 금액 기준, 근사치)

_all_days = [DATE_START + timedelta(days=i) for i in range(TOTAL_SPAN_DAYS + 1)]
_day_frac = np.array([days_between(DATE_START, d) / TOTAL_SPAN_DAYS for d in _all_days])
_count_w = 1.0 + (COUNT_DENSITY_END_START_RATIO - 1.0) * _day_frac
_revenue_w = 1.0 + (REVENUE_RATE_END_START_RATIO - 1.0) * _day_frac

_year_day_idx: dict[int, list[int]] = {}
for _i, _d in enumerate(_all_days):
    _year_day_idx.setdefault(_d.year, []).append(_i)

YEAR_TARGETS = {}
for _y, _idxs in sorted(_year_day_idx.items()):
    YEAR_TARGETS[_y] = {
        "start": _all_days[_idxs[0]],
        "end": _all_days[_idxs[-1]],
        "target_count": int(
            round(TOTAL_ORDERS * _count_w[_idxs].sum() / _count_w.sum())
        ),
        "target_revenue": TARGET_TOTAL_REVENUE_ALL
        * _revenue_w[_idxs].sum()
        / _revenue_w.sum(),
    }
# 반올림 오차를 마지막 연도에서 흡수해 총합을 정확히 TOTAL_ORDERS로 맞춘다.
_diff = TOTAL_ORDERS - sum(v["target_count"] for v in YEAR_TARGETS.values())
YEAR_TARGETS[max(YEAR_TARGETS)]["target_count"] += _diff

print("=" * 70)
print("1. 원본 파일 로드")
print("=" * 70)
src = pd.ExcelFile(SRC_PATH)
sheets: dict[str, pd.DataFrame] = {
    name: src.parse(name) for name in src.sheet_names if name != "Index"
}
for name, df in sheets.items():
    print(f"  {name}: {len(df)}행")

customers0 = sheets["Customers"]
orders0 = sheets["Sales Orders"]
lines0 = sheets["Sales Order Lines"]
quotes0 = sheets["Sales Quotes"]
qlines0 = sheets["Sales Quote Lines"]
fulfill0 = sheets["Order Fulfillment"]
flines0 = sheets["Fulfillment Lines"]
invoices0 = sheets["Invoices"]
credit0 = sheets["Credit Limits"]
contracts0 = sheets["Customer Contracts"]
pricelists0 = sheets["Price Lists"]
discounts0 = sheets["Discounts"]
reports0 = sheets["Sales Reports"]
forecasts0 = sheets["Sales Forecasts"]

NEW_ORDERS = TOTAL_ORDERS - len(orders0)
BASELINE_AVG_ORDER_VALUE = float(
    orders0["Total_Amount"].sum() / len(orders0)
)  # 원본 전체 평균(모든 상태 포함)
print(
    f"\n신규 생성 주문 수: {NEW_ORDERS} (기존 {len(orders0)}건 보존, 목표 총 {TOTAL_ORDERS}건)"
)


# ---------------------------------------------------------------------------
# 2. 품목 카탈로그 (원본 98개 item_id를 그대로 재사용 — 신규 품목 추가 없음)
# ---------------------------------------------------------------------------

item_stats = (
    lines0.groupby("Item_ID")
    .agg(
        description=("Description", "first"),
        mean_price=("Unit_Price", "mean"),
        std_price=("Unit_Price", "std"),
    )
    .reset_index()
)
item_stats["std_price"] = item_stats["std_price"].fillna(item_stats["mean_price"] * 0.1)
item_freq = lines0["Item_ID"].value_counts(normalize=True)
ITEM_IDS = item_stats["Item_ID"].tolist()
ITEM_DESC = dict(zip(item_stats["Item_ID"], item_stats["description"]))
ITEM_MEAN_PRICE = dict(zip(item_stats["Item_ID"], item_stats["mean_price"]))
ITEM_STD_PRICE = dict(zip(item_stats["Item_ID"], item_stats["std_price"]))
ITEM_WEIGHTS = np.array([item_freq.get(i, item_freq.min()) for i in ITEM_IDS])
ITEM_WEIGHTS = ITEM_WEIGHTS / ITEM_WEIGHTS.sum()

UOM_IDS = sorted(lines0["UOM_ID"].dropna().unique().tolist())
UOM_WEIGHTS = lines0["UOM_ID"].value_counts(normalize=True).reindex(UOM_IDS).values
WAREHOUSE_IDS = sorted(lines0["Warehouse_ID"].dropna().unique().tolist())
WAREHOUSE_WEIGHTS = (
    lines0["Warehouse_ID"].value_counts(normalize=True).reindex(WAREHOUSE_IDS).values
)
DISCOUNT_PCT_CHOICES = sorted(lines0["Discount_Percent"].dropna().unique().tolist())
DISCOUNT_PCT_WEIGHTS = (
    lines0["Discount_Percent"]
    .value_counts(normalize=True)
    .reindex(DISCOUNT_PCT_CHOICES)
    .values
)
QTY_LOG_MEAN = np.log(lines0["Quantity"].clip(lower=1)).mean()
QTY_LOG_STD = np.log(lines0["Quantity"].clip(lower=1)).std()

print("\n" + "=" * 70)
print("2. 품목 카탈로그")
print("=" * 70)
print(
    f"  품목 {len(ITEM_IDS)}개, UOM {UOM_IDS}, 창고 {WAREHOUSE_IDS}, 할인율 후보 {DISCOUNT_PCT_CHOICES}"
)


def sample_item() -> int:
    return int(RNG.choice(ITEM_IDS, p=ITEM_WEIGHTS))


def sample_unit_price(item_id: int, scale: float) -> float:
    mean = ITEM_MEAN_PRICE[item_id] * scale
    std = max(ITEM_STD_PRICE[item_id] * scale, mean * 0.03)
    price = RNG.normal(mean, std)
    return round(max(price, 0.5), 4)


def sample_quantity(scale: float = 1.0) -> int:
    qty = np.exp(RNG.normal(QTY_LOG_MEAN, QTY_LOG_STD)) * scale
    return int(max(1, round(qty)))


def sample_discount_percent() -> float:
    return float(RNG.choice(DISCOUNT_PCT_CHOICES, p=DISCOUNT_PCT_WEIGHTS))


def sample_uom() -> int:
    return int(RNG.choice(UOM_IDS, p=UOM_WEIGHTS))


def sample_warehouse() -> int:
    return int(RNG.choice(WAREHOUSE_IDS, p=WAREHOUSE_WEIGHTS))


# ---------------------------------------------------------------------------
# 3. 신규 고객 생성
# ---------------------------------------------------------------------------

print("\n" + "=" * 70)
print("3. 신규 고객 생성")
print("=" * 70)

CITY_POOL = [
    "Amman",
    "Zarqa",
    "Irbid",
    "Aqaba",
    "Mafraq",
    "Karak",
    "Jerash",
    "Salt",
    "Madaba",
    "Dubai",
    "Doha",
    "Riyadh",
]
STREET_POOL = [
    "University St",
    "Zahran St",
    "Mecca St",
    "King Abdullah II St",
    "Rainbow St",
    "Wasfi Al-Tal St",
    "Istiqlal St",
    "Prince Mohammed St",
    "Al-Madina St",
    "Airport Rd",
]
NAME_PREFIX = [
    "Jordan",
    "Petra",
    "Aqaba",
    "Amman",
    "Al-Ittihad",
    "Zad",
    "Golden",
    "Royal",
    "National",
    "United",
    "Nile",
    "Desert Rose",
    "Cedar",
    "Gulf",
    "Levant",
    "Nour",
    "Al-Rawabi",
    "Sahara",
]
NAME_CORE = {
    "Banking": ["Bank", "Financial Group", "Capital"],
    "Energy": ["Energy", "Power", "Petroleum", "Gas"],
    "Public Sector": ["Municipal Services", "Public Works", "Authority"],
    "Pharmaceutical": ["Pharmaceuticals", "Pharma", "Life Sciences", "Medical Labs"],
    "Logistics": ["Logistics", "Freight", "Shipping", "Cargo"],
    "FMCG": ["Foods", "Consumer Goods", "Trading", "Mills"],
    "Construction": ["Construction", "Contracting", "Engineering", "Builders"],
    "Manufacturing": ["Industries", "Manufacturing", "Steel", "Textiles"],
    "Telecom": ["Telecom", "Communications", "Networks"],
}
NAME_SUFFIX = ["Co.", "Group", "Ltd.", "PLC", "Trading Co.", "Holdings", ""]

CUST_TYPE_CHOICES = customers0["Customer_Type"].value_counts(normalize=True)
INDUSTRY_CHOICES = customers0["Industry"].value_counts(normalize=True)
COUNTRY_CHOICES = customers0["Country"].value_counts(normalize=True)
PAYMENT_TERMS_CHOICES = customers0["Payment_Terms"].value_counts(normalize=True)

existing_names = set(customers0["Customer_Name"])


def gen_company_name(industry: str) -> str:
    for _ in range(50):
        prefix = RNG.choice(NAME_PREFIX)
        core = RNG.choice(NAME_CORE.get(industry, ["Trading", "Group"]))
        suffix = RNG.choice(NAME_SUFFIX)
        name = " ".join(p for p in [prefix, core, suffix] if p)
        if name not in existing_names:
            existing_names.add(name)
            return name
    raise RuntimeError("회사명 생성 충돌이 반복됨 — NAME_PREFIX/CORE 풀을 늘려야 함")


def name_to_slug(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalpha())[:14]


def gen_phone() -> str:
    area = RNG.choice([77, 78, 79])
    mid = int(RNG.integers(100, 999))
    last = int(RNG.integers(1000, 9999))
    return f"+962 {area} {mid} {last}"


new_customers = []
next_customer_id = int(customers0["Customer_ID"].max()) + 1
for i in range(NEW_CUSTOMERS):
    acquire_frac = i / max(NEW_CUSTOMERS - 1, 1)  # 0=가장 먼저 생김(과거), 1=가장 최근
    acquire_date = DATE_START + timedelta(
        days=int(acquire_frac * days_between(DATE_START, DATE_END - timedelta(days=30)))
    )
    industry = str(RNG.choice(INDUSTRY_CHOICES.index, p=INDUSTRY_CHOICES.values))
    country = str(RNG.choice(COUNTRY_CHOICES.index, p=COUNTRY_CHOICES.values))
    ctype = str(RNG.choice(CUST_TYPE_CHOICES.index, p=CUST_TYPE_CHOICES.values))
    pterm = str(RNG.choice(PAYMENT_TERMS_CHOICES.index, p=PAYMENT_TERMS_CHOICES.values))
    name = gen_company_name(industry)

    # D-5: 오래 전에 유입된 고객일수록 지금까지 살아남아 활성 상태일 확률이 낮다(이탈 누적).
    inactive_prob = 0.32 * (1 - acquire_frac)
    is_active = bool(RNG.random() > inactive_prob)

    created_dt = combine(acquire_date)
    updated_dt = combine(
        min(DATE_END, acquire_date + timedelta(days=int(RNG.integers(0, 400))))
    )

    new_customers.append(
        {
            "Customer_ID": next_customer_id + i,
            "Company_ID": 1,
            "Customer_Code": f"CUS-{next_customer_id + i:04d}",
            "Customer_Name": name,
            "Customer_Type": ctype,
            "Industry": industry,
            "Contact_Person": f"{RNG.choice(['Amal','Zeina','Huda','Rami','Sara','Nour','Yousef','Dana','Omar','Lina','Hadi','Rana'])} {RNG.choice(['Sawalha','Odeh','Khoury','Haddad','Qasim','Barakat','Nasser','Salameh'])}",
            "Email": f"procurement@{name_to_slug(name)}.com",
            "Phone_Number": gen_phone(),
            "Billing_Address": f"{int(RNG.integers(1, 130))} {RNG.choice(STREET_POOL)}, {RNG.choice(CITY_POOL)}",
            "Shipping_Address": f"{int(RNG.integers(1, 130))} {RNG.choice(STREET_POOL)}, {RNG.choice(CITY_POOL)}",
            "Country": country,
            "Tax_ID": int(RNG.integers(100000000, 999999999)),
            "Currency": "JOD",
            "Payment_Terms": pterm,
            "Account_Manager_ID": int(RNG.integers(25, 29)),
            "Is_Active": is_active,
            "Created_At": created_dt,
            "Updated_At": updated_dt,
            "Created_By_User_ID": int(RNG.integers(1, rep_pool_max(acquire_date) + 1)),
            "_acquire_date": acquire_date,  # 내부용, 최종 저장 전 제거
        }
    )

new_customers_df = pd.DataFrame(new_customers)
customers_all = pd.concat(
    [
        customers0.assign(
            _acquire_date=pd.to_datetime(customers0["Created_At"]).dt.date
        ),
        new_customers_df,
    ],
    ignore_index=True,
)
print(f"  신규 고객 {len(new_customers_df)}명 생성 (총 {len(customers_all)}명)")
print(
    f"  비활성 고객: {(~customers_all['Is_Active']).sum()}명 / {len(customers_all)}명"
)

CUSTOMER_SHIP_ADDR = dict(
    zip(customers_all["Customer_ID"], customers_all["Shipping_Address"])
)
CUSTOMER_PAYMENT_TERMS = dict(
    zip(customers_all["Customer_ID"], customers_all["Payment_Terms"])
)
CUSTOMER_TYPE = dict(zip(customers_all["Customer_ID"], customers_all["Customer_Type"]))
CUSTOMER_ACQUIRE = dict(
    zip(customers_all["Customer_ID"], customers_all["_acquire_date"])
)


def eligible_customers(order_date: date) -> list[int]:
    return [cid for cid, acq in CUSTOMER_ACQUIRE.items() if acq <= order_date]


def pick_customer(order_date: date) -> int:
    pool = eligible_customers(order_date)
    weights = np.array(
        [1.5 if CUSTOMER_TYPE[c] in ("Corporate", "Government") else 1.0 for c in pool]
    )
    weights = weights / weights.sum()
    return int(RNG.choice(pool, p=weights))


# ---------------------------------------------------------------------------
# 4. 신규 주문 + 주문상세 + (연동) 견적 생성
# ---------------------------------------------------------------------------

print("\n" + "=" * 70)
print("4. 신규 주문 생성")
print("=" * 70)

ORDER_STATUS_CHOICES = orders0["Status"].value_counts(normalize=True)
LINES_PER_ORDER = (
    lines0.groupby("Sales_Order_ID").size().value_counts(normalize=True).sort_index()
)
QUOTE_LINK_RATE = orders0["Quote_ID"].notna().mean()
APPROVAL_RATE = orders0["Approval_Request_ID"].notna().mean()

next_order_id = int(orders0["Sales_Order_ID"].max()) + 1
next_line_id = int(lines0["Sales_Order_Line_ID"].max()) + 1
next_quote_id = int(quotes0["Sales_Quote_ID"].max()) + 1
next_qline_id = int(qlines0["Sales_Quote_Line_ID"].max()) + 1
next_approval_id = int(orders0["Approval_Request_ID"].dropna().max()) + 1

# 연도별로 "원본에 이미 있는 만큼"을 뺀 나머지를 신규 주문으로 채운다.
orders0_dated = orders0.assign(_d=pd.to_datetime(orders0["Order_Date"]).dt.date)
band_plan = []
for y, b in sorted(YEAR_TARGETS.items()):
    in_year = orders0_dated[
        (orders0_dated["_d"] >= b["start"]) & (orders0_dated["_d"] <= b["end"])
    ]
    orig_count = len(in_year)
    orig_revenue = float(in_year["Total_Amount"].sum())
    new_count = b["target_count"] - orig_count
    new_revenue = max(
        b["target_revenue"] - orig_revenue, new_count * BASELINE_AVG_ORDER_VALUE * 0.02
    )
    avg_value = new_revenue / new_count if new_count > 0 else 0.0
    scale = float(np.clip(np.sqrt(avg_value / BASELINE_AVG_ORDER_VALUE), 0.05, 3.0))
    band_plan.append(
        {
            "year": y,
            **b,
            "orig_count": orig_count,
            "orig_revenue": orig_revenue,
            "new_count": new_count,
            "new_avg_value": avg_value,
            "scale": scale,
        }
    )

print("\n  연도별 계획 (기간 / 원본건수·금액 / 신규건수 / 신규평균값 / 스케일):")
for bp in band_plan:
    print(
        f"    {bp['year']} ({bp['start']}~{bp['end']})  원본 {bp['orig_count']}건/{bp['orig_revenue']:,.0f}  ->  신규 {bp['new_count']}건, 평균 {bp['new_avg_value']:,.0f}, scale={bp['scale']:.3f}"
    )

assert (
    sum(bp["new_count"] for bp in band_plan) == NEW_ORDERS
), "연도별 신규 건수 합이 NEW_ORDERS와 안 맞음"

# (order_date를 뽑을 연도, 그 해의 price/qty scale)의 목록으로 미리 펼쳐둔다.
order_plan = []
for bp in band_plan:
    for _ in range(bp["new_count"]):
        d = random_date(bp["start"], bp["end"])
        order_plan.append((d, bp["scale"]))
RNG.shuffle(order_plan)

new_orders = []
new_lines = []
new_quotes_linked = []
new_qlines_linked = []

for k, (order_date, scale) in enumerate(order_plan):
    order_id = next_order_id + k

    customer_id = pick_customer(order_date)
    status = str(RNG.choice(ORDER_STATUS_CHOICES.index, p=ORDER_STATUS_CHOICES.values))
    rep_id = int(RNG.integers(1, rep_pool_max(order_date) + 1))

    n_lines = int(RNG.choice(LINES_PER_ORDER.index, p=LINES_PER_ORDER.values))
    order_created = combine(order_date)

    line_rows = []
    for line_no in range(1, n_lines + 1):
        item_id = sample_item()
        qty = sample_quantity(scale)
        price = sample_unit_price(item_id, scale)
        disc_pct = sample_discount_percent()
        line_total = round(qty * price * (1 - disc_pct / 100), 2)
        tax_amt = round(line_total * TAX_RATE, 2)

        # 원본 실측 규칙(결측치 0%): Invoiced/Delivered/Shipped=전량 배송,
        # Partially Shipped=평균 70%(표준편차 13.5%) 부분 배송,
        # Confirmed/Cancelled/Draft=아직 배송 전이라 0(NaN 아님).
        if status in ("Invoiced", "Delivered", "Shipped"):
            qty_delivered = float(qty)
        elif status == "Partially Shipped":
            ratio = float(np.clip(RNG.normal(0.70, 0.135), 0.3, 0.95))
            qty_delivered = float(round(qty * ratio))
        else:
            qty_delivered = 0.0

        line_rows.append(
            {
                "Sales_Order_Line_ID": next_line_id,
                "Company_ID": 1,
                "Sales_Order_ID": order_id,
                "Line_Number": line_no,
                "Item_ID": item_id,
                "Description": ITEM_DESC[item_id],
                "UOM_ID": sample_uom(),
                "Quantity": qty,
                "Unit_Price": price,
                "Discount_Percent": disc_pct,
                "Tax_Code_ID": 1,
                "Tax_Amount": tax_amt,
                "Line_Total": line_total,
                "Quantity_Delivered": qty_delivered,
                "Warehouse_ID": sample_warehouse(),
                "Created_At": order_created,
                "Updated_At": combine(
                    min(DATE_END, order_date + timedelta(days=int(RNG.integers(0, 8))))
                ),
                "Created_By_User_ID": rep_id,
            }
        )
        next_line_id += 1

    subtotal = round(sum(r["Line_Total"] for r in line_rows), 2)
    tax_amount = round(sum(r["Tax_Amount"] for r in line_rows), 2)
    total_amount = round(
        subtotal + tax_amount, 2
    )  # D-2: 할인은 총액에 반영 안 함(원본 재현)
    disc_pct_header = float(np.clip(RNG.normal(2.78, 3.59), 0, 15))
    discount_amount = round(subtotal * disc_pct_header / 100, 2)

    quote_id = np.nan
    if RNG.random() < QUOTE_LINK_RATE:
        quote_date = order_date - timedelta(days=int(RNG.integers(5, 30)))
        if quote_date >= DATE_START:
            quote_id = next_quote_id
            new_quotes_linked.append(
                {
                    "Sales_Quote_ID": next_quote_id,
                    "Company_ID": 1,
                    "Customer_ID": customer_id,
                    "Quote_Number": f"SQ-{quote_date.year}-{next_quote_id:05d}",
                    "Quote_Date": quote_date,
                    "Valid_Until": quote_date + timedelta(days=30),
                    "Sales_Rep_ID": rep_id,
                    "Subtotal": subtotal,
                    "Discount_Amount": discount_amount,
                    "Tax_Amount": tax_amount,
                    "Total_Amount": total_amount,
                    "Currency": "JOD",
                    "Notes": str(
                        RNG.choice(
                            [
                                "Delivery ex-works Amman.",
                                "Lead time subject to stock availability.",
                                "Volume discount applied.",
                                "Standard commercial terms apply.",
                            ]
                        )
                    ),
                    "Status": "Accepted",
                    "Created_At": combine(quote_date),
                    "Updated_At": combine(
                        quote_date + timedelta(days=int(RNG.integers(1, 6)))
                    ),
                    "Created_By_User_ID": rep_id,
                }
            )
            for qr in line_rows:
                new_qlines_linked.append(
                    {
                        "Sales_Quote_Line_ID": next_qline_id,
                        "Company_ID": 1,
                        "Sales_Quote_ID": quote_id,
                        "Line_Number": qr["Line_Number"],
                        "Item_ID": qr["Item_ID"],
                        "Description": qr["Description"],
                        "UOM_ID": qr["UOM_ID"],
                        "Quantity": qr["Quantity"],
                        "Unit_Price": qr["Unit_Price"],
                        "Discount_Percent": qr["Discount_Percent"],
                        "Tax_Code_ID": 1,
                        "Tax_Amount": qr["Tax_Amount"],
                        "Line_Total": qr["Line_Total"],
                        "Created_At": combine(quote_date),
                        "Updated_At": combine(
                            quote_date + timedelta(days=int(RNG.integers(1, 6)))
                        ),
                        "Created_By_User_ID": rep_id,
                    }
                )
                next_qline_id += 1
            next_quote_id += 1

    approval_id = np.nan
    if RNG.random() < APPROVAL_RATE:
        approval_id = next_approval_id
        next_approval_id += 1

    new_orders.append(
        {
            "Sales_Order_ID": order_id,
            "Company_ID": 1,
            "Customer_ID": customer_id,
            "Quote_ID": quote_id,
            "Order_Number": f"SO-{order_date.year}-{order_id:05d}",
            "Order_Date": order_date,
            "Required_Delivery_Date": order_date
            + timedelta(days=int(RNG.choice([7, 14, 21], p=[0.25, 0.5, 0.25]))),
            "Delivery_Address": CUSTOMER_SHIP_ADDR[customer_id],
            "Sales_Rep_ID": rep_id,
            "Subtotal": subtotal,
            "Discount_Amount": discount_amount,
            "Tax_Amount": tax_amount,
            "Total_Amount": total_amount,
            "Currency": "JOD",
            "Payment_Terms": CUSTOMER_PAYMENT_TERMS[customer_id],
            "Status": status,
            "Approval_Request_ID": approval_id,
            "Created_At": order_created,
            "Updated_At": combine(
                min(DATE_END, order_date + timedelta(days=int(RNG.integers(0, 10))))
            ),
            "Created_By_User_ID": rep_id,
            "_disc_pct_header": disc_pct_header,
            "_year": order_date.year,
        }
    )
    new_lines.extend(line_rows)

new_orders_df = pd.DataFrame(new_orders)
new_lines_df = pd.DataFrame(new_lines)
print(f"  신규 주문(보정 전) {len(new_orders_df)}건, 신규 라인 {len(new_lines_df)}건")
print(
    f"  견적 연동 주문 {len(new_quotes_linked)}건 (연동률 목표 {QUOTE_LINK_RATE:.2%})"
)

# ---------------------------------------------------------------------------
# 4-보정. 표본 변동으로 연도별 실제 매출이 목표와 어긋나는 만큼 단가에
# 보정 배율을 곱해 정확히 맞춘다. 공식(라인합계=수량*단가*(1-할인율), 세금=16%,
# 총액=소계+세금)은 그대로 유지한 채 "크기"만 보정한다.
# ---------------------------------------------------------------------------

new_lines_df = new_lines_df.merge(
    new_orders_df[["Sales_Order_ID", "_year"]], on="Sales_Order_ID", how="left"
)
year_correction: dict[int, float] = {}
for bp in band_plan:
    y = bp["year"]
    mask = new_lines_df["_year"] == y
    if not mask.any():
        continue
    actual_new_subtotal = float(new_lines_df.loc[mask, "Line_Total"].sum())
    actual_new_revenue = actual_new_subtotal * (1 + TAX_RATE)
    target_new_revenue = bp["target_revenue"] - bp["orig_revenue"]
    if actual_new_revenue <= 0 or target_new_revenue <= 0:
        year_correction[y] = 1.0
        continue
    correction = float(np.clip(target_new_revenue / actual_new_revenue, 0.2, 4.0))
    year_correction[y] = correction
    new_lines_df.loc[mask, "Unit_Price"] = (
        new_lines_df.loc[mask, "Unit_Price"] * correction
    ).round(4)

print("\n  연도별 보정 배율:", {y: round(c, 3) for y, c in year_correction.items()})

# 보정된 단가로 라인합계·세금을 다시 계산한다(공식은 위와 동일).
new_lines_df["Line_Total"] = (
    new_lines_df["Quantity"]
    * new_lines_df["Unit_Price"]
    * (1 - new_lines_df["Discount_Percent"] / 100)
).round(2)
new_lines_df["Tax_Amount"] = (new_lines_df["Line_Total"] * TAX_RATE).round(2)

# 헤더(Subtotal/Tax_Amount/Total_Amount/Discount_Amount)를 보정된 라인으로 재집계한다.
header_agg = (
    new_lines_df.groupby("Sales_Order_ID")
    .agg(Subtotal=("Line_Total", "sum"), Tax_Amount=("Tax_Amount", "sum"))
    .round(2)
)
new_orders_df = new_orders_df.drop(
    columns=["Subtotal", "Tax_Amount", "Total_Amount", "Discount_Amount"]
).merge(header_agg, on="Sales_Order_ID", how="left")
new_orders_df["Total_Amount"] = (
    new_orders_df["Subtotal"] + new_orders_df["Tax_Amount"]
).round(2)
new_orders_df["Discount_Amount"] = (
    new_orders_df["Subtotal"] * new_orders_df["_disc_pct_header"] / 100
).round(2)

# 연동된 견적(및 견적상세)도 같은 연도 보정 배율을 적용해 주문과 금액이 계속 일치하게 한다.
if new_quotes_linked:
    quotes_linked_df = pd.DataFrame(new_quotes_linked)
    qlines_linked_df = pd.DataFrame(new_qlines_linked)
    quote_year = dict(
        zip(
            new_orders_df["Quote_ID"].dropna(),
            new_orders_df.loc[new_orders_df["Quote_ID"].notna(), "_year"],
        )
    )
    qlines_linked_df["_corr"] = (
        qlines_linked_df["Sales_Quote_ID"]
        .map(quote_year)
        .map(year_correction)
        .fillna(1.0)
    )
    qlines_linked_df["Unit_Price"] = (
        qlines_linked_df["Unit_Price"] * qlines_linked_df["_corr"]
    ).round(4)
    qlines_linked_df["Line_Total"] = (
        qlines_linked_df["Quantity"]
        * qlines_linked_df["Unit_Price"]
        * (1 - qlines_linked_df["Discount_Percent"] / 100)
    ).round(2)
    qlines_linked_df["Tax_Amount"] = (qlines_linked_df["Line_Total"] * TAX_RATE).round(
        2
    )
    qlines_linked_df = qlines_linked_df.drop(columns=["_corr"])
    q_header_agg = (
        qlines_linked_df.groupby("Sales_Quote_ID")
        .agg(Subtotal=("Line_Total", "sum"), Tax_Amount=("Tax_Amount", "sum"))
        .round(2)
    )
    quotes_linked_df = quotes_linked_df.drop(
        columns=["Subtotal", "Tax_Amount", "Total_Amount"]
    ).merge(q_header_agg, on="Sales_Quote_ID", how="left")
    quotes_linked_df["Total_Amount"] = (
        quotes_linked_df["Subtotal"] + quotes_linked_df["Tax_Amount"]
    ).round(2)
    quotes_linked_df["Discount_Amount"] = 0.0
else:
    quotes_linked_df = pd.DataFrame(columns=quotes0.columns)
    qlines_linked_df = pd.DataFrame(columns=qlines0.columns)

new_lines_df = new_lines_df.drop(columns=["_year"])
new_orders_df = new_orders_df.drop(columns=["_disc_pct_header"])

orders_all = pd.concat(
    [orders0, new_orders_df.drop(columns=["_year"])], ignore_index=True
)
lines_all = pd.concat([lines0, new_lines_df], ignore_index=True)

# 연도별 집계로 "건수 증가 / 매출 감소" 추세가 실제로 나오는지 확인
orders_all["_year"] = pd.to_datetime(orders_all["Order_Date"]).dt.year
valid_mask = ~orders_all["Status"].isin(["Cancelled", "Draft"])
yearly = (
    orders_all[valid_mask]
    .groupby("_year")
    .agg(order_count=("Sales_Order_ID", "count"), total_revenue=("Total_Amount", "sum"))
)
print("\n  연도별 집계 (취소/초안 제외):")
print(yearly.to_string())


# ---------------------------------------------------------------------------
# 5. 배송(Order Fulfillment) + 배송상세(Fulfillment Lines)
#    원본 규칙(실측): 주문 상태가 Invoiced/Delivered/Shipped/Partially Shipped일
#    때만 배송 레코드가 있다 (원본 56건 = 정확히 이 네 상태의 합).
# ---------------------------------------------------------------------------

print("\n" + "=" * 70)
print("5. 배송/배송상세 생성")
print("=" * 70)

FULFILLABLE_STATUS = {"Invoiced", "Delivered", "Shipped", "Partially Shipped"}
CARRIER_CHOICES = fulfill0["Carrier"].value_counts(normalize=True)

next_fulfill_id = int(fulfill0["Fulfillment_ID"].max()) + 1
next_fline_id = int(flines0["Fulfillment_Line_ID"].max()) + 1

new_fulfill = []
new_flines = []
order_to_fulfill_id: dict[int, int] = {}

lines_by_order = new_lines_df.groupby("Sales_Order_ID")
for _, o in new_orders_df.iterrows():
    if o["Status"] not in FULFILLABLE_STATUS:
        continue
    fid = next_fulfill_id
    order_to_fulfill_id[int(o["Sales_Order_ID"])] = fid
    order_date = o["Order_Date"]
    ship_date = order_date + timedelta(days=int(RNG.integers(5, 15)))
    ship_date = min(ship_date, DATE_END)
    is_delivered = o["Status"] in ("Invoiced", "Delivered")
    delivery_date = ship_date + timedelta(days=int(RNG.integers(2, 8)))
    rep_id = int(o["Sales_Rep_ID"])

    new_fulfill.append(
        {
            "Fulfillment_ID": fid,
            "Company_ID": 1,
            "Order_ID": int(o["Sales_Order_ID"]),
            "Shipment_Number": f"SHP-{ship_date.year}-{fid:05d}",
            "Shipment_Date": ship_date,
            "Carrier": str(RNG.choice(CARRIER_CHOICES.index, p=CARRIER_CHOICES.values)),
            "Tracking_Number": f"TRK{int(RNG.integers(1000000000, 9999999999))}",
            "Delivery_Date": delivery_date,
            "Packed_By_User_ID": int(RNG.integers(1, rep_pool_max(order_date) + 1)),
            "Shipped_By_User_ID": int(RNG.integers(1, rep_pool_max(order_date) + 1)),
            "Status": "Delivered" if is_delivered else "In Transit",
            "Notes": (
                "Signed POD on file."
                if is_delivered
                else "Awaiting delivery confirmation."
            ),
            "Created_At": combine(ship_date),
            "Updated_At": combine(delivery_date),
            "Created_By_User_ID": rep_id,
        }
    )

    if int(o["Sales_Order_ID"]) in lines_by_order.groups:
        for _, ln in lines_by_order.get_group(int(o["Sales_Order_ID"])).iterrows():
            # 원본 실측: Delivered/In Transit 상관없이 Quantity_Shipped는 항상 Quantity와 동일(결측 0%, ratio 1.0).
            qty_shipped = float(ln["Quantity"])
            new_flines.append(
                {
                    "Fulfillment_Line_ID": next_fline_id,
                    "Company_ID": 1,
                    "Fulfillment_ID": fid,
                    "Sales_Order_Line_ID": int(ln["Sales_Order_Line_ID"]),
                    "Line_Number": int(ln["Line_Number"]),
                    "Item_ID": int(ln["Item_ID"]),
                    "Description": ln["Description"],
                    "UOM_ID": int(ln["UOM_ID"]),
                    "Quantity": float(ln["Quantity"]),
                    "Unit_Price": ln["Unit_Price"],
                    "Discount_Percent": ln["Discount_Percent"],
                    "Tax_Code_ID": 1,
                    "Tax_Amount": ln["Tax_Amount"],
                    "Line_Total": ln["Line_Total"],
                    "Quantity_Shipped": qty_shipped,
                    "Warehouse_ID": int(ln["Warehouse_ID"]),
                    "Created_At": combine(ship_date),
                    "Updated_At": combine(delivery_date),
                    "Created_By_User_ID": rep_id,
                }
            )
            next_fline_id += 1
    next_fulfill_id += 1

new_fulfill_df = pd.DataFrame(new_fulfill)
new_flines_df = pd.DataFrame(new_flines)
print(
    f"  신규 배송 {len(new_fulfill_df)}건, 배송상세 {len(new_flines_df)}건 (자격 주문 {new_orders_df['Status'].isin(FULFILLABLE_STATUS).sum()}건 중)"
)


# ---------------------------------------------------------------------------
# 6. 청구서(Invoices) — 배송이 있는 주문에서만 발행 (원본 관측과 동일 패턴)
# ---------------------------------------------------------------------------

print("\n" + "=" * 70)
print("6. 청구서 생성")
print("=" * 70)

INVOICE_STATUS_CHOICES = invoices0["Status"].value_counts(normalize=True)
INVOICE_RATE_GIVEN_FULFILLED = len(invoices0) / len(fulfill0)  # 53/56

PAYMENT_TERMS_DAYS = {"NET30": 30, "NET45": 45, "NET60": 60, "2/10N30": 30}

next_invoice_id = int(invoices0["Invoice_ID"].max()) + 1

new_invoices = []
for _, o in new_orders_df.iterrows():
    oid = int(o["Sales_Order_ID"])
    if oid not in order_to_fulfill_id:
        continue
    if RNG.random() >= INVOICE_RATE_GIVEN_FULFILLED:
        continue

    fid = order_to_fulfill_id[oid]
    order_date = o["Order_Date"]
    invoice_date = order_date + timedelta(days=int(RNG.integers(10, 25)))
    invoice_date = min(invoice_date, DATE_END)
    terms = o["Payment_Terms"]
    due_date = invoice_date + timedelta(days=PAYMENT_TERMS_DAYS.get(terms, 30))

    status = str(
        RNG.choice(INVOICE_STATUS_CHOICES.index, p=INVOICE_STATUS_CHOICES.values)
    )
    total = float(o["Total_Amount"])
    if status == "Paid":
        amount_paid, outstanding = total, 0.0
    elif status in ("Overdue", "Unpaid"):
        amount_paid, outstanding = 0.0, total
    else:  # Partially Paid
        amount_paid = round(total * RNG.uniform(0.2, 0.8), 2)
        outstanding = round(total - amount_paid, 2)

    iid = next_invoice_id
    new_invoices.append(
        {
            "Invoice_ID": iid,
            "Company_ID": 1,
            "Fulfillment_ID": fid,
            "Customer_ID": int(o["Customer_ID"]),
            "Order_ID": oid,
            "Invoice_Number": f"INV-{invoice_date.year}-{iid:05d}",
            "Invoice_Date": invoice_date,
            "Due_Date": due_date,
            "Subtotal": float(o["Subtotal"]),
            "Tax_Amount": float(o["Tax_Amount"]),
            "Total_Amount": total,
            "Amount_Paid": amount_paid,
            "Outstanding_Amount": outstanding,
            "Currency": "JOD",
            "Payment_Terms": terms,
            "Status": status,
            "Customer_Invoice_ID": iid,
            "Created_At": combine(invoice_date),
            "Updated_At": combine(
                min(DATE_END, invoice_date + timedelta(days=int(RNG.integers(0, 5))))
            ),
            "Created_By_User_ID": int(o["Sales_Rep_ID"]),
        }
    )
    next_invoice_id += 1

new_invoices_df = pd.DataFrame(new_invoices)
print(f"  신규 청구서 {len(new_invoices_df)}건")


# ---------------------------------------------------------------------------
# 7. 단독 견적(주문으로 전환되지 않은 견적) — 원본 관측: Accepted 상태는 전부
#    주문으로 연동됐고, 단독으로 남는 견적은 Sent/Draft/Expired/Rejected뿐이었다.
# ---------------------------------------------------------------------------

print("\n" + "=" * 70)
print("7. 단독 견적 생성")
print("=" * 70)

QUOTE_TOTAL_TARGET = int(
    round(TOTAL_ORDERS * len(quotes0) / len(orders0))
)  # 800 * 60/70
linked_new_quote_count = len(quotes_linked_df)
standalone_target = QUOTE_TOTAL_TARGET - len(quotes0) - linked_new_quote_count
standalone_target = max(standalone_target, 0)

STANDALONE_QUOTE_STATUS = quotes0[quotes0["Status"] != "Accepted"][
    "Status"
].value_counts(normalize=True)
QUOTE_NOTES_POOL = quotes0["Notes"].dropna().unique().tolist()

new_quotes_standalone = []
new_qlines_standalone = []

for _ in range(standalone_target):
    quote_id = next_quote_id
    quote_date = random_date(DATE_START, DATE_END)
    scale = next(
        (bp["scale"] for bp in band_plan if bp["year"] == quote_date.year), 1.0
    )
    customer_id = pick_customer(quote_date)
    rep_id = int(RNG.integers(1, rep_pool_max(quote_date) + 1))
    status = str(
        RNG.choice(STANDALONE_QUOTE_STATUS.index, p=STANDALONE_QUOTE_STATUS.values)
    )

    n_lines = int(RNG.choice(LINES_PER_ORDER.index, p=LINES_PER_ORDER.values))
    q_lines = []
    for line_no in range(1, n_lines + 1):
        item_id = sample_item()
        qty = sample_quantity(scale)
        price = sample_unit_price(item_id, scale)
        disc_pct = sample_discount_percent()
        line_total = round(qty * price * (1 - disc_pct / 100), 2)
        tax_amt = round(line_total * TAX_RATE, 2)
        q_lines.append(
            {
                "Sales_Quote_Line_ID": next_qline_id,
                "Company_ID": 1,
                "Sales_Quote_ID": quote_id,
                "Line_Number": line_no,
                "Item_ID": item_id,
                "Description": ITEM_DESC[item_id],
                "UOM_ID": sample_uom(),
                "Quantity": qty,
                "Unit_Price": price,
                "Discount_Percent": disc_pct,
                "Tax_Code_ID": 1,
                "Tax_Amount": tax_amt,
                "Line_Total": line_total,
                "Created_At": combine(quote_date),
                "Updated_At": combine(
                    min(DATE_END, quote_date + timedelta(days=int(RNG.integers(0, 6))))
                ),
                "Created_By_User_ID": rep_id,
            }
        )
        next_qline_id += 1

    subtotal = round(sum(r["Line_Total"] for r in q_lines), 2)
    tax_amount = round(sum(r["Tax_Amount"] for r in q_lines), 2)
    total_amount = round(subtotal + tax_amount, 2)
    disc_pct_header = float(np.clip(RNG.normal(2.78, 3.59), 0, 15))

    new_quotes_standalone.append(
        {
            "Sales_Quote_ID": quote_id,
            "Company_ID": 1,
            "Customer_ID": customer_id,
            "Quote_Number": f"SQ-{quote_date.year}-{quote_id:05d}",
            "Quote_Date": quote_date,
            "Valid_Until": quote_date + timedelta(days=30),
            "Sales_Rep_ID": rep_id,
            "Subtotal": subtotal,
            "Discount_Amount": round(subtotal * disc_pct_header / 100, 2),
            "Tax_Amount": tax_amount,
            "Total_Amount": total_amount,
            "Currency": "JOD",
            "Notes": str(RNG.choice(QUOTE_NOTES_POOL)) if QUOTE_NOTES_POOL else "",
            "Status": status,
            "Created_At": combine(quote_date),
            "Updated_At": combine(
                min(DATE_END, quote_date + timedelta(days=int(RNG.integers(1, 20))))
            ),
            "Created_By_User_ID": rep_id,
        }
    )
    new_qlines_standalone.extend(q_lines)
    next_quote_id += 1

new_quotes_standalone_df = pd.DataFrame(new_quotes_standalone)
new_qlines_standalone_df = pd.DataFrame(new_qlines_standalone)
quotes_all_new = pd.concat(
    [quotes_linked_df, new_quotes_standalone_df], ignore_index=True
)
qlines_all_new = pd.concat(
    [qlines_linked_df, new_qlines_standalone_df], ignore_index=True
)
print(
    f"  단독 견적 {len(new_quotes_standalone_df)}건 (연동 {linked_new_quote_count}건 + 단독 {len(new_quotes_standalone_df)}건 = 총 신규 {len(quotes_all_new)}건, 목표 {QUOTE_TOTAL_TARGET - len(quotes0)}건)"
)


# ---------------------------------------------------------------------------
# 8. 참조성 테이블: 가격표 / 여신한도 / 고객계약 / 할인
#    (주문량이 아니라 "고객 수" 증가 비율에 맞춰 스케일한다)
# ---------------------------------------------------------------------------

print("\n" + "=" * 70)
print("8. 참조성 테이블 생성 (가격표/여신한도/계약/할인)")
print("=" * 70)

new_customer_ids = new_customers_df["Customer_ID"].tolist()

# 8-1. 여신한도 (신규 고객 1인당 1건)
CREDIT_RATING_CHOICES = credit0["Credit_Rating"].value_counts(normalize=True)
next_credit_id = int(credit0["Credit_Limit_ID"].max()) + 1
new_credit = []
for cid in new_customer_ids:
    acquire_d = CUSTOMER_ACQUIRE[cid]
    limit_amt = round(float(RNG.uniform(2000, 45000)), 2)
    # 원본 실측: 노출액은 한도의 0~60%가 아니라 훨씬 작다(중앙값 2.3%, 평균 10.8%,
    # log(비율) 평균 -3.76/표준편차 1.56인 로그정규 분포. 드물게 한도 초과(비율>1)도 있었음).
    exposure_ratio = float(np.exp(RNG.normal(-3.76, 1.56)))
    exposure = round(limit_amt * exposure_ratio, 2)
    new_credit.append(
        {
            "Credit_Limit_ID": next_credit_id,
            "Customer_ID": cid,
            "Credit_Limit_Amount": limit_amt,
            "Currency": "JOD",
            "Current_Exposure": exposure,
            "Available_Credit": round(limit_amt - exposure, 2),
            "Credit_Rating": str(
                RNG.choice(CREDIT_RATING_CHOICES.index, p=CREDIT_RATING_CHOICES.values)
            ),
            "Review_Date": acquire_d + timedelta(days=int(RNG.integers(30, 400))),
            "Approved_By_User_ID": int(RNG.integers(1, rep_pool_max(acquire_d) + 1)),
            "Is_On_Hold": bool(RNG.random() < 0.15),
            "Updated_At": combine(
                min(DATE_END, acquire_d + timedelta(days=int(RNG.integers(30, 500))))
            ),
        }
    )
    next_credit_id += 1
new_credit_df = pd.DataFrame(new_credit)

# 8-2. 고객계약 (신규 고객의 62.5%에게 부여, 원본 25/40 비율)
CONTRACT_STATUS_CHOICES = contracts0["Status"].value_counts(normalize=True)
next_contract_id = int(contracts0["Customer_Contract_ID"].max()) + 1
new_contracts = []
for cid in new_customer_ids:
    if RNG.random() >= 25 / 40:
        continue
    acquire_d = CUSTOMER_ACQUIRE[cid]
    start_d = acquire_d + timedelta(days=int(RNG.integers(0, 60)))
    end_d = start_d + timedelta(days=int(RNG.integers(180, 720)))
    cust_name = next(
        (c["Customer_Name"] for c in new_customers if c["Customer_ID"] == cid), ""
    )
    new_contracts.append(
        {
            "Customer_Contract_ID": next_contract_id,
            "Customer_ID": cid,
            "Contract_Number": f"CC-{start_d.year}-{next_contract_id:05d}",
            "Contract_Name": f"Customer Contract {next_contract_id}",
            "Start_Date": start_d,
            "End_Date": end_d,
            "Total_Value": round(float(RNG.uniform(2000, 60000)), 2),
            "Currency": "JOD",
            "Payment_Terms": f"Customer_Contracts_{next_contract_id}",
            "Auto_Renew": bool(RNG.random() < 0.5),
            "Document_URL": f"https://portal.example-erp.jo/customer-contracts/{next_contract_id}",
            "Status": str(
                RNG.choice(
                    CONTRACT_STATUS_CHOICES.index, p=CONTRACT_STATUS_CHOICES.values
                )
            ),
        }
    )
    next_contract_id += 1
new_contracts_df = pd.DataFrame(new_contracts)

# 8-3. 가격표 (품목 카탈로그 기준, 고객 성장 비율만큼 확대)
SEGMENT_CHOICES = pricelists0["Customer_Segment"].value_counts(normalize=True)
next_pricelist_id = int(pricelists0["Price_List_ID"].max()) + 1
PRICE_LIST_TARGET_NEW = int(round(len(pricelists0) * NEW_CUSTOMERS / len(customers0)))
new_pricelists = []
for _ in range(PRICE_LIST_TARGET_NEW):
    eff_d = random_date(DATE_START, DATE_END)
    item_id = sample_item() if RNG.random() < 0.7 else None
    new_pricelists.append(
        {
            "Price_List_ID": next_pricelist_id,
            "Item_ID": float(item_id) if item_id is not None else np.nan,
            "List_Code": f"PL-{next_pricelist_id:04d}",
            "List_Name": f"Price List {next_pricelist_id}",
            "Currency": "JOD",
            "Effective_Date": eff_d,
            "Expiry_Date": eff_d + timedelta(days=int(RNG.integers(90, 720))),
            "Customer_Segment": str(
                RNG.choice(SEGMENT_CHOICES.index, p=SEGMENT_CHOICES.values)
            ),
            "Is_Active": bool(RNG.random() < 0.75),
        }
    )
    next_pricelist_id += 1
new_pricelists_df = pd.DataFrame(new_pricelists)

# 8-4. 할인 (신규 고객 성장 비율만큼 확대, 가격표/고객 참조)
DISCOUNT_TYPE_CHOICES = discounts0["Discount_Type"].value_counts(normalize=True)
APPLICABLE_TO_CHOICES = discounts0["Applicable_To"].value_counts(normalize=True)
next_discount_id = int(discounts0["Discount_ID"].max()) + 1
DISCOUNT_TARGET_NEW = int(round(len(discounts0) * NEW_CUSTOMERS / len(customers0)))
pricelist_ids_all = (
    pricelists0["Price_List_ID"].tolist() + new_pricelists_df["Price_List_ID"].tolist()
)
new_discounts = []
for _ in range(DISCOUNT_TARGET_NEW):
    valid_from = random_date(DATE_START, DATE_END)
    new_discounts.append(
        {
            "Discount_ID": next_discount_id,
            "Price_List_ID": float(RNG.choice(pricelist_ids_all)),
            "Customer_ID": float(RNG.choice(new_customer_ids)),
            "Discount_Code": f"D-{next_discount_id:04d}",
            "Discount_Name": f"Discount {next_discount_id}",
            "Discount_Type": str(
                RNG.choice(DISCOUNT_TYPE_CHOICES.index, p=DISCOUNT_TYPE_CHOICES.values)
            ),
            "Discount_Value": round(float(RNG.uniform(500, 40000)), 2),
            "Min_Order_Amount": round(float(RNG.uniform(1000, 45000)), 2),
            "Max_Discount_Amount": round(float(RNG.uniform(1000, 25000)), 2),
            "Valid_From": valid_from,
            "Valid_To": valid_from + timedelta(days=int(RNG.integers(30, 400))),
            "Applicable_To": str(
                RNG.choice(APPLICABLE_TO_CHOICES.index, p=APPLICABLE_TO_CHOICES.values)
            ),
            "Is_Active": bool(RNG.random() < 0.6),
        }
    )
    next_discount_id += 1
new_discounts_df = pd.DataFrame(new_discounts)

print(
    f"  여신한도 {len(new_credit_df)}건, 고객계약 {len(new_contracts_df)}건, 가격표 {len(new_pricelists_df)}건, 할인 {len(new_discounts_df)}건"
)


# ---------------------------------------------------------------------------
# 9. Sales Reports / Sales Forecasts
#    원본에서도 Sales_Order_ID/Invoice_ID/Customer_ID가 서로 엄격히 대응하지
#    않는 느슨한 분석용 테이블임을 확인했다(참조 유효성만 유지, 논리적 결합은
#    원본과 동일하게 느슨함). Company_ID 1/2 혼재(D-3)는 이번에 1로 통일한다.
# ---------------------------------------------------------------------------

print("\n" + "=" * 70)
print("9. Sales Reports / Sales Forecasts 생성")
print("=" * 70)

order_ids_all = orders_all["Sales_Order_ID"].tolist()
invoice_ids_all = (
    pd.concat(
        [invoices0["Invoice_ID"], new_invoices_df["Invoice_ID"]], ignore_index=True
    ).tolist()
    if len(new_invoices_df)
    else invoices0["Invoice_ID"].tolist()
)
customer_ids_all = customers_all["Customer_ID"].tolist()

REPORT_TYPE_CHOICES = reports0["Report_Type"].value_counts(normalize=True)
next_report_id = int(reports0["Sales_Report_ID"].max()) + 1
REPORT_TARGET_NEW = max(
    int(round(len(reports0) * TOTAL_ORDERS / len(orders0))) - len(reports0), 0
)
new_reports = []
for _ in range(REPORT_TARGET_NEW):
    gen_d = random_date(DATE_START, DATE_END)
    period_start = gen_d - timedelta(days=int(RNG.integers(30, 240)))
    new_reports.append(
        {
            "Sales_Report_ID": next_report_id,
            "Company_ID": 1,  # D-3: 오염된 2 혼재를 재현하지 않고 1로 통일
            "Sales_Order_ID": float(RNG.choice(order_ids_all)),
            "Invoice_ID": float(RNG.choice(invoice_ids_all)),
            "Customer_ID": float(RNG.choice(customer_ids_all)),
            "Report_Code": f"SR-{next_report_id:04d}",
            "Report_Name": f"Sales Report {next_report_id}",
            "Report_Type": str(
                RNG.choice(REPORT_TYPE_CHOICES.index, p=REPORT_TYPE_CHOICES.values)
            ),
            "Period_Start": period_start,
            "Period_End": gen_d,
            "Total_Revenue": round(float(RNG.uniform(500, 40000)), 2),
            "Orders_Count": int(RNG.integers(1, 45)),
            "Generated_By_User_ID": float(RNG.integers(1, rep_pool_max(gen_d) + 1)),
            "Generated_At": combine(gen_d),
            "Created_At": combine(gen_d),
            "Updated_At": combine(
                min(DATE_END, gen_d + timedelta(days=int(RNG.integers(0, 300))))
            ),
            "Created_By_User_ID": int(RNG.integers(1, rep_pool_max(gen_d) + 1)),
        }
    )
    next_report_id += 1
new_reports_df = pd.DataFrame(new_reports)

FORECAST_METHOD_CHOICES = forecasts0["Forecast_Method"].value_counts(normalize=True)
next_forecast_id = int(forecasts0["Sales_Forecast_ID"].max()) + 1
FORECAST_TARGET_NEW = max(
    int(round(len(forecasts0) * TOTAL_ORDERS / len(orders0))) - len(forecasts0), 0
)
report_ids_all = (
    pd.concat(
        [reports0["Sales_Report_ID"], new_reports_df["Sales_Report_ID"]],
        ignore_index=True,
    ).tolist()
    if len(new_reports_df)
    else reports0["Sales_Report_ID"].tolist()
)
new_forecasts = []
for _ in range(FORECAST_TARGET_NEW):
    gen_d = random_date(DATE_START, DATE_END)
    forecast_qty = round(float(RNG.uniform(10, 400)), 4)
    actual_qty = round(forecast_qty * RNG.uniform(0.5, 1.4), 4)
    forecast_rev = round(float(RNG.uniform(500, 45000)), 2)
    actual_rev = round(forecast_rev * RNG.uniform(0.5, 1.4), 2)
    new_forecasts.append(
        {
            "Sales_Forecast_ID": next_forecast_id,
            "Company_ID": 1,  # D-3
            "Sales_Report_ID": (
                float(RNG.choice(report_ids_all)) if RNG.random() < 0.85 else np.nan
            ),
            "Item_ID": float(sample_item()) if RNG.random() < 0.85 else np.nan,
            "Customer_ID": float(RNG.choice(customer_ids_all)),
            "Product_ID": float(RNG.integers(1, 20)) if RNG.random() < 0.85 else np.nan,
            "Forecast_Period": f"Sales_Forecasts_{next_forecast_id}",
            "Forecasted_Quantity": forecast_qty,
            "Forecasted_Revenue": forecast_rev,
            "Actual_Quantity": actual_qty,
            "Actual_Revenue": actual_rev,
            "Forecast_Method": str(
                RNG.choice(
                    FORECAST_METHOD_CHOICES.index, p=FORECAST_METHOD_CHOICES.values
                )
            ),
            # 원본 실측: Forecasted/Actual과 연동되는 공식이 아니라, 평균 12.37/표준편차 7.4,
            # 1.42~24.95 범위의 별도 무작위값이었다(느슨하게 연결된 분석용 테이블 특성 그대로 재현).
            "Accuracy_Percent": round(
                float(np.clip(RNG.normal(12.37, 7.40), 0.5, 30.0)), 2
            ),
            "Created_By_User_ID": int(RNG.integers(1, rep_pool_max(gen_d) + 1)),
            "Created_At": combine(gen_d),
            "Updated_At": combine(
                min(DATE_END, gen_d + timedelta(days=int(RNG.integers(0, 300))))
            ),
        }
    )
    next_forecast_id += 1
new_forecasts_df = pd.DataFrame(new_forecasts)

print(
    f"  Sales Reports {len(new_reports_df)}건, Sales Forecasts {len(new_forecasts_df)}건"
)


# ---------------------------------------------------------------------------
# 10. 시트 조립 (원본 컬럼 순서·헤더 그대로 유지)
# ---------------------------------------------------------------------------

print("\n" + "=" * 70)
print("10. 시트 조립")
print("=" * 70)


def combine_sheet(orig: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if new is None or len(new) == 0:
        return orig.copy()
    new = new.reindex(columns=orig.columns)
    return pd.concat([orig, new], ignore_index=True)


final_sheets: dict[str, pd.DataFrame] = {
    "Customers": customers_all.drop(columns=["_acquire_date"]).reindex(
        columns=customers0.columns
    ),
    "Sales Orders": combine_sheet(
        orders0, new_orders_df.drop(columns=["_year"], errors="ignore")
    ),
    "Sales Order Lines": combine_sheet(lines0, new_lines_df),
    "Sales Quotes": combine_sheet(quotes0, quotes_all_new),
    "Sales Quote Lines": combine_sheet(qlines0, qlines_all_new),
    "Order Fulfillment": combine_sheet(fulfill0, new_fulfill_df),
    "Fulfillment Lines": combine_sheet(flines0, new_flines_df),
    "Invoices": combine_sheet(invoices0, new_invoices_df),
    "Credit Limits": combine_sheet(credit0, new_credit_df),
    "Customer Contracts": combine_sheet(contracts0, new_contracts_df),
    "Price Lists": combine_sheet(pricelists0, new_pricelists_df),
    "Discounts": combine_sheet(discounts0, new_discounts_df),
    "Sales Reports": combine_sheet(reports0, new_reports_df),
    "Sales Forecasts": combine_sheet(forecasts0, new_forecasts_df),
}

for name, df in final_sheets.items():
    print(f"  {name}: {len(sheets[name])} -> {len(df)}행")

# D-3: Company_ID 1/2 혼재는 "전부 1로 통일"하기로 했으므로, 새로 만든 행뿐
# 아니라 원본에 이미 있던 오염된 행(Reports 18건 중 일부, Forecasts 40건 중
# 일부)도 이 컬럼만 예외적으로 고친다. (다른 컬럼·다른 테이블의 원본 값은
# 그대로 둔다 — 이건 D-3에서 명시적으로 승인된 유일한 예외다.)
before_r = int((final_sheets["Sales Reports"]["Company_ID"] == 2).sum())
before_f = int((final_sheets["Sales Forecasts"]["Company_ID"] == 2).sum())
final_sheets["Sales Reports"]["Company_ID"] = 1
final_sheets["Sales Forecasts"]["Company_ID"] = 1
print(
    f"\n  D-3 적용: Sales Reports Company_ID=2 였던 {before_r}건, Sales Forecasts {before_f}건을 1로 통일 (원본 포함)"
)


# ---------------------------------------------------------------------------
# 11. 검증: 참조 무결성 + 계산 공식
# ---------------------------------------------------------------------------

print("\n" + "=" * 70)
print("11. 검증")
print("=" * 70)

errors: list[str] = []


def check_fk(
    child_df: pd.DataFrame,
    child_col: str,
    parent_df: pd.DataFrame,
    parent_col: str,
    label: str,
    nullable: bool = True,
) -> None:
    vals = child_df[child_col].dropna() if nullable else child_df[child_col]
    valid_ids = set(parent_df[parent_col])
    bad = ~vals.astype(float).isin({float(v) for v in valid_ids})
    n_bad = int(bad.sum())
    if n_bad:
        errors.append(
            f"FK 위반: {label} — {n_bad}건이 존재하지 않는 {parent_col}를 참조"
        )
    else:
        print(f"  OK  {label}: {len(vals)}건 전부 유효")


check_fk(
    final_sheets["Sales Orders"],
    "Customer_ID",
    final_sheets["Customers"],
    "Customer_ID",
    "Sales Orders.Customer_ID -> Customers",
)
check_fk(
    final_sheets["Sales Orders"],
    "Quote_ID",
    final_sheets["Sales Quotes"],
    "Sales_Quote_ID",
    "Sales Orders.Quote_ID -> Sales Quotes",
)
check_fk(
    final_sheets["Sales Order Lines"],
    "Sales_Order_ID",
    final_sheets["Sales Orders"],
    "Sales_Order_ID",
    "Sales Order Lines -> Sales Orders",
    nullable=False,
)
check_fk(
    final_sheets["Sales Quotes"],
    "Customer_ID",
    final_sheets["Customers"],
    "Customer_ID",
    "Sales Quotes.Customer_ID -> Customers",
)
check_fk(
    final_sheets["Sales Quote Lines"],
    "Sales_Quote_ID",
    final_sheets["Sales Quotes"],
    "Sales_Quote_ID",
    "Sales Quote Lines -> Sales Quotes",
    nullable=False,
)
check_fk(
    final_sheets["Order Fulfillment"],
    "Order_ID",
    final_sheets["Sales Orders"],
    "Sales_Order_ID",
    "Order Fulfillment -> Sales Orders",
    nullable=False,
)
check_fk(
    final_sheets["Fulfillment Lines"],
    "Fulfillment_ID",
    final_sheets["Order Fulfillment"],
    "Fulfillment_ID",
    "Fulfillment Lines -> Order Fulfillment",
    nullable=False,
)
check_fk(
    final_sheets["Fulfillment Lines"],
    "Sales_Order_Line_ID",
    final_sheets["Sales Order Lines"],
    "Sales_Order_Line_ID",
    "Fulfillment Lines -> Sales Order Lines",
    nullable=False,
)
check_fk(
    final_sheets["Invoices"],
    "Customer_ID",
    final_sheets["Customers"],
    "Customer_ID",
    "Invoices.Customer_ID -> Customers",
    nullable=False,
)
check_fk(
    final_sheets["Invoices"],
    "Order_ID",
    final_sheets["Sales Orders"],
    "Sales_Order_ID",
    "Invoices.Order_ID -> Sales Orders",
    nullable=False,
)
check_fk(
    final_sheets["Invoices"],
    "Fulfillment_ID",
    final_sheets["Order Fulfillment"],
    "Fulfillment_ID",
    "Invoices.Fulfillment_ID -> Order Fulfillment",
    nullable=False,
)
check_fk(
    final_sheets["Credit Limits"],
    "Customer_ID",
    final_sheets["Customers"],
    "Customer_ID",
    "Credit Limits -> Customers",
)
check_fk(
    final_sheets["Customer Contracts"],
    "Customer_ID",
    final_sheets["Customers"],
    "Customer_ID",
    "Customer Contracts -> Customers",
)
check_fk(
    final_sheets["Discounts"],
    "Customer_ID",
    final_sheets["Customers"],
    "Customer_ID",
    "Discounts.Customer_ID -> Customers",
)
check_fk(
    final_sheets["Discounts"],
    "Price_List_ID",
    final_sheets["Price Lists"],
    "Price_List_ID",
    "Discounts.Price_List_ID -> Price Lists",
)

# 계산 공식 재검증 (허용 오차 0.02 — 부동소수 반올림)
for label, df in [
    ("Sales Order Lines", final_sheets["Sales Order Lines"]),
    ("Sales Quote Lines", final_sheets["Sales Quote Lines"]),
]:
    calc_total = (
        df["Quantity"] * df["Unit_Price"] * (1 - df["Discount_Percent"] / 100)
    ).round(2)
    diff = (calc_total - df["Line_Total"]).abs()
    if diff.max() > 0.02:
        errors.append(
            f"공식 위반: {label}.Line_Total 계산 불일치 최대 {diff.max():.4f}"
        )
    else:
        print(f"  OK  {label}.Line_Total 공식 (최대 오차 {diff.max():.4f})")

    calc_tax = (df["Line_Total"] * TAX_RATE).round(2)
    diff_tax = (calc_tax - df["Tax_Amount"]).abs()
    if diff_tax.max() > 0.02:
        errors.append(
            f"공식 위반: {label}.Tax_Amount 계산 불일치 최대 {diff_tax.max():.4f}"
        )
    else:
        print(f"  OK  {label}.Tax_Amount 공식 (최대 오차 {diff_tax.max():.4f})")

for label, header_df, line_df, key in [
    (
        "Sales Orders",
        final_sheets["Sales Orders"],
        final_sheets["Sales Order Lines"],
        "Sales_Order_ID",
    ),
    (
        "Sales Quotes",
        final_sheets["Sales Quotes"],
        final_sheets["Sales Quote Lines"],
        "Sales_Quote_ID",
    ),
]:
    grp = line_df.groupby(key)["Line_Total"].sum().rename("lines_sum")
    merged = header_df.merge(grp, left_on=key, right_index=True, how="left")
    diff = (merged["Subtotal"] - merged["lines_sum"]).abs()
    if diff.max() > 0.05:
        errors.append(
            f"공식 위반: {label}.Subtotal != SUM(Line_Total) 최대 오차 {diff.max():.4f}"
        )
    else:
        print(f"  OK  {label}.Subtotal = SUM(Line_Total) (최대 오차 {diff.max():.4f})")

    diff_total = (
        merged["Total_Amount"] - (merged["Subtotal"] + merged["Tax_Amount"])
    ).abs()
    if diff_total.max() > 0.02:
        errors.append(
            f"공식 위반: {label}.Total_Amount != Subtotal+Tax_Amount 최대 오차 {diff_total.max():.4f}"
        )
    else:
        print(
            f"  OK  {label}.Total_Amount = Subtotal + Tax_Amount (최대 오차 {diff_total.max():.4f})"
        )

# 주문 건수·기간 확인
final_order_count = len(final_sheets["Sales Orders"])
date_min = pd.to_datetime(final_sheets["Sales Orders"]["Order_Date"]).min()
date_max = pd.to_datetime(final_sheets["Sales Orders"]["Order_Date"]).max()
print(f"\n  최종 주문 건수: {final_order_count} (목표 {TOTAL_ORDERS})")
print(f"  주문 날짜 범위: {date_min.date()} ~ {date_max.date()}")
if final_order_count != TOTAL_ORDERS:
    errors.append(f"최종 주문 건수 {final_order_count} != 목표 {TOTAL_ORDERS}")

# 원본 70건이 값 하나도 안 바뀌었는지 확인
orig_check = final_sheets["Sales Orders"].iloc[: len(orders0)].reset_index(drop=True)
orig_ref = orders0.reset_index(drop=True)
for col in orders0.columns:
    if col in ("Order_Date", "Required_Delivery_Date", "Created_At", "Updated_At"):
        a, b = pd.to_datetime(orig_check[col]), pd.to_datetime(orig_ref[col])
        mismatch = (a != b).sum()
    elif pd.api.types.is_numeric_dtype(orig_ref[col]):
        a, b = orig_check[col], orig_ref[col]
        mismatch = (
            (a.isna() != b.isna())
            | ((~a.isna()) & (~b.isna()) & (a.astype(float) != b.astype(float)))
        ).sum()
    else:
        mismatch = (orig_check[col].astype(str) != orig_ref[col].astype(str)).sum()
    if mismatch:
        errors.append(f"원본 보존 위반: Sales Orders.{col}에서 {mismatch}건 값이 바뀜")
if not errors or all("원본 보존" not in e for e in errors):
    print("  OK  원본 70건 전 컬럼 값 보존 확인")

print()
if errors:
    print(f"검증 실패 {len(errors)}건:")
    for e in errors:
        print(f"  - {e}")
else:
    print("모든 검증 통과.")


# ---------------------------------------------------------------------------
# 12. 저장
# ---------------------------------------------------------------------------

print("\n" + "=" * 70)
print("12. 저장")
print("=" * 70)

with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
    for name in src.sheet_names:
        if name == "Index":
            sheets_index = src.parse("Index", header=None)
            # "Rows" 열(1번 컬럼)을 실제 변경된 행 수로 갱신한다. 시트 이름이 있는
            # 행만 대상으로 하고(안내문 행은 그대로 둠), 매칭 안 되는 시트명은 원본 값 유지.
            for i in sheets_index.index:
                sheet_name_cell = sheets_index.iat[i, 0]
                if sheet_name_cell in final_sheets:
                    sheets_index.iat[i, 1] = len(final_sheets[sheet_name_cell])
            sheets_index.to_excel(writer, sheet_name="Index", header=False, index=False)
            continue
        final_sheets[name].to_excel(writer, sheet_name=name, index=False)

print(f"  저장 완료: {OUT_PATH}")
print(f"\n{'=' * 70}\n요약\n{'=' * 70}")
for name in src.sheet_names:
    if name == "Index":
        continue
    print(f"  {name}: {len(sheets[name])} -> {len(final_sheets[name])}행")
