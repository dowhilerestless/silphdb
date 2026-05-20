-- 0. Custom Types (Must be created before the tables that use them)
CREATE TYPE grading_enum AS ENUM ('Graded', 'Raw');
CREATE TYPE condition_enum AS ENUM ('M', 'NM', 'LP', 'MP', 'HP', 'DMG', 'UKN');

-- 1. Sets
CREATE TABLE sets (
    set_id VARCHAR(50) PRIMARY KEY,
    set_name VARCHAR(100) NOT NULL,
    printed_total INT DEFAULT 0,
    total_cards INT DEFAULT 0,
    series VARCHAR(50),
    release_date DATE
);

-- 2. Pokedex
CREATE TABLE pokedex (
    pokedex_number INT PRIMARY KEY,
    pokemon_name VARCHAR(100) NOT NULL,
    generation INT DEFAULT 1,
    primary_type VARCHAR(20),
    secondary_type VARCHAR(20),
    evolution_chain_id INT 
);

-- 3. The Cards
CREATE TABLE cards (
    definition_id VARCHAR(50) PRIMARY KEY,
    pokedex_number INT REFERENCES pokedex(pokedex_number),
    set_id VARCHAR(50) REFERENCES sets(set_id),
    card_number VARCHAR(10),
    print_run VARCHAR(20), 
    language VARCHAR(10),  
    finish VARCHAR(20),
    rarity VARCHAR(50),   
    artist VARCHAR(100),
    printed_name VARCHAR(100)
);

-- 4. The Events (Renamed and generalized)
CREATE TABLE events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_date DATE NOT NULL,
    event_type VARCHAR(20), 
    platform VARCHAR(100),
    item_amount DECIMAL(10, 2) DEFAULT 0.00,
    shipping_amount DECIMAL(10, 2) DEFAULT 0.00,
    tax_amount DECIMAL(10, 2) DEFAULT 0.00,
    total_amount DECIMAL(10, 2) GENERATED ALWAYS AS (item_amount + shipping_amount + tax_amount) STORED,
    counterparty VARCHAR(100)
);

-- 5. The Assets (Updated with lifecycle event tracking)
CREATE TABLE assets (
    asset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    definition_id VARCHAR(50) REFERENCES cards(definition_id),
    acquisition_event_id UUID REFERENCES events(event_id),
    disposition_event_id UUID REFERENCES events(event_id),
    storage_location VARCHAR(50), 
    is_active_display BOOLEAN DEFAULT TRUE,
    surface_grade INT CHECK (surface_grade BETWEEN 1 AND 10),
    corners_grade INT CHECK (corners_grade BETWEEN 1 AND 10),
    edges_grade INT CHECK (edges_grade BETWEEN 1 AND 10),
    centering_grade INT CHECK (centering_grade BETWEEN 1 AND 10),
    has_swirl BOOLEAN DEFAULT FALSE,
    curator_notes TEXT,
    grading_status grading_enum,
    raw_condition condition_enum
);

-- 6. Binders & Mapping
CREATE TABLE binders (
    binder_id VARCHAR(50) PRIMARY KEY, 
    display_name TEXT,                  
    max_pokedex_id INT DEFAULT 151     
);

CREATE TABLE binder_sets (
    binder_id VARCHAR(50) REFERENCES binders(binder_id),
    set_id VARCHAR(20),
    PRIMARY KEY (binder_id, set_id)
);