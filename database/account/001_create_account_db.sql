-- Purpose: create the authentication database before the remaining account scripts.
-- Run first. Tested with MySQL 8 compatible utf8mb4_unicode_ci collation.
CREATE DATABASE IF NOT EXISTS account_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
