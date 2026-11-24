-- ForestWatch AI - MySQL 8 schema. The app also runs CREATE TABLE IF NOT EXISTS on startup;
-- this script is for creating the database/user and for DBAs who prefer explicit DDL.
CREATE DATABASE IF NOT EXISTS forestwatch CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- CREATE USER 'forestwatch'@'localhost' IDENTIFIED BY 'change_me';
-- GRANT ALL PRIVILEGES ON forestwatch.* TO 'forestwatch'@'localhost'; FLUSH PRIVILEGES;
USE forestwatch;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(190) NOT NULL,
  name VARCHAR(120) NOT NULL,
  password_hash VARCHAR(100) NOT NULL,
  notify_email TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY ix_users_email (email)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS monitored_locations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  name VARCHAR(160) NOT NULL,
  west DOUBLE NOT NULL, south DOUBLE NOT NULL, east DOUBLE NOT NULL, north DOUBLE NOT NULL,
  area_ha DOUBLE NOT NULL,
  monitoring_enabled TINYINT(1) NOT NULL DEFAULT 0,
  frequency_days INT NOT NULL DEFAULT 7,
  monitoring_status VARCHAR(40) NOT NULL DEFAULT 'idle',
  monitoring_message VARCHAR(400) NULL,
  latest_observation DATE NULL,
  last_checked_at DATETIME NULL,
  last_analysis_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_loc_user (user_id),
  CONSTRAINT fk_loc_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS satellite_images (
  id INT AUTO_INCREMENT PRIMARY KEY,
  location_id INT NULL,
  user_id INT NOT NULL,
  source VARCHAR(40) NOT NULL,
  acquisition_from DATE NOT NULL,
  acquisition_to DATE NOT NULL,
  cloud_cover_pct DOUBLE NULL,
  valid_pixel_pct DOUBLE NULL,
  bbox JSON NOT NULL,
  file_path VARCHAR(300) NOT NULL,
  is_demo TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_img_loc (location_id), KEY ix_img_user (user_id),
  CONSTRAINT fk_img_loc FOREIGN KEY (location_id) REFERENCES monitored_locations(id) ON DELETE SET NULL,
  CONSTRAINT fk_img_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS deforestation_analysis (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  location_id INT NULL,
  before_image_id INT NULL,
  after_image_id INT NULL,
  bbox JSON NOT NULL,
  place_name VARCHAR(200) NULL,
  before_date DATE NOT NULL,
  after_date DATE NOT NULL,
  method VARCHAR(60) NOT NULL DEFAULT 'ndvi-rules-v1',
  thresholds JSON NOT NULL,
  mean_ndvi_before DOUBLE NULL, mean_ndvi_after DOUBLE NULL,
  forest_area_ha DOUBLE NOT NULL DEFAULT 0,
  loss_ha DOUBLE NOT NULL DEFAULT 0,
  uncertain_ha DOUBLE NOT NULL DEFAULT 0,
  fire_ha DOUBLE NOT NULL DEFAULT 0,
  loss_pct_of_forest DOUBLE NOT NULL DEFAULT 0,
  valid_pixel_pct DOUBLE NOT NULL DEFAULT 0,
  confidence DOUBLE NULL,
  is_demo TINYINT(1) NOT NULL DEFAULT 0,
  report_text TEXT NULL,
  overlay_path VARCHAR(300) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_an_user (user_id), KEY ix_an_loc (location_id), KEY ix_an_created (created_at),
  KEY ix_analysis_user_created (user_id, created_at),
  CONSTRAINT fk_an_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_an_loc FOREIGN KEY (location_id) REFERENCES monitored_locations(id) ON DELETE CASCADE,
  CONSTRAINT fk_an_bimg FOREIGN KEY (before_image_id) REFERENCES satellite_images(id) ON DELETE SET NULL,
  CONSTRAINT fk_an_aimg FOREIGN KEY (after_image_id) REFERENCES satellite_images(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS deforestation_alerts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  analysis_id INT NOT NULL,
  location_id INT NULL,
  location_name VARCHAR(200) NOT NULL,
  lat DOUBLE NOT NULL, lon DOUBLE NOT NULL,
  detection_date DATE NOT NULL,
  loss_ha DOUBLE NOT NULL,
  severity VARCHAR(10) NOT NULL,
  status VARCHAR(12) NOT NULL DEFAULT 'NEW',
  is_demo TINYINT(1) NOT NULL DEFAULT 0,
  reviewed_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_al_user (user_id), KEY ix_al_an (analysis_id), KEY ix_al_loc (location_id), KEY ix_al_sev (severity), KEY ix_al_status (status),
  CONSTRAINT fk_al_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_al_an FOREIGN KEY (analysis_id) REFERENCES deforestation_analysis(id) ON DELETE CASCADE,
  CONSTRAINT fk_al_loc FOREIGN KEY (location_id) REFERENCES monitored_locations(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS analysis_history (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  analysis_id INT NULL,
  action VARCHAR(40) NOT NULL,
  detail VARCHAR(500) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_h_user (user_id), KEY ix_h_action (action), KEY ix_h_created (created_at),
  CONSTRAINT fk_h_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_h_an FOREIGN KEY (analysis_id) REFERENCES deforestation_analysis(id) ON DELETE SET NULL
) ENGINE=InnoDB;
