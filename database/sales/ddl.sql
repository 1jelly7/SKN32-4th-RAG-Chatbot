-- 판매(Sales) 도메인 테이블 DDL
-- 생성 기준: ERP_Schema_v2_Corrected Column Dictionary
-- 담당: 판매(rag_sales) 도메인. 이 파일은 database/sales/ 소유이며
-- 통합/타 도메인 코드가 직접 수정하지 않는다.


CREATE TABLE IF NOT EXISTS `customers` (
    `customer_id` BIGINT,
    `company_id` BIGINT NOT NULL,
    `customer_code` VARCHAR(20),
    `customer_name` VARCHAR(150),
    `customer_type` VARCHAR(30),
    `industry` VARCHAR(50),
    `contact_person` VARCHAR(100),
    `email` VARCHAR(150),
    `phone_number` VARCHAR(20),
    `billing_address` VARCHAR(255),
    `shipping_address` VARCHAR(255),
    `country` VARCHAR(50),
    `tax_id` VARCHAR(30),
    `currency` VARCHAR(5),
    `payment_terms` VARCHAR(50),
    `account_manager_id` BIGINT,
    `is_active` TINYINT(1),
    `created_at` DATETIME,
    `updated_at` DATETIME,
    `created_by_user_id` BIGINT,
    PRIMARY KEY (`customer_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `price_lists` (
    `price_list_id` BIGINT,
    `item_id` BIGINT,
    `list_code` VARCHAR(20),
    `list_name` VARCHAR(150),
    `currency` VARCHAR(5),
    `effective_date` DATE,
    `expiry_date` DATE,
    `customer_segment` VARCHAR(50),
    `is_active` TINYINT(1),
    PRIMARY KEY (`price_list_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `credit_limits` (
    `credit_limit_id` BIGINT,
    `customer_id` BIGINT,
    `credit_limit_amount` DECIMAL(18,2),
    `currency` VARCHAR(5),
    `current_exposure` DECIMAL(18,2),
    `available_credit` DECIMAL(18,2),
    `credit_rating` VARCHAR(10),
    `review_date` DATE,
    `approved_by_user_id` BIGINT,
    `is_on_hold` TINYINT(1),
    `updated_at` DATETIME,
    PRIMARY KEY (`credit_limit_id`),
    FOREIGN KEY (`customer_id`) REFERENCES `customers` (`customer_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `customer_contracts` (
    `customer_contract_id` BIGINT,
    `customer_id` BIGINT,
    `contract_number` VARCHAR(30),
    `contract_name` VARCHAR(150),
    `start_date` DATE,
    `end_date` DATE,
    `total_value` DECIMAL(18,2),
    `currency` VARCHAR(5),
    `payment_terms` VARCHAR(50),
    `auto_renew` TINYINT(1),
    `document_url` VARCHAR(255),
    `status` VARCHAR(20),
    PRIMARY KEY (`customer_contract_id`),
    FOREIGN KEY (`customer_id`) REFERENCES `customers` (`customer_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `sales_quotes` (
    `sales_quote_id` BIGINT,
    `company_id` BIGINT NOT NULL,
    `customer_id` BIGINT,
    `quote_number` VARCHAR(30),
    `quote_date` DATE,
    `valid_until` DATE,
    `sales_rep_id` BIGINT,
    `subtotal` DECIMAL(18,2),
    `discount_amount` DECIMAL(18,2),
    `tax_amount` DECIMAL(18,2),
    `total_amount` DECIMAL(18,2),
    `currency` VARCHAR(5),
    `notes` TEXT,
    `status` VARCHAR(20),
    `created_at` DATETIME,
    `updated_at` DATETIME,
    `created_by_user_id` BIGINT,
    PRIMARY KEY (`sales_quote_id`),
    FOREIGN KEY (`customer_id`) REFERENCES `customers` (`customer_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `discounts` (
    `discount_id` BIGINT,
    `price_list_id` BIGINT,
    `customer_id` BIGINT,
    `discount_code` VARCHAR(20),
    `discount_name` VARCHAR(150),
    `discount_type` VARCHAR(30),
    `discount_value` DECIMAL(10,4),
    `min_order_amount` DECIMAL(18,2),
    `max_discount_amount` DECIMAL(18,2),
    `valid_from` DATE,
    `valid_to` DATE,
    `applicable_to` VARCHAR(50),
    `is_active` TINYINT(1),
    PRIMARY KEY (`discount_id`),
    FOREIGN KEY (`price_list_id`) REFERENCES `price_lists` (`price_list_id`),
    FOREIGN KEY (`customer_id`) REFERENCES `customers` (`customer_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `sales_quote_lines` (
    `sales_quote_line_id` BIGINT NOT NULL,
    `company_id` BIGINT NOT NULL,
    `sales_quote_id` BIGINT NOT NULL,
    `line_number` INT NOT NULL,
    `item_id` BIGINT NOT NULL,
    `description` VARCHAR(255),
    `uom_id` BIGINT,
    `quantity` DECIMAL(14,4) NOT NULL,
    `unit_price` DECIMAL(18,4),
    `discount_percent` DECIMAL(5,2),
    `tax_code_id` BIGINT,
    `tax_amount` DECIMAL(18,2),
    `line_total` DECIMAL(18,2),
    `created_at` DATETIME,
    `updated_at` DATETIME,
    `created_by_user_id` BIGINT,
    PRIMARY KEY (`sales_quote_line_id`),
    FOREIGN KEY (`sales_quote_id`) REFERENCES `sales_quotes` (`sales_quote_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `sales_orders` (
    `sales_order_id` BIGINT,
    `company_id` BIGINT NOT NULL,
    `customer_id` BIGINT,
    `quote_id` BIGINT,
    `order_number` VARCHAR(30),
    `order_date` DATE,
    `required_delivery_date` DATE,
    `delivery_address` VARCHAR(255),
    `sales_rep_id` BIGINT,
    `subtotal` DECIMAL(18,2),
    `discount_amount` DECIMAL(18,2),
    `tax_amount` DECIMAL(18,2),
    `total_amount` DECIMAL(18,2),
    `currency` VARCHAR(5),
    `payment_terms` VARCHAR(50),
    `status` VARCHAR(20),
    `approval_request_id` BIGINT,
    `created_at` DATETIME,
    `updated_at` DATETIME,
    `created_by_user_id` BIGINT,
    PRIMARY KEY (`sales_order_id`),
    FOREIGN KEY (`customer_id`) REFERENCES `customers` (`customer_id`),
    FOREIGN KEY (`quote_id`) REFERENCES `sales_quotes` (`sales_quote_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `sales_order_lines` (
    `sales_order_line_id` BIGINT NOT NULL,
    `company_id` BIGINT NOT NULL,
    `sales_order_id` BIGINT NOT NULL,
    `line_number` INT NOT NULL,
    `item_id` BIGINT NOT NULL,
    `description` VARCHAR(255),
    `uom_id` BIGINT,
    `quantity` DECIMAL(14,4) NOT NULL,
    `unit_price` DECIMAL(18,4),
    `discount_percent` DECIMAL(5,2),
    `tax_code_id` BIGINT,
    `tax_amount` DECIMAL(18,2),
    `line_total` DECIMAL(18,2),
    `quantity_delivered` DECIMAL(14,4),
    `warehouse_id` BIGINT,
    `created_at` DATETIME,
    `updated_at` DATETIME,
    `created_by_user_id` BIGINT,
    PRIMARY KEY (`sales_order_line_id`),
    FOREIGN KEY (`sales_order_id`) REFERENCES `sales_orders` (`sales_order_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `order_fulfillment` (
    `fulfillment_id` BIGINT,
    `company_id` BIGINT NOT NULL,
    `order_id` BIGINT,
    `shipment_number` VARCHAR(30),
    `shipment_date` DATE,
    `carrier` VARCHAR(100),
    `tracking_number` VARCHAR(100),
    `delivery_date` DATE,
    `packed_by_user_id` BIGINT,
    `shipped_by_user_id` BIGINT,
    `status` VARCHAR(20),
    `notes` VARCHAR(255),
    `created_at` DATETIME,
    `updated_at` DATETIME,
    `created_by_user_id` BIGINT,
    PRIMARY KEY (`fulfillment_id`),
    FOREIGN KEY (`order_id`) REFERENCES `sales_orders` (`sales_order_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `fulfillment_lines` (
    `fulfillment_line_id` BIGINT NOT NULL,
    `company_id` BIGINT NOT NULL,
    `fulfillment_id` BIGINT NOT NULL,
    `sales_order_line_id` BIGINT,
    `line_number` INT NOT NULL,
    `item_id` BIGINT NOT NULL,
    `description` VARCHAR(255),
    `uom_id` BIGINT,
    `quantity` DECIMAL(14,4) NOT NULL,
    `unit_price` DECIMAL(18,4),
    `discount_percent` DECIMAL(5,2),
    `tax_code_id` BIGINT,
    `tax_amount` DECIMAL(18,2),
    `line_total` DECIMAL(18,2),
    `quantity_shipped` DECIMAL(14,4),
    `warehouse_id` BIGINT,
    `created_at` DATETIME,
    `updated_at` DATETIME,
    `created_by_user_id` BIGINT,
    PRIMARY KEY (`fulfillment_line_id`),
    FOREIGN KEY (`fulfillment_id`) REFERENCES `order_fulfillment` (`fulfillment_id`),
    FOREIGN KEY (`sales_order_line_id`) REFERENCES `sales_order_lines` (`sales_order_line_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `invoices` (
    `invoice_id` BIGINT,
    `company_id` BIGINT NOT NULL,
    `fulfillment_id` BIGINT,
    `customer_id` BIGINT,
    `order_id` BIGINT,
    `invoice_number` VARCHAR(30),
    `invoice_date` DATE,
    `due_date` DATE,
    `subtotal` DECIMAL(18,2),
    `tax_amount` DECIMAL(18,2),
    `total_amount` DECIMAL(18,2),
    `amount_paid` DECIMAL(18,2),
    `outstanding_amount` DECIMAL(18,2),
    `currency` VARCHAR(5),
    `payment_terms` VARCHAR(50),
    `status` VARCHAR(20),
    `customer_invoice_id` BIGINT,
    `created_at` DATETIME,
    `updated_at` DATETIME,
    `created_by_user_id` BIGINT,
    PRIMARY KEY (`invoice_id`),
    FOREIGN KEY (`fulfillment_id`) REFERENCES `order_fulfillment` (`fulfillment_id`),
    FOREIGN KEY (`customer_id`) REFERENCES `customers` (`customer_id`),
    FOREIGN KEY (`order_id`) REFERENCES `sales_orders` (`sales_order_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `sales_reports` (
    `sales_report_id` BIGINT,
    `company_id` BIGINT NOT NULL,
    `sales_order_id` BIGINT,
    `invoice_id` BIGINT,
    `customer_id` BIGINT,
    `report_code` VARCHAR(20),
    `report_name` VARCHAR(150),
    `report_type` VARCHAR(50),
    `period_start` DATE,
    `period_end` DATE,
    `total_revenue` DECIMAL(18,2),
    `orders_count` INT,
    `generated_by_user_id` BIGINT,
    `generated_at` DATETIME,
    `created_at` DATETIME,
    `updated_at` DATETIME,
    `created_by_user_id` BIGINT,
    PRIMARY KEY (`sales_report_id`),
    FOREIGN KEY (`sales_order_id`) REFERENCES `sales_orders` (`sales_order_id`),
    FOREIGN KEY (`invoice_id`) REFERENCES `invoices` (`invoice_id`),
    FOREIGN KEY (`customer_id`) REFERENCES `customers` (`customer_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `sales_forecasts` (
    `sales_forecast_id` BIGINT,
    `company_id` BIGINT NOT NULL,
    `sales_report_id` BIGINT,
    `item_id` BIGINT,
    `customer_id` BIGINT,
    `product_id` BIGINT,
    `forecast_period` VARCHAR(30),
    `forecasted_quantity` DECIMAL(14,4),
    `forecasted_revenue` DECIMAL(18,2),
    `actual_quantity` DECIMAL(14,4),
    `actual_revenue` DECIMAL(18,2),
    `forecast_method` VARCHAR(50),
    `accuracy_percent` DECIMAL(6,2),
    `created_by_user_id` BIGINT,
    `created_at` DATETIME,
    `updated_at` DATETIME,
    PRIMARY KEY (`sales_forecast_id`),
    FOREIGN KEY (`sales_report_id`) REFERENCES `sales_reports` (`sales_report_id`),
    FOREIGN KEY (`customer_id`) REFERENCES `customers` (`customer_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

