CREATE DATABASE IF NOT EXISTS procurement_demo;
USE procurement_demo;

CREATE TABLE plants (
  plant_id VARCHAR(32) NOT NULL,
  plant_code VARCHAR(32) NOT NULL,
  plant_name VARCHAR(128) NOT NULL,
  country_code CHAR(2) NOT NULL,
  country_name VARCHAR(64) NOT NULL,
  city VARCHAR(64) NOT NULL,
  address VARCHAR(255),
  is_active BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  PRIMARY KEY (plant_id),
  UNIQUE KEY uq_plants_code (plant_code)
);

CREATE TABLE parts (
  part_id VARCHAR(32) NOT NULL,
  part_code VARCHAR(64) NOT NULL,
  part_name VARCHAR(128) NOT NULL,
  description VARCHAR(255),
  category VARCHAR(64),
  unit_of_measure VARCHAR(16) NOT NULL,
  is_active BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  PRIMARY KEY (part_id),
  UNIQUE KEY uq_parts_code (part_code)
);

CREATE TABLE suppliers (
  supplier_id VARCHAR(32) NOT NULL,
  supplier_name VARCHAR(128) NOT NULL,
  country_code CHAR(2) NOT NULL,
  country_name VARCHAR(64) NOT NULL,
  contact_endpoint VARCHAR(255) NOT NULL,
  currency CHAR(3) NOT NULL,
  quality_score DECIMAL(5,2),
  reliability_score DECIMAL(5,2),
  is_active BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  PRIMARY KEY (supplier_id)
);

CREATE TABLE supplier_parts (
  supplier_part_id VARCHAR(32) NOT NULL,
  supplier_id VARCHAR(32) NOT NULL,
  part_id VARCHAR(32) NOT NULL,
  lead_time_days INT,
  min_order_quantity DECIMAL(18,4),
  is_preferred BOOLEAN NOT NULL,
  is_active BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  PRIMARY KEY (supplier_part_id),
  UNIQUE KEY uq_supplier_parts_supplier_part (supplier_id, part_id),
  CONSTRAINT fk_supplier_parts_supplier
    FOREIGN KEY (supplier_id) REFERENCES suppliers (supplier_id),
  CONSTRAINT fk_supplier_parts_part
    FOREIGN KEY (part_id) REFERENCES parts (part_id)
);

CREATE TABLE procurement_requests (
  request_id VARCHAR(32) NOT NULL,
  plant_id VARCHAR(32) NOT NULL,
  part_id VARCHAR(32) NOT NULL,
  quantity DECIMAL(18,4) NOT NULL,
  required_delivery_date DATE NOT NULL,
  currency CHAR(3) NOT NULL,
  status ENUM(
    'open',
    'offers_requested',
    'offers_received',
    'evaluated',
    'ordered',
    'cancelled',
    'failed'
  ) NOT NULL,
  requested_by VARCHAR(128),
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  PRIMARY KEY (request_id),
  CONSTRAINT fk_procurement_requests_plant
    FOREIGN KEY (plant_id) REFERENCES plants (plant_id),
  CONSTRAINT fk_procurement_requests_part
    FOREIGN KEY (part_id) REFERENCES parts (part_id)
);

CREATE TABLE supplier_offers (
  offer_id VARCHAR(32) NOT NULL,
  request_id VARCHAR(32) NOT NULL,
  supplier_id VARCHAR(32) NOT NULL,
  part_id VARCHAR(32) NOT NULL,
  plant_id VARCHAR(32) NOT NULL,
  quantity DECIMAL(18,4) NOT NULL,
  parts_cost DECIMAL(18,2) NOT NULL,
  shipping_cost DECIMAL(18,2) NOT NULL,
  total_cost DECIMAL(18,2) NOT NULL,
  currency CHAR(3) NOT NULL,
  delivery_date DATE NOT NULL,
  valid_until DATE NOT NULL,
  status ENUM('received', 'selected', 'rejected', 'expired') NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  PRIMARY KEY (offer_id),
  CONSTRAINT fk_supplier_offers_request
    FOREIGN KEY (request_id) REFERENCES procurement_requests (request_id),
  CONSTRAINT fk_supplier_offers_supplier
    FOREIGN KEY (supplier_id) REFERENCES suppliers (supplier_id),
  CONSTRAINT fk_supplier_offers_part
    FOREIGN KEY (part_id) REFERENCES parts (part_id),
  CONSTRAINT fk_supplier_offers_plant
    FOREIGN KEY (plant_id) REFERENCES plants (plant_id),
  CONSTRAINT chk_supplier_offers_total_cost
    CHECK (total_cost = parts_cost + shipping_cost)
);

CREATE TABLE purchase_orders (
  purchase_order_id VARCHAR(32) NOT NULL,
  request_id VARCHAR(32) NOT NULL,
  offer_id VARCHAR(32) NOT NULL,
  supplier_id VARCHAR(32) NOT NULL,
  plant_id VARCHAR(32) NOT NULL,
  part_id VARCHAR(32) NOT NULL,
  quantity DECIMAL(18,4) NOT NULL,
  total_amount DECIMAL(18,2) NOT NULL,
  currency CHAR(3) NOT NULL,
  status ENUM('created', 'registered', 'failed', 'cancelled') NOT NULL,
  external_reference VARCHAR(128),
  registered_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  PRIMARY KEY (purchase_order_id),
  CONSTRAINT fk_purchase_orders_request
    FOREIGN KEY (request_id) REFERENCES procurement_requests (request_id),
  CONSTRAINT fk_purchase_orders_offer
    FOREIGN KEY (offer_id) REFERENCES supplier_offers (offer_id),
  CONSTRAINT fk_purchase_orders_supplier
    FOREIGN KEY (supplier_id) REFERENCES suppliers (supplier_id),
  CONSTRAINT fk_purchase_orders_plant
    FOREIGN KEY (plant_id) REFERENCES plants (plant_id),
  CONSTRAINT fk_purchase_orders_part
    FOREIGN KEY (part_id) REFERENCES parts (part_id)
);
