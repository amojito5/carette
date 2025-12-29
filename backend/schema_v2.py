"""
Carette - Schéma BDD Simplifié (Version Widget Sans Comptes)
Migration vers modèle email/téléphone simple
"""

# ============================================
# NOUVELLE STRUCTURE SIMPLIFIÉE
# ============================================

CREATE_OFFERS_SIMPLE = """
CREATE TABLE IF NOT EXISTS carpool_offers_v2 (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Conducteur (pas de user_id, juste contact direct)
    driver_email VARCHAR(255) NOT NULL,
    driver_phone VARCHAR(20) NOT NULL,
    driver_name VARCHAR(100),
    
    -- Trajet
    departure VARCHAR(255) NOT NULL,
    destination VARCHAR(255) NOT NULL,
    departure_coords JSON,
    destination_coords JSON,
    datetime DATETIME NOT NULL,
    seats_available INT NOT NULL DEFAULT 1,
    
    -- Route et zones (optionnel pour matching avancé)
    route_geometry JSON,
    detour_zone JSON,
    max_detour_km INT DEFAULT 10,
    
    -- Événement lié
    event_id VARCHAR(255),
    event_name VARCHAR(255),
    event_location VARCHAR(255),
    event_date DATE,
    
    -- Métadonnées
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    status ENUM('active', 'full', 'expired', 'cancelled') DEFAULT 'active',
    
    -- Indexes
    INDEX idx_datetime (datetime),
    INDEX idx_event_id (event_id),
    INDEX idx_status (status),
    INDEX idx_driver_email (driver_email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

CREATE_RESERVATIONS_SIMPLE = """
CREATE TABLE IF NOT EXISTS carpool_reservations_v2 (
    id INT AUTO_INCREMENT PRIMARY KEY,
    offer_id INT NOT NULL,
    
    -- Passager (pas de user_id)
    passenger_email VARCHAR(255) NOT NULL,
    passenger_phone VARCHAR(20) NOT NULL,
    passenger_name VARCHAR(100),
    passengers_count INT DEFAULT 1,
    
    -- Statut
    status ENUM('pending', 'confirmed', 'rejected', 'cancelled') DEFAULT 'pending',
    
    -- Paiement (simulé pour l'instant)
    payment_status ENUM('none', 'simulated', 'paid') DEFAULT 'simulated',
    payment_amount DECIMAL(5,2) DEFAULT 1.00,
    
    -- Métadonnées
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at DATETIME,
    cancelled_at DATETIME,
    
    -- Contrainte unicité
    FOREIGN KEY (offer_id) REFERENCES carpool_offers_v2(id) ON DELETE CASCADE,
    INDEX idx_offer_id (offer_id),
    INDEX idx_passenger_email (passenger_email),
    INDEX idx_status (status),
    UNIQUE KEY uniq_passenger_offer (offer_id, passenger_email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

CREATE_CONFIRMATION_TOKENS = """
CREATE TABLE IF NOT EXISTS confirmation_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    token VARCHAR(64) UNIQUE NOT NULL,
    reservation_id INT NOT NULL,
    action ENUM('accept', 'reject') NOT NULL,
    expires_at DATETIME NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    used_at DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (reservation_id) REFERENCES carpool_reservations_v2(id) ON DELETE CASCADE,
    INDEX idx_token (token),
    INDEX idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

# ============================================
# SCRIPT DE MIGRATION (Si besoin de migrer données existantes)
# ============================================

MIGRATION_NOTE = """
-- Si vous avez déjà des données dans les anciennes tables,
-- vous pouvez migrer avec :

INSERT INTO carpool_offers_v2 
    (driver_email, driver_phone, departure, destination, datetime, 
     seats_available, event_id, event_name, event_location, event_date)
SELECT 
    user_id as driver_email,  -- Remplacer par email si disponible
    '' as driver_phone,        -- À compléter manuellement
    departure, 
    destination, 
    datetime,
    seats,
    event_id,
    event_name,
    event_location,
    event_date
FROM carpool_offers;

-- OU simplement repartir de zéro si en phase de test
"""
