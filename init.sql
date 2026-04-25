-- 1. Pokedex
CREATE TABLE pokedex (
    pokedex_number INT PRIMARY KEY,
    pokemon_name VARCHAR(100) NOT NULL,
    generation INT DEFAULT 1,
    primary_type VARCHAR(20),
    secondary_type VARCHAR(20)
);

-- 2. The Cards
CREATE TABLE cards (
    definition_id VARCHAR(50) PRIMARY KEY,
    pokedex_number INT REFERENCES pokedex(pokedex_number),
    set_name VARCHAR(50),
    card_number VARCHAR(10),
    print_run VARCHAR(20), -- e.g., 'Unlimited', 'Shadowless'
    language VARCHAR(10),  -- e.g., 'EN', 'JP'
    finish VARCHAR(20),   -- e.g., 'Holo', 'Reverse'
    artist VARCHAR(100)
);

-- 3. The Acquisitions
CREATE TABLE acquisition_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_date DATE NOT NULL,
    event_type VARCHAR(20), -- 'Purchase', 'Gift', 'Trade'
    counterparty VARCHAR(100),
    item_cost DECIMAL(10, 2) DEFAULT 0.00,
    shipping_cost DECIMAL(10, 2) DEFAULT 0.00,
    tax_cost DECIMAL(10, 2) DEFAULT 0.00,
    total_cost_basis DECIMAL(10, 2) GENERATED ALWAYS AS (item_cost + shipping_cost + tax_cost) STORED
);

-- 4. The Assets
CREATE TABLE assets (
    asset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    definition_id VARCHAR(50) REFERENCES cards(definition_id),
    event_id UUID REFERENCES acquisition_events(event_id),
    storage_location VARCHAR(50), -- e.g., 'Binder Slot A1'
    is_active_display BOOLEAN DEFAULT TRUE,
    
    -- QA Subgrades
    surface_grade INT CHECK (surface_grade BETWEEN 1 AND 10),
    corners_grade INT CHECK (corners_grade BETWEEN 1 AND 10),
    edges_grade INT CHECK (edges_grade BETWEEN 1 AND 10),
    centering_grade INT CHECK (centering_grade BETWEEN 1 AND 10),
    
    has_swirl BOOLEAN DEFAULT FALSE,
    curator_notes TEXT
);