#!/usr/bin/env bash
set -euo pipefail

mysql --local-infile=1 -u root -p"${MYSQL_ROOT_PASSWORD}" <<'SQL'
CREATE DATABASE IF NOT EXISTS procurement_demo;
USE procurement_demo;

LOAD DATA LOCAL INFILE '/seed-data/plants.csv'
INTO TABLE plants
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(plant_id, plant_code, plant_name, country_code, country_name, city, address, @is_active, @created_at, @updated_at)
SET
  is_active = (@is_active = 'true'),
  created_at = STR_TO_DATE(@created_at, '%Y-%m-%dT%H:%i:%sZ'),
  updated_at = STR_TO_DATE(@updated_at, '%Y-%m-%dT%H:%i:%sZ');

LOAD DATA LOCAL INFILE '/seed-data/parts.csv'
INTO TABLE parts
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(part_id, part_code, part_name, description, category, unit_of_measure, reference_unit_price, reference_currency, @is_active, @created_at, @updated_at)
SET
  is_active = (@is_active = 'true'),
  created_at = STR_TO_DATE(@created_at, '%Y-%m-%dT%H:%i:%sZ'),
  updated_at = STR_TO_DATE(@updated_at, '%Y-%m-%dT%H:%i:%sZ');

LOAD DATA LOCAL INFILE '/seed-data/suppliers.csv'
INTO TABLE suppliers
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(supplier_id, supplier_name, country_code, country_name, contact_endpoint, currency, quality_score, reliability_score, @is_active, @created_at, @updated_at)
SET
  is_active = (@is_active = 'true'),
  created_at = STR_TO_DATE(@created_at, '%Y-%m-%dT%H:%i:%sZ'),
  updated_at = STR_TO_DATE(@updated_at, '%Y-%m-%dT%H:%i:%sZ');

LOAD DATA LOCAL INFILE '/seed-data/supplier_parts.csv'
INTO TABLE supplier_parts
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(supplier_part_id, supplier_id, part_id, lead_time_days, min_order_quantity, @is_preferred, @is_active, @created_at, @updated_at)
SET
  is_preferred = (@is_preferred = 'true'),
  is_active = (@is_active = 'true'),
  created_at = STR_TO_DATE(@created_at, '%Y-%m-%dT%H:%i:%sZ'),
  updated_at = STR_TO_DATE(@updated_at, '%Y-%m-%dT%H:%i:%sZ');
SQL
