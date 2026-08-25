-- 구매(Purchase) 도메인 테이블 DDL
-- 생성 기준: ERP_Purchasing_Analytics.xlsx 실측 (5시트)
-- 담당: 구매(rag_purchase) 도메인. 이 파일은 database/purchase/ 소유이며
-- 통합/타 도메인 코드가 직접 수정하지 않는다.
use purchase;

CREATE TABLE IF NOT EXISTS `vendors` (
    `vendor_id` BIGINT NOT NULL,
    `vendor_code` VARCHAR(20) NOT NULL,
    `vendor_name` VARCHAR(200) NOT NULL,
    `country` VARCHAR(100),
    `currency` VARCHAR(10),
    `payment_terms` VARCHAR(20),
    `is_active` TINYINT(1) NOT NULL,
    PRIMARY KEY (`vendor_id`),
    UNIQUE KEY `uk_vendors_vendor_code` (`vendor_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `purchase_orders` (
    `po_id` BIGINT NOT NULL,
    `vendor_id` BIGINT NOT NULL,
    `po_number` VARCHAR(30) NOT NULL,
    `po_date` DATE NOT NULL,
    `subtotal` DECIMAL(14,2),
    `tax_amount` DECIMAL(14,2),
    `total_amount` DECIMAL(14,2) NOT NULL,
    `currency` VARCHAR(10),
    `status` VARCHAR(30) NOT NULL,
    PRIMARY KEY (`po_id`),
    UNIQUE KEY `uk_purchase_orders_po_number` (`po_number`),
    FOREIGN KEY (`vendor_id`) REFERENCES `vendors` (`vendor_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `purchase_order_lines` (
    `po_line_id` BIGINT NOT NULL,
    `po_id` BIGINT NOT NULL,
    `item_id` BIGINT NOT NULL,
    `description` VARCHAR(300),
    `quantity` INT NOT NULL,
    `unit_price` DECIMAL(14,4),
    `discount_percent` DECIMAL(5,2),
    `line_total` DECIMAL(14,2),
    PRIMARY KEY (`po_line_id`),
    FOREIGN KEY (`po_id`) REFERENCES `purchase_orders` (`po_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `vendor_invoices` (
    `invoice_id` BIGINT NOT NULL,
    `invoice_number` VARCHAR(30) NOT NULL,
    `invoice_date` DATE NOT NULL,
    `po_id` BIGINT NOT NULL,
    `vendor_id` BIGINT NOT NULL,
    `subtotal` DECIMAL(14,2),
    `tax_amount` DECIMAL(14,2),
    `total_amount` DECIMAL(14,2) NOT NULL,
    `amount_paid` DECIMAL(14,2),
    `outstanding_amount` DECIMAL(14,2),
    `currency` VARCHAR(10),
    `status` VARCHAR(30) NOT NULL,
    PRIMARY KEY (`invoice_id`),
    UNIQUE KEY `uk_vendor_invoices_invoice_number` (`invoice_number`),
    FOREIGN KEY (`po_id`) REFERENCES `purchase_orders` (`po_id`),
    FOREIGN KEY (`vendor_id`) REFERENCES `vendors` (`vendor_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `goods_receipts` (
    `gr_id` BIGINT NOT NULL,
    `gr_number` VARCHAR(30) NOT NULL,
    `receipt_date` DATE NOT NULL,
    `po_id` BIGINT NOT NULL,
    `vendor_id` BIGINT NOT NULL,
    PRIMARY KEY (`gr_id`),
    UNIQUE KEY `uk_goods_receipts_gr_number` (`gr_number`),
    FOREIGN KEY (`po_id`) REFERENCES `purchase_orders` (`po_id`),
    FOREIGN KEY (`vendor_id`) REFERENCES `vendors` (`vendor_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
