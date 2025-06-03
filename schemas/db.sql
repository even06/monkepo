-- =====================================================
-- POKEMON BATTLE BOT - CLEAN INSTALL
-- This will drop existing tables and recreate everything
-- =====================================================

-- Create/use the database
CREATE DATABASE IF NOT EXISTS pokemon_battle_bot 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE pokemon_battle_bot;

-- Drop existing tables in correct order (foreign keys first)
DROP TABLE IF EXISTS pokemon_moves;
DROP TABLE IF EXISTS pokemon;
DROP TABLE IF EXISTS pokemon_movesets;
DROP TABLE IF EXISTS battle_participants;
DROP TABLE IF EXISTS battles;
DROP TABLE IF EXISTS pending_choices;
DROP TABLE IF EXISTS user_items;
DROP TABLE IF EXISTS moves;
DROP TABLE IF EXISTS pokemon_species;
DROP TABLE IF EXISTS servers;
DROP TABLE IF EXISTS users;

-- =====================================================
-- USERS TABLE - Core user management
-- =====================================================
CREATE TABLE users (
    id VARCHAR(20) PRIMARY KEY,  -- Discord user ID
    username VARCHAR(50) NOT NULL,
    discriminator VARCHAR(4),
    avatar_url VARCHAR(255),
    trainer_level INT DEFAULT 1,
    trainer_xp INT DEFAULT 0,
    coins INT DEFAULT 500,  -- Pokedollars
    battle_points INT DEFAULT 0,
    battles_won INT DEFAULT 0,
    battles_lost INT DEFAULT 0,
    current_streak INT DEFAULT 0,
    best_streak INT DEFAULT 0,
    last_battle TIMESTAMP NULL,
    settings JSON DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_username (username),
    INDEX idx_battles_won (battles_won),
    INDEX idx_trainer_level (trainer_level)
);

-- =====================================================
-- POKEMON SPECIES TABLE - Static Pokemon data
-- =====================================================
CREATE TABLE pokemon_species (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    type1 VARCHAR(20) NOT NULL,
    type2 VARCHAR(20) NULL,
    base_hp INT NOT NULL,
    base_attack INT NOT NULL,
    base_defense INT NOT NULL,
    base_sp_attack INT NOT NULL,
    base_sp_defense INT NOT NULL,
    base_speed INT NOT NULL,
    evolution_level INT NULL,
    evolution_into INT NULL,
    evolution_method VARCHAR(20) DEFAULT 'LEVEL',
    evolution_requirement VARCHAR(50) NULL,
    sprite_url VARCHAR(255) NULL,
    pokedex_number INT UNIQUE NOT NULL,
    generation INT DEFAULT 1,
    rarity VARCHAR(20) DEFAULT 'COMMON',
    
    INDEX idx_pokedex_number (pokedex_number),
    INDEX idx_type1 (type1),
    INDEX idx_evolution_level (evolution_level)
);

-- =====================================================
-- MOVES TABLE - All available moves
-- =====================================================
CREATE TABLE moves (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    type VARCHAR(20) NOT NULL,
    category VARCHAR(20) NOT NULL,  -- PHYSICAL, SPECIAL, STATUS
    power INT NULL,
    accuracy INT NOT NULL,
    base_pp INT NOT NULL,
    priority INT DEFAULT 0,
    effect_description TEXT NULL,
    effect_data JSON DEFAULT NULL,
    is_signature BOOLEAN DEFAULT FALSE,
    
    INDEX idx_name (name),
    INDEX idx_type (type),
    INDEX idx_category (category)
);

-- =====================================================
-- POKEMON MOVESETS - What moves each species can learn
-- =====================================================
CREATE TABLE pokemon_movesets (
    species_id INT,
    move_id INT,
    learn_method VARCHAR(20) NOT NULL,  -- LEVEL, TM, EGG, TUTOR
    learn_level INT NULL,
    
    PRIMARY KEY (species_id, move_id, learn_method),
    FOREIGN KEY (species_id) REFERENCES pokemon_species(id) ON DELETE CASCADE,
    FOREIGN KEY (move_id) REFERENCES moves(id) ON DELETE CASCADE,
    
    INDEX idx_species_level (species_id, learn_level)
);

-- =====================================================
-- POKEMON TABLE - User's Pokemon instances
-- =====================================================
CREATE TABLE pokemon (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),  -- MySQL UUID
    user_id VARCHAR(20) NOT NULL,
    species_id INT NOT NULL,
    nickname VARCHAR(50) NULL,
    level INT DEFAULT 5 CHECK (level BETWEEN 1 AND 50),  -- MVP cap at 50
    experience INT DEFAULT 0,
    is_starter BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,  -- In active team vs storage
    team_slot INT NULL CHECK (team_slot BETWEEN 1 AND 3),  -- MVP: 3v3 battles
    friendship INT DEFAULT 50 CHECK (friendship BETWEEN 0 AND 255),
    nature VARCHAR(20) NOT NULL DEFAULT 'HARDY',
    gender VARCHAR(10) DEFAULT 'UNKNOWN',
    
    -- Individual Values (0-31) - Pokemon genetics
    hp_iv INT DEFAULT 0 CHECK (hp_iv BETWEEN 0 AND 31),
    attack_iv INT DEFAULT 0 CHECK (attack_iv BETWEEN 0 AND 31),
    defense_iv INT DEFAULT 0 CHECK (defense_iv BETWEEN 0 AND 31),
    sp_attack_iv INT DEFAULT 0 CHECK (sp_attack_iv BETWEEN 0 AND 31),
    sp_defense_iv INT DEFAULT 0 CHECK (sp_defense_iv BETWEEN 0 AND 31),
    speed_iv INT DEFAULT 0 CHECK (speed_iv BETWEEN 0 AND 31),
    
    -- Current battle status
    current_hp INT NULL,  -- NULL means full HP
    status_condition VARCHAR(20) DEFAULT 'HEALTHY',
    status_turns INT DEFAULT 0,
    
    -- Metadata
    original_trainer VARCHAR(20) NOT NULL,
    caught_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    caught_location VARCHAR(50) DEFAULT 'STARTER_LAB',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (species_id) REFERENCES pokemon_species(id),
    FOREIGN KEY (original_trainer) REFERENCES users(id),
    
    INDEX idx_user_active (user_id, is_active),
    INDEX idx_user_team (user_id, team_slot),
    INDEX idx_species (species_id),
    INDEX idx_level (level)
);

-- =====================================================
-- POKEMON MOVES - Current moveset for each Pokemon
-- =====================================================
CREATE TABLE pokemon_moves (
    pokemon_id CHAR(36),
    move_id INT,
    slot INT CHECK (slot BETWEEN 1 AND 4),
    current_pp INT NOT NULL,
    max_pp INT NOT NULL,
    
    PRIMARY KEY (pokemon_id, slot),
    FOREIGN KEY (pokemon_id) REFERENCES pokemon(id) ON DELETE CASCADE,
    FOREIGN KEY (move_id) REFERENCES moves(id) ON DELETE CASCADE,
    
    INDEX idx_pokemon_moves (pokemon_id)
);

-- =====================================================
-- BATTLES TABLE - Battle instances
-- =====================================================
CREATE TABLE battles (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    player1_id VARCHAR(20) NOT NULL,
    player2_id VARCHAR(20) NOT NULL,
    winner_id VARCHAR(20) NULL,
    battle_format VARCHAR(20) DEFAULT '3v3',
    battle_type VARCHAR(20) DEFAULT 'SINGLES',
    turn_count INT DEFAULT 0,
    weather VARCHAR(20) DEFAULT 'NONE',
    battle_data JSON DEFAULT NULL,  -- Complete battle log for replays
    spectator_data JSON DEFAULT NULL,  -- Chat, predictions, reactions
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL,
    status VARCHAR(20) DEFAULT 'WAITING',  -- WAITING, ACTIVE, COMPLETED, ABANDONED
    
    FOREIGN KEY (player1_id) REFERENCES users(id),
    FOREIGN KEY (player2_id) REFERENCES users(id),
    FOREIGN KEY (winner_id) REFERENCES users(id),
    
    INDEX idx_battles_participants (player1_id, player2_id),
    INDEX idx_battles_status (status),
    INDEX idx_battles_date (started_at)
);

-- =====================================================
-- BATTLE PARTICIPANTS - Team snapshots for battles
-- =====================================================
CREATE TABLE battle_participants (
    battle_id CHAR(36),
    user_id VARCHAR(20),
    team_data JSON NOT NULL,  -- Snapshot of team at battle start
    final_xp_gained INT DEFAULT 0,
    performance_data JSON DEFAULT NULL,  -- Damage dealt, KOs, etc.
    
    PRIMARY KEY (battle_id, user_id),
    FOREIGN KEY (battle_id) REFERENCES battles(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- =====================================================
-- USER ITEMS - Inventory system
-- =====================================================
CREATE TABLE user_items (
    user_id VARCHAR(20),
    item_type VARCHAR(50) NOT NULL,
    item_id VARCHAR(50) NOT NULL,
    quantity INT DEFAULT 1,
    acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (user_id, item_type, item_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    INDEX idx_user_items (user_id, item_type)
);

-- =====================================================
-- PENDING CHOICES - Player decisions (move learning, evolution, etc.)
-- =====================================================
CREATE TABLE pending_choices (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    pokemon_id CHAR(36) NOT NULL,
    choice_type VARCHAR(20) NOT NULL,  -- MOVE_LEARN, EVOLUTION, NICKNAME
    choice_data JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    
    FOREIGN KEY (pokemon_id) REFERENCES pokemon(id) ON DELETE CASCADE,
    
    INDEX idx_pending_pokemon (pokemon_id),
    INDEX idx_pending_expires (expires_at)
);

-- =====================================================
-- SERVERS TABLE - Discord server settings
-- =====================================================
CREATE TABLE servers (
    id VARCHAR(20) PRIMARY KEY,  -- Discord server ID
    name VARCHAR(100) NOT NULL,
    settings JSON DEFAULT NULL,
    battle_channel VARCHAR(20) NULL,
    announcement_channel VARCHAR(20) NULL,
    is_premium BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_server_name (name)
);

-- =====================================================
-- ADD FOREIGN KEY CONSTRAINTS FOR EVOLUTION CHAINS
-- (Done after table creation to avoid circular dependencies)
-- =====================================================
ALTER TABLE pokemon_species 
ADD CONSTRAINT fk_evolution_into 
FOREIGN KEY (evolution_into) REFERENCES pokemon_species(id) ON DELETE SET NULL;

-- =====================================================
-- INITIAL DATA SEEDING - POKEMON SPECIES
-- =====================================================
INSERT INTO pokemon_species (name, type1, type2, base_hp, base_attack, base_defense, base_sp_attack, base_sp_defense, base_speed, evolution_level, pokedex_number, rarity) VALUES
-- Starter Line 1: Charmander
('Charmander', 'FIRE', NULL, 39, 52, 43, 60, 50, 65, 16, 4, 'STARTER'),
('Charmeleon', 'FIRE', NULL, 58, 64, 58, 80, 65, 80, 36, 5, 'STARTER'),
('Charizard', 'FIRE', 'FLYING', 78, 84, 78, 109, 85, 100, NULL, 6, 'STARTER'),

-- Starter Line 2: Squirtle  
('Squirtle', 'WATER', NULL, 44, 48, 65, 50, 64, 43, 16, 7, 'STARTER'),
('Wartortle', 'WATER', NULL, 59, 63, 80, 65, 80, 58, 36, 8, 'STARTER'),
('Blastoise', 'WATER', NULL, 79, 83, 100, 85, 105, 78, NULL, 9, 'STARTER'),

-- Starter Line 3: Bulbasaur
('Bulbasaur', 'GRASS', 'POISON', 45, 49, 49, 65, 65, 45, 16, 1, 'STARTER'),
('Ivysaur', 'GRASS', 'POISON', 60, 62, 63, 80, 80, 60, 32, 2, 'STARTER'),
('Venusaur', 'GRASS', 'POISON', 80, 82, 83, 100, 100, 80, NULL, 3, 'STARTER'),

-- Common Pokemon Lines
('Caterpie', 'BUG', NULL, 45, 30, 35, 20, 20, 45, 7, 10, 'COMMON'),
('Metapod', 'BUG', NULL, 50, 20, 55, 25, 25, 30, 10, 11, 'COMMON'),
('Butterfree', 'BUG', 'FLYING', 60, 45, 50, 90, 80, 70, NULL, 12, 'COMMON'),

('Weedle', 'BUG', 'POISON', 40, 35, 30, 20, 20, 50, 7, 13, 'COMMON'),
('Kakuna', 'BUG', 'POISON', 45, 25, 50, 25, 25, 35, 10, 14, 'COMMON'),
('Beedrill', 'BUG', 'POISON', 65, 90, 40, 45, 80, 75, NULL, 15, 'COMMON'),

('Pidgey', 'NORMAL', 'FLYING', 40, 45, 40, 35, 35, 56, 18, 16, 'COMMON'),
('Pidgeotto', 'NORMAL', 'FLYING', 63, 60, 55, 50, 50, 71, 36, 17, 'COMMON'),
('Pidgeot', 'NORMAL', 'FLYING', 83, 80, 75, 70, 70, 101, NULL, 18, 'COMMON'),

('Rattata', 'NORMAL', NULL, 30, 56, 35, 25, 35, 72, 20, 19, 'COMMON'),
('Raticate', 'NORMAL', NULL, 55, 81, 60, 50, 70, 97, NULL, 20, 'COMMON'),

('Pikachu', 'ELECTRIC', NULL, 35, 55, 40, 50, 50, 90, NULL, 25, 'UNCOMMON'),
('Raichu', 'ELECTRIC', NULL, 60, 90, 55, 90, 80, 110, NULL, 26, 'UNCOMMON');

-- Update evolution chains (using temporary table to avoid MySQL limitation)
CREATE TEMPORARY TABLE temp_evolution AS
SELECT 
    p1.id as from_id,
    p2.id as to_id
FROM pokemon_species p1
JOIN pokemon_species p2 ON (
    (p1.name = 'Charmander' AND p2.name = 'Charmeleon') OR
    (p1.name = 'Charmeleon' AND p2.name = 'Charizard') OR
    (p1.name = 'Squirtle' AND p2.name = 'Wartortle') OR
    (p1.name = 'Wartortle' AND p2.name = 'Blastoise') OR
    (p1.name = 'Bulbasaur' AND p2.name = 'Ivysaur') OR
    (p1.name = 'Ivysaur' AND p2.name = 'Venusaur') OR
    (p1.name = 'Caterpie' AND p2.name = 'Metapod') OR
    (p1.name = 'Metapod' AND p2.name = 'Butterfree') OR
    (p1.name = 'Weedle' AND p2.name = 'Kakuna') OR
    (p1.name = 'Kakuna' AND p2.name = 'Beedrill') OR
    (p1.name = 'Pidgey' AND p2.name = 'Pidgeotto') OR
    (p1.name = 'Pidgeotto' AND p2.name = 'Pidgeot') OR
    (p1.name = 'Rattata' AND p2.name = 'Raticate')
);

-- Apply the evolution chains
UPDATE pokemon_species ps
JOIN temp_evolution te ON ps.id = te.from_id
SET ps.evolution_into = te.to_id;

-- Clean up
DROP TEMPORARY TABLE temp_evolution;

-- =====================================================
-- INITIAL DATA SEEDING - MOVES
-- =====================================================
INSERT INTO moves (name, type, category, power, accuracy, base_pp, priority, effect_description) VALUES
-- Normal moves
('Tackle', 'NORMAL', 'PHYSICAL', 40, 100, 35, 0, 'A physical attack with no additional effects.'),
('Scratch', 'NORMAL', 'PHYSICAL', 40, 100, 35, 0, 'A physical attack with sharp claws.'),
('Quick Attack', 'NORMAL', 'PHYSICAL', 40, 100, 30, 1, 'A priority move that always goes first.'),
('Hyper Beam', 'NORMAL', 'SPECIAL', 150, 90, 5, 0, 'Powerful attack that requires recharging.'),

-- Fire moves  
('Ember', 'FIRE', 'SPECIAL', 40, 100, 25, 0, 'May burn the target.'),
('Flamethrower', 'FIRE', 'SPECIAL', 90, 100, 15, 0, 'May burn the target.'),
('Fire Blast', 'FIRE', 'SPECIAL', 110, 85, 5, 0, 'High chance to burn the target.'),

-- Water moves
('Water Gun', 'WATER', 'SPECIAL', 40, 100, 25, 0, 'A basic water attack.'),
('Bubble Beam', 'WATER', 'SPECIAL', 65, 100, 20, 0, 'May lower target Speed.'),
('Surf', 'WATER', 'SPECIAL', 90, 100, 15, 0, 'A powerful water attack.'),
('Hydro Pump', 'WATER', 'SPECIAL', 110, 80, 5, 0, 'A very powerful water attack.'),

-- Grass moves
('Vine Whip', 'GRASS', 'PHYSICAL', 45, 100, 25, 0, 'A basic grass attack.'),
('Razor Leaf', 'GRASS', 'PHYSICAL', 55, 95, 25, 0, 'High critical hit ratio.'),
('Solar Beam', 'GRASS', 'SPECIAL', 120, 100, 10, 0, 'Charges first turn, attacks second.'),

-- Electric moves
('Thunder Shock', 'ELECTRIC', 'SPECIAL', 40, 100, 30, 0, 'May paralyze the target.'),
('Thunderbolt', 'ELECTRIC', 'SPECIAL', 90, 100, 15, 0, 'May paralyze the target.'),
('Thunder', 'ELECTRIC', 'SPECIAL', 110, 70, 10, 0, 'High chance to paralyze.'),

-- Bug moves
('String Shot', 'BUG', 'STATUS', 0, 95, 40, 0, 'Lowers target Speed.'),
('Bug Bite', 'BUG', 'PHYSICAL', 60, 100, 20, 0, 'A basic bug attack.'),

-- Flying moves
('Gust', 'FLYING', 'SPECIAL', 40, 100, 35, 0, 'A basic flying attack.'),
('Wing Attack', 'FLYING', 'PHYSICAL', 60, 100, 35, 0, 'A basic flying attack.'),
('Air Slash', 'FLYING', 'SPECIAL', 75, 95, 15, 0, 'May cause flinching.'),

-- Poison moves
('Poison Sting', 'POISON', 'PHYSICAL', 15, 100, 35, 0, 'May poison the target.'),
('Sludge Bomb', 'POISON', 'SPECIAL', 90, 100, 10, 0, 'May poison the target.'),

-- Status moves
('Growl', 'NORMAL', 'STATUS', 0, 100, 40, 0, 'Lowers target Attack.'),
('Tail Whip', 'NORMAL', 'STATUS', 0, 100, 30, 0, 'Lowers target Defense.'),
('Leer', 'NORMAL', 'STATUS', 0, 100, 30, 0, 'Lowers target Defense.'),
('Sleep Powder', 'GRASS', 'STATUS', 0, 75, 15, 0, 'Puts target to sleep.'),
('Stun Spore', 'GRASS', 'STATUS', 0, 75, 30, 0, 'Paralyzes the target.'),
('Poison Powder', 'GRASS', 'STATUS', 0, 75, 35, 0, 'Poisons the target.');

-- =====================================================
-- POKEMON MOVESETS - Basic movesets for MVP
-- =====================================================
INSERT INTO pokemon_movesets (species_id, move_id, learn_method, learn_level) VALUES
-- Charmander movesets
(1, 2, 'LEVEL', 1),   -- Scratch
(1, 23, 'LEVEL', 1),  -- Growl  
(1, 5, 'LEVEL', 7),   -- Ember
(1, 6, 'LEVEL', 13),  -- Flamethrower

-- Squirtle movesets
(4, 1, 'LEVEL', 1),   -- Tackle
(4, 24, 'LEVEL', 1),  -- Tail Whip
(4, 8, 'LEVEL', 7),   -- Water Gun
(4, 9, 'LEVEL', 13),  -- Bubble Beam

-- Bulbasaur movesets  
(7, 1, 'LEVEL', 1),   -- Tackle
(7, 23, 'LEVEL', 1),  -- Growl
(7, 12, 'LEVEL', 7),  -- Vine Whip
(7, 13, 'LEVEL', 13), -- Razor Leaf

-- Basic moves for common Pokemon
(10, 1, 'LEVEL', 1),  -- Caterpie: Tackle
(10, 17, 'LEVEL', 1), -- Caterpie: String Shot
(13, 1, 'LEVEL', 1),  -- Weedle: Tackle  
(13, 21, 'LEVEL', 1), -- Weedle: Poison Sting
(16, 1, 'LEVEL', 1),  -- Pidgey: Tackle
(16, 19, 'LEVEL', 1), -- Pidgey: Gust
(19, 1, 'LEVEL', 1),  -- Rattata: Tackle
(19, 3, 'LEVEL', 1),  -- Rattata: Quick Attack
(21, 15, 'LEVEL', 1), -- Pikachu: Thunder Shock
(21, 16, 'LEVEL', 15); -- Pikachu: Thunderbolt

-- =====================================================
-- HELPER FUNCTIONS AND PROCEDURES
-- =====================================================

-- Function to get XP needed for next level
DELIMITER //
CREATE FUNCTION GetXPForLevel(level_num INT) 
RETURNS INT
READS SQL DATA
DETERMINISTIC
BEGIN
    RETURN (level_num * 100) + (level_num * level_num * 10);
END //
DELIMITER ;

-- Procedure to calculate Pokemon stats
DELIMITER //
CREATE PROCEDURE CalculatePokemonStats(
    IN pokemon_uuid CHAR(36)
)
BEGIN
    DECLARE poke_level INT;
    DECLARE species_hp, species_att, species_def, species_spa, species_spd, species_spe INT;
    DECLARE iv_hp, iv_att, iv_def, iv_spa, iv_spd, iv_spe INT;
    DECLARE calc_hp, calc_att, calc_def, calc_spa, calc_spd, calc_spe INT;
    
    -- Get Pokemon data
    SELECT p.level, s.base_hp, s.base_attack, s.base_defense, s.base_sp_attack, s.base_sp_defense, s.base_speed,
           p.hp_iv, p.attack_iv, p.defense_iv, p.sp_attack_iv, p.sp_defense_iv, p.speed_iv
    INTO poke_level, species_hp, species_att, species_def, species_spa, species_spd, species_spe,
         iv_hp, iv_att, iv_def, iv_spa, iv_spd, iv_spe
    FROM pokemon p
    JOIN pokemon_species s ON p.species_id = s.id
    WHERE p.id = pokemon_uuid;
    
    -- Calculate stats using Pokemon formula
    SET calc_hp = FLOOR(((2 * species_hp + iv_hp) * poke_level / 100) + poke_level + 10);
    SET calc_att = FLOOR(((2 * species_att + iv_att) * poke_level / 100) + 5);
    SET calc_def = FLOOR(((2 * species_def + iv_def) * poke_level / 100) + 5);
    SET calc_spa = FLOOR(((2 * species_spa + iv_spa) * poke_level / 100) + 5);
    SET calc_spd = FLOOR(((2 * species_spd + iv_spd) * poke_level / 100) + 5);
    SET calc_spe = FLOOR(((2 * species_spe + iv_spe) * poke_level / 100) + 5);
    
    -- Return calculated stats
    SELECT calc_hp as hp, calc_att as attack, calc_def as defense, 
           calc_spa as sp_attack, calc_spd as sp_defense, calc_spe as speed;
END //
DELIMITER ;

-- =====================================================
-- USEFUL VIEWS
-- =====================================================

-- View for complete Pokemon data with calculated stats
CREATE VIEW pokemon_full AS
SELECT 
    p.id as pokemon_id,
    p.user_id,
    p.species_id,
    p.nickname,
    p.level,
    p.experience,
    p.is_starter,
    p.is_active,
    p.team_slot,
    p.friendship,
    p.nature,
    p.gender,
    p.hp_iv,
    p.attack_iv,
    p.defense_iv,
    p.sp_attack_iv,
    p.sp_defense_iv,
    p.speed_iv,
    p.current_hp,
    p.status_condition,
    p.status_turns,
    p.original_trainer,
    p.caught_at,
    p.caught_location,
    p.created_at,
    p.updated_at,
    s.name as species_name,
    s.type1,
    s.type2,
    s.pokedex_number,
    s.evolution_level,
    s.evolution_into,
    -- Calculate stats on the fly
    FLOOR(((2 * s.base_hp + p.hp_iv) * p.level / 100) + p.level + 10) as max_hp_calculated,
    FLOOR(((2 * s.base_attack + p.attack_iv) * p.level / 100) + 5) as attack_calculated,
    FLOOR(((2 * s.base_defense + p.defense_iv) * p.level / 100) + 5) as defense_calculated,
    FLOOR(((2 * s.base_sp_attack + p.sp_attack_iv) * p.level / 100) + 5) as sp_attack_calculated,
    FLOOR(((2 * s.base_sp_defense + p.sp_defense_iv) * p.level / 100) + 5) as sp_defense_calculated,
    FLOOR(((2 * s.base_speed + p.speed_iv) * p.level / 100) + 5) as speed_calculated
FROM pokemon p
JOIN pokemon_species s ON p.species_id = s.id;

-- View for active teams
CREATE VIEW active_teams AS
SELECT 
    u.username,
    u.id as user_id,
    p.id as pokemon_id,
    p.species_id,
    p.nickname,
    p.level,
    p.experience,
    p.is_starter,
    p.team_slot,
    p.friendship,
    p.nature,
    p.gender,
    p.hp_iv,
    p.attack_iv,
    p.defense_iv,
    p.sp_attack_iv,
    p.sp_defense_iv,
    p.speed_iv,
    p.current_hp,
    p.status_condition,
    p.status_turns,
    s.name as species_name,
    s.type1,
    s.type2
FROM users u
JOIN pokemon p ON u.id = p.user_id
JOIN pokemon_species s ON p.species_id = s.id
WHERE p.is_active = TRUE
ORDER BY u.id, p.team_slot;


-- =====================================================
-- DATABASE UPDATES FOR PERSISTENT BUTTONS & SERVER CONFIG
-- Run these ALTER statements on your existing database
-- =====================================================

USE pokemon_battle_bot;

-- Add persistent button and configuration columns to servers table
ALTER TABLE servers 
ADD COLUMN language VARCHAR(5) DEFAULT 'en',
ADD COLUMN starter_channel_id VARCHAR(20) NULL,
ADD COLUMN starter_message_id VARCHAR(20) NULL,
ADD COLUMN updates_channel_id VARCHAR(20) NULL,
ADD COLUMN last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

-- Create table for tracking persistent buttons
CREATE TABLE persistent_buttons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    server_id VARCHAR(20) NOT NULL,
    channel_id VARCHAR(20) NOT NULL,
    message_id VARCHAR(20) NOT NULL,
    button_type VARCHAR(50) NOT NULL, -- 'STARTER_SELECTION', 'ADMIN_SETUP', etc.
    button_data JSON DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    
    UNIQUE KEY unique_server_button (server_id, button_type),
    FOREIGN KEY (server_id) REFERENCES servers(id),
    
    INDEX idx_server_type (server_id, button_type),
    INDEX idx_message (channel_id, message_id)
);

-- Create table for pending starter selections (for multi-step process)
CREATE TABLE pending_starters (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id VARCHAR(20) NOT NULL,
    server_id VARCHAR(20) NOT NULL,
    selected_species_id INT NOT NULL,
    pokemon_nickname VARCHAR(50) NULL,
    generated_ivs JSON NOT NULL, -- Store the specific IVs generated for this Pokemon
    step VARCHAR(20) DEFAULT 'SPECIES_SELECTED', -- SPECIES_SELECTED, NAMED, CONFIRMED
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (server_id) REFERENCES servers(id),
    FOREIGN KEY (selected_species_id) REFERENCES pokemon_species(id),
    
    INDEX idx_user_server (user_id, server_id),
    INDEX idx_expires (expires_at)
);

-- Add index for faster server language lookups
CREATE INDEX idx_servers_language ON servers(language);

-- Update existing servers to have default English language
UPDATE servers SET language = 'en' WHERE language IS NULL;

-- Create view for server configuration status
CREATE VIEW server_config_status AS
SELECT 
    s.id as server_id,
    s.name as server_name,
    s.language,
    s.starter_channel_id,
    s.updates_channel_id,
    CASE 
        WHEN s.starter_channel_id IS NOT NULL AND s.updates_channel_id IS NOT NULL THEN 'COMPLETE'
        WHEN s.starter_channel_id IS NOT NULL OR s.updates_channel_id IS NOT NULL THEN 'PARTIAL'
        ELSE 'NOT_CONFIGURED'
    END as config_status,
    pb.message_id as starter_button_message_id,
    pb.is_active as starter_button_active
FROM servers s
LEFT JOIN persistent_buttons pb ON s.id = pb.server_id AND pb.button_type = 'STARTER_SELECTION';

-- Function to clean up expired pending starters
DELIMITER //
CREATE EVENT cleanup_expired_starters
ON SCHEDULE EVERY 1 HOUR
DO
BEGIN
    DELETE FROM pending_starters WHERE expires_at < NOW();
END //
DELIMITER ;

-- Enable event scheduler if not already enabled
SET GLOBAL event_scheduler = ON;

-- Success message
SELECT 'Database updated successfully for persistent buttons and server configuration!' as status;

-- =====================================================
-- SUCCESS MESSAGE
-- =====================================================
SELECT 'Pokemon Battle Bot Database Created Successfully!' as status,
       COUNT(*) as species_count 
FROM pokemon_species;
