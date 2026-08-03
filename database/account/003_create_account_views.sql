-- Run after 002. HR directory access must use this view, never the accounts table.
USE account_db;

CREATE OR REPLACE VIEW v_account_directory AS
SELECT id, username, display_name, role, is_active, created_at, updated_at
FROM accounts;
