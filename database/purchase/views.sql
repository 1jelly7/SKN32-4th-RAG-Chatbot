-- purchase_db 조회용 View 5개 (챗봇 Text2SQL이 조회하는 대상)
-- 실행: mysql -u JangGGo -p1234 -h 127.0.0.1 purchase_db < database/purchase/views.sql

CREATE OR REPLACE VIEW v_purchase_order AS
SELECT PO_ID, company_id, PO_Number, PO_Date, Vendor_ID,
       Subtotal, Tax_Amount, Total_Amount, Currency, Status
FROM purchase_orders
WHERE Status <> 'Cancelled';

CREATE OR REPLACE VIEW v_purchase_order_line AS
SELECT pol.PO_Line_ID, pol.company_id, pol.PO_ID,
       po.Vendor_ID, po.PO_Date, po.Status,
       pol.Item_ID, pol.Item_Code, pol.Description,
       pol.Quantity, pol.Unit_Price, pol.Discount_Percent, pol.Line_Total
FROM po_lines pol
JOIN purchase_orders po ON pol.PO_ID = po.PO_ID
WHERE po.Status <> 'Cancelled';

CREATE OR REPLACE VIEW v_vendor AS
SELECT Vendor_ID, company_id, Vendor_Code, Vendor_Name,
       Vendor_Type, Country, Currency, Payment_Terms, Active
FROM vendors;

CREATE OR REPLACE VIEW v_vendor_invoice AS
SELECT Invoice_ID, company_id, Invoice_Number, Invoice_Date,
       PO_ID, Vendor_ID, Due_Date, Subtotal, Tax_Amount, Total_Amount,
       Amount_Paid, Outstanding_Amount, Currency, Payment_Status
FROM invoices;

CREATE OR REPLACE VIEW v_purchase_order_status AS
SELECT PO_ID, Status, Total_Amount, PO_Date, Vendor_ID
FROM purchase_orders;
