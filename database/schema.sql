PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS pois (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    osm_type TEXT NOT NULL,
    osm_id INTEGER NOT NULL,

    name TEXT,
    category TEXT NOT NULL,
    subcategory TEXT,

    latitude REAL NOT NULL,
    longitude REAL NOT NULL,

    sector TEXT,
    sector_status TEXT NOT NULL,
    address TEXT,

    tags_json TEXT NOT NULL DEFAULT '{}',

    source TEXT NOT NULL DEFAULT 'OpenStreetMap',

    imported_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    UNIQUE (osm_type, osm_id)
);

CREATE INDEX IF NOT EXISTS idx_pois_category
ON pois(category);

CREATE INDEX IF NOT EXISTS idx_pois_subcategory
ON pois(subcategory);

CREATE INDEX IF NOT EXISTS idx_pois_sector
ON pois(sector);

CREATE INDEX IF NOT EXISTS idx_pois_sector_status
ON pois(sector_status);

CREATE INDEX IF NOT EXISTS idx_pois_name
ON pois(name);

CREATE INDEX IF NOT EXISTS idx_pois_coordinates
ON pois(latitude, longitude);


CREATE TABLE IF NOT EXISTS sectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL UNIQUE,

    source TEXT,

    geometry_json TEXT,

    metadata_json TEXT NOT NULL DEFAULT '{}',

    imported_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS import_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source TEXT NOT NULL,

    area TEXT,

    started_at TEXT NOT NULL,
    completed_at TEXT,

    records_received INTEGER NOT NULL DEFAULT 0,
    records_inserted INTEGER NOT NULL DEFAULT 0,
    records_updated INTEGER NOT NULL DEFAULT 0,

    status TEXT NOT NULL,

    error_message TEXT
);