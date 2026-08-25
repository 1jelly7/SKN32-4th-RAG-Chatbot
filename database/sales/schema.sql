-- ============================================================
-- sales DB 스키마
-- ------------------------------------------------------------
-- ERP_Seed_Data_Sales_Purchasing.xlsx 중 판매/고객/재고 관련 시트를 옮긴 것입니다.
-- (구매 관련 시트는 이미 purchase DB에 있으므로 여기서는 제외했습니다)
--
-- 실행 방법:
--   mysql -u JangGGo -p1234 -h 127.0.0.1 sales < database/sales/schema.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS sales CHARACTER SET utf8mb4;
USE sales;

-- ------------------------------------------------------------
-- 마스터 데이터 (다른 테이블이 참조하므로 먼저 생성)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    customer_id          BIGINT PRIMARY KEY,
    company_id            BIGINT NOT NULL,
    customer_code          VARCHAR(20) NOT NULL UNIQUE,
    customer_name          VARCHAR(200) NOT NULL,
    customer_type          VARCHAR(50),
    industry              VARCHAR(100),
    contact_person          VARCHAR(100),
    email                 VARCHAR(200),
    phone_number            VARCHAR(50),
    billing_address          VARCHAR(300),
    shipping_address         VARCHAR(300),
    country               VARCHAR(100),
    tax_id                 VARCHAR(50),
    currency              VARCHAR(10),
    payment_terms           VARCHAR(20),
    account_manager_id        BIGINT,
    is_active              BOOLEAN DEFAULT TRUE,
    created_at             DATETIME,
    updated_at             DATETIME,
    created_by_user_id        BIGINT
);

CREATE TABLE IF NOT EXISTS inventory_items (
    item_id           BIGINT PRIMARY KEY,
    company_id         BIGINT NOT NULL,
    item_code          VARCHAR(20) NOT NULL UNIQUE,
    item_name          VARCHAR(200) NOT NULL,
    item_category_id      BIGINT,
    uom_id            BIGINT,
    barcode           VARCHAR(50),
    min_stock_level      DECIMAL(14, 2),
    max_stock_level      DECIMAL(14, 2),
    reorder_point       DECIMAL(14, 2),
    lead_time_days      INT,
    unit_cost          DECIMAL(14, 4),
    is_serialized       BOOLEAN,
    is_lot_tracked       BOOLEAN,
    is_active          BOOLEAN DEFAULT TRUE,
    created_at          DATETIME,
    updated_at          DATETIME,
    created_by_user_id     BIGINT
);

-- ------------------------------------------------------------
-- 고객 관련 (여신, 계약, 가격, 견적)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS credit_limits (
    credit_limit_id     BIGINT PRIMARY KEY,
    customer_id          BIGINT,
    credit_limit_amount     DECIMAL(14, 2),
    currency            VARCHAR(10),
    current_exposure       DECIMAL(14, 2),
    available_credit       DECIMAL(14, 2),
    credit_rating         VARCHAR(10),
    review_date          DATE,
    approved_by_user_id      BIGINT,
    is_on_hold           BOOLEAN,
    updated_at           DATETIME,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS customer_contracts (
    customer_contract_id  BIGINT PRIMARY KEY,
    customer_id          BIGINT,
    contract_number        VARCHAR(30) NOT NULL UNIQUE,
    contract_name         VARCHAR(200),
    start_date           DATE,
    end_date            DATE,
    total_value          DECIMAL(14, 2),
    currency            VARCHAR(10),
    payment_terms         VARCHAR(50),
    auto_renew           BOOLEAN,
    document_url          VARCHAR(300),
    status              VARCHAR(30),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS price_lists (
    price_list_id    BIGINT PRIMARY KEY,
    item_id         BIGINT,
    list_code        VARCHAR(20) NOT NULL UNIQUE,
    list_name        VARCHAR(200),
    currency        VARCHAR(10),
    effective_date     DATE,
    expiry_date       DATE,
    customer_segment    VARCHAR(50),
    is_active        BOOLEAN,
    FOREIGN KEY (item_id) REFERENCES inventory_items(item_id)
);

CREATE TABLE IF NOT EXISTS sales_quotes (
    sales_quote_id     BIGINT PRIMARY KEY,
    company_id         BIGINT NOT NULL,
    customer_id         BIGINT,
    quote_number        VARCHAR(30) NOT NULL UNIQUE,
    quote_date          DATE,
    valid_until         DATE,
    sales_rep_id         BIGINT,
    subtotal           DECIMAL(14, 2),
    discount_amount       DECIMAL(14, 2),
    tax_amount          DECIMAL(14, 2),
    total_amount         DECIMAL(14, 2),
    currency           VARCHAR(10),
    notes             VARCHAR(500),
    status            VARCHAR(30),
    created_at          DATETIME,
    updated_at          DATETIME,
    created_by_user_id      BIGINT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- ------------------------------------------------------------
-- 재고 (재고수량, 창고이동)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_levels (
    stock_level_id    BIGINT PRIMARY KEY,
    company_id        BIGINT NOT NULL,
    item_id          BIGINT,
    warehouse_id       BIGINT,
    bin_location_id      BIGINT,
    quantity_on_hand     DECIMAL(14, 2),
    quantity_reserved    DECIMAL(14, 2),
    quantity_available    DECIMAL(14, 2),
    quantity_on_order    DECIMAL(14, 2),
    last_count_date     DATE,
    updated_at         DATETIME,
    created_at         DATETIME,
    created_by_user_id     BIGINT,
    FOREIGN KEY (item_id) REFERENCES inventory_items(item_id)
);

CREATE TABLE IF NOT EXISTS discounts (
    discount_id       BIGINT PRIMARY KEY,
    price_list_id      BIGINT,
    customer_id        BIGINT,
    discount_code       VARCHAR(20) NOT NULL UNIQUE,
    discount_name       VARCHAR(200),
    discount_type       VARCHAR(30),
    discount_value      DECIMAL(14, 2),
    min_order_amount     DECIMAL(14, 2),
    max_discount_amount    DECIMAL(14, 2),
    valid_from         DATE,
    valid_to          DATE,
    applicable_to       VARCHAR(50),
    is_active         BOOLEAN,
    FOREIGN KEY (price_list_id) REFERENCES price_lists(price_list_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS inventory_transfers (
    inventory_transfer_id  BIGINT PRIMARY KEY,
    company_id             BIGINT NOT NULL,
    stock_level_id           BIGINT,
    item_id                BIGINT,
    from_warehouse_id          BIGINT,
    to_warehouse_id           BIGINT,
    transfer_number           VARCHAR(30) NOT NULL UNIQUE,
    transfer_date            DATE,
    quantity               DECIMAL(14, 2),
    reason                VARCHAR(300),
    requested_by_user_id        BIGINT,
    approved_by_user_id         BIGINT,
    status                VARCHAR(30),
    created_at              DATETIME,
    updated_at              DATETIME,
    created_by_user_id          BIGINT,
    FOREIGN KEY (stock_level_id) REFERENCES stock_levels(stock_level_id),
    FOREIGN KEY (item_id) REFERENCES inventory_items(item_id)
);

-- ------------------------------------------------------------
-- 판매 주문 및 이행
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sales_orders (
    sales_order_id       BIGINT PRIMARY KEY,
    company_id            BIGINT NOT NULL,
    customer_id            BIGINT,
    quote_id              BIGINT,
    order_number           VARCHAR(30) NOT NULL UNIQUE,
    order_date            DATE,
    required_delivery_date     DATE,
    delivery_address         VARCHAR(300),
    sales_rep_id            BIGINT,
    subtotal              DECIMAL(14, 2),
    discount_amount          DECIMAL(14, 2),
    tax_amount             DECIMAL(14, 2),
    total_amount            DECIMAL(14, 2),
    currency              VARCHAR(10),
    payment_terms           VARCHAR(20),
    status                VARCHAR(30),
    approval_request_id        BIGINT,
    created_at             DATETIME,
    updated_at             DATETIME,
    created_by_user_id         BIGINT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (quote_id) REFERENCES sales_quotes(sales_quote_id)
);

CREATE TABLE IF NOT EXISTS sales_quote_lines (
    sales_quote_line_id  BIGINT PRIMARY KEY,
    company_id           BIGINT NOT NULL,
    sales_quote_id         BIGINT NOT NULL,
    line_number           INT,
    item_id              BIGINT,
    description           VARCHAR(300),
    uom_id               BIGINT,
    quantity             DECIMAL(14, 2),
    unit_price            DECIMAL(14, 4),
    discount_percent        DECIMAL(5, 2),
    tax_code_id            BIGINT,
    tax_amount            DECIMAL(14, 2),
    line_total            DECIMAL(14, 2),
    created_at            DATETIME,
    updated_at            DATETIME,
    created_by_user_id        BIGINT,
    FOREIGN KEY (sales_quote_id) REFERENCES sales_quotes(sales_quote_id),
    FOREIGN KEY (item_id) REFERENCES inventory_items(item_id)
);

CREATE TABLE IF NOT EXISTS order_fulfillment (
    fulfillment_id      BIGINT PRIMARY KEY,
    company_id           BIGINT NOT NULL,
    order_id             BIGINT NOT NULL,
    shipment_number         VARCHAR(30) NOT NULL UNIQUE,
    shipment_date          DATE,
    carrier             VARCHAR(100),
    tracking_number         VARCHAR(50),
    delivery_date          DATE,
    packed_by_user_id        BIGINT,
    shipped_by_user_id        BIGINT,
    status              VARCHAR(30),
    notes              VARCHAR(500),
    created_at            DATETIME,
    updated_at            DATETIME,
    created_by_user_id        BIGINT,
    FOREIGN KEY (order_id) REFERENCES sales_orders(sales_order_id)
);

CREATE TABLE IF NOT EXISTS sales_order_lines (
    sales_order_line_id  BIGINT PRIMARY KEY,
    company_id           BIGINT NOT NULL,
    sales_order_id         BIGINT NOT NULL,
    line_number           INT,
    item_id              BIGINT,
    description           VARCHAR(300),
    uom_id               BIGINT,
    quantity             DECIMAL(14, 2),
    unit_price            DECIMAL(14, 4),
    discount_percent        DECIMAL(5, 2),
    tax_code_id            BIGINT,
    tax_amount            DECIMAL(14, 2),
    line_total            DECIMAL(14, 2),
    quantity_delivered        DECIMAL(14, 2),
    warehouse_id           BIGINT,
    created_at            DATETIME,
    updated_at            DATETIME,
    created_by_user_id        BIGINT,
    FOREIGN KEY (sales_order_id) REFERENCES sales_orders(sales_order_id),
    FOREIGN KEY (item_id) REFERENCES inventory_items(item_id)
);

CREATE TABLE IF NOT EXISTS fulfillment_lines (
    fulfillment_line_id   BIGINT PRIMARY KEY,
    company_id            BIGINT NOT NULL,
    fulfillment_id          BIGINT NOT NULL,
    sales_order_line_id       BIGINT,
    line_number            INT,
    item_id               BIGINT,
    description            VARCHAR(300),
    uom_id                BIGINT,
    quantity              DECIMAL(14, 2),
    unit_price             DECIMAL(14, 4),
    discount_percent         DECIMAL(5, 2),
    tax_code_id             BIGINT,
    tax_amount             DECIMAL(14, 2),
    line_total             DECIMAL(14, 2),
    quantity_shipped         DECIMAL(14, 2),
    warehouse_id            BIGINT,
    created_at             DATETIME,
    updated_at             DATETIME,
    created_by_user_id         BIGINT,
    FOREIGN KEY (fulfillment_id) REFERENCES order_fulfillment(fulfillment_id),
    FOREIGN KEY (sales_order_line_id) REFERENCES sales_order_lines(sales_order_line_id)
);

-- ------------------------------------------------------------
-- 청구/리포트/예측
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id          BIGINT PRIMARY KEY,
    company_id           BIGINT NOT NULL,
    fulfillment_id         BIGINT,
    customer_id           BIGINT,
    order_id             BIGINT,
    invoice_number         VARCHAR(30) NOT NULL UNIQUE,
    invoice_date          DATE,
    due_date            DATE,
    subtotal            DECIMAL(14, 2),
    tax_amount           DECIMAL(14, 2),
    total_amount          DECIMAL(14, 2),
    amount_paid           DECIMAL(14, 2),
    outstanding_amount       DECIMAL(14, 2),
    currency            VARCHAR(10),
    payment_terms          VARCHAR(20),
    status              VARCHAR(30),
    customer_invoice_id       BIGINT,
    created_at            DATETIME,
    updated_at            DATETIME,
    created_by_user_id        BIGINT,
    FOREIGN KEY (fulfillment_id) REFERENCES order_fulfillment(fulfillment_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (order_id) REFERENCES sales_orders(sales_order_id)
);

CREATE TABLE IF NOT EXISTS sales_reports (
    sales_report_id      BIGINT PRIMARY KEY,
    company_id            BIGINT NOT NULL,
    sales_order_id          BIGINT,
    invoice_id            BIGINT,
    customer_id            BIGINT,
    report_code            VARCHAR(30) NOT NULL UNIQUE,
    report_name            VARCHAR(200),
    report_type            VARCHAR(50),
    period_start           DATE,
    period_end            DATE,
    total_revenue           DECIMAL(14, 2),
    orders_count           INT,
    generated_by_user_id        BIGINT,
    generated_at           DATETIME,
    created_at             DATETIME,
    updated_at             DATETIME,
    created_by_user_id         BIGINT,
    FOREIGN KEY (sales_order_id) REFERENCES sales_orders(sales_order_id),
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS sales_forecasts (
    sales_forecast_id     BIGINT PRIMARY KEY,
    company_id            BIGINT NOT NULL,
    sales_report_id         BIGINT,
    item_id              BIGINT,
    customer_id            BIGINT,
    product_id             BIGINT,
    forecast_period          VARCHAR(100),
    forecasted_quantity        DECIMAL(14, 2),
    forecasted_revenue         DECIMAL(14, 2),
    actual_quantity          DECIMAL(14, 2),
    actual_revenue           DECIMAL(14, 2),
    forecast_method          VARCHAR(50),
    accuracy_percent          DECIMAL(6, 2),
    created_by_user_id         BIGINT,
    created_at             DATETIME,
    updated_at             DATETIME,
    FOREIGN KEY (sales_report_id) REFERENCES sales_reports(sales_report_id),
    FOREIGN KEY (item_id) REFERENCES inventory_items(item_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE INDEX idx_so_customer_date ON sales_orders (customer_id, order_date);
CREATE INDEX idx_so_status ON sales_orders (status);
CREATE INDEX idx_invoice_status ON invoices (status);
CREATE INDEX idx_stock_item_warehouse ON stock_levels (item_id, warehouse_id);
