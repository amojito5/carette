"""
Script d'initialisation automatique des tables carpool au démarrage.
Crée les tables si elles n'existent pas, puis ajoute les colonnes manquantes.
"""

import sql

def init_carpool_tables():
    """Crée les tables carpool si elles n'existent pas"""
    print("🔄 Initialisation des tables carpool...")
    
    with sql.db_cursor() as cur:
        # Créer carpool_offers
        cur.execute("""
            CREATE TABLE IF NOT EXISTS carpool_offers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                departure VARCHAR(255) NOT NULL,
                destination VARCHAR(255) NOT NULL,
                datetime DATETIME NOT NULL,
                seats INT NOT NULL DEFAULT 1,
                comment TEXT,
                details JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accept_passengers_on_route BOOLEAN DEFAULT TRUE,
                seats_outbound INT,
                seats_return INT,
                route_outbound JSON,
                route_return JSON,
                max_detour_km INT DEFAULT 5,
                max_detour_time INT DEFAULT 25,
                detour_zone_outbound JSON,
                detour_zone_return JSON,
                current_route_geometry JSON,
                current_departure_time DATETIME,
                time_budget_used INT DEFAULT 0,
                original_departure_time DATETIME,
                return_datetime DATETIME,
                current_return_arrival_time DATETIME,
                event_id VARCHAR(255),
                event_name VARCHAR(255),
                event_location VARCHAR(255),
                event_date DATE,
                event_time VARCHAR(50),
                referring_site VARCHAR(255),
                page_url VARCHAR(500),
                INDEX idx_user_id (user_id),
                INDEX idx_datetime (datetime)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table carpool_offers créée/vérifiée")
        
        # Vérifier et ajouter les colonnes manquantes (si table existait déjà)
        cur.execute("SHOW COLUMNS FROM carpool_offers")
        existing_cols = {row[0] for row in cur.fetchall()}
        
        required_cols = {
            'current_route_geometry': 'JSON DEFAULT NULL',
            'current_departure_time': 'DATETIME DEFAULT NULL',
            'time_budget_used': 'INT DEFAULT 0',
            'original_departure_time': 'DATETIME DEFAULT NULL',
            'return_datetime': 'DATETIME DEFAULT NULL',
            'current_return_arrival_time': 'DATETIME DEFAULT NULL',
            'event_id': 'VARCHAR(255)',
            'event_name': 'VARCHAR(255)',
            'event_location': 'VARCHAR(255)',
            'event_date': 'DATE',
            'event_time': 'VARCHAR(50)',
            'referring_site': 'VARCHAR(255)',
            'page_url': 'VARCHAR(500)'
        }
        
        for col_name, col_def in required_cols.items():
            if col_name not in existing_cols:
                try:
                    cur.execute(f"ALTER TABLE carpool_offers ADD COLUMN {col_name} {col_def}")
                    print(f"    ➕ Colonne {col_name} ajoutée")
                except Exception as e:
                    if 'Duplicate column' in str(e):
                        pass  # Un autre worker l'a déjà ajoutée
                    else:
                        raise
        
        # Créer carpool_reservations (sans colonnes dupliquées !)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS carpool_reservations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                offer_id INT NOT NULL,
                passenger_user_id VARCHAR(255) NOT NULL,
                passengers INT NOT NULL DEFAULT 1,
                trip_type ENUM('outbound', 'return', 'both') NOT NULL DEFAULT 'outbound',
                meeting_point_coords JSON,
                meeting_point_address VARCHAR(500),
                detour_route JSON,
                status ENUM('pending', 'confirmed', 'rejected', 'cancelled') NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pickup_order INT,
                pickup_time DATETIME,
                pickup_coords JSON,
                pickup_address VARCHAR(500),
                route_segment_geometry JSON,
                FOREIGN KEY (offer_id) REFERENCES carpool_offers(id) ON DELETE CASCADE,
                INDEX idx_offer_id (offer_id),
                INDEX idx_passenger_user_id (passenger_user_id),
                INDEX idx_status (status),
                UNIQUE KEY uniq_user_offer_trip (offer_id, passenger_user_id, trip_type)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table carpool_reservations créée/vérifiée")
        
        # Vérifier et ajouter les colonnes manquantes
        cur.execute("SHOW COLUMNS FROM carpool_reservations")
        existing_cols = {row[0] for row in cur.fetchall()}
        
        # Supprimer l'ancienne colonne user_id si elle existe encore
        if 'user_id' in existing_cols:
            try:
                cur.execute("ALTER TABLE carpool_reservations DROP COLUMN user_id")
                print("    🗑️ Colonne user_id obsolète supprimée")
            except:
                pass
        
        required_cols = {
            'passenger_user_id': 'VARCHAR(255) NOT NULL',
            'meeting_point_coords': 'JSON DEFAULT NULL',
            'meeting_point_address': 'VARCHAR(500) DEFAULT NULL',
            'detour_route': 'JSON DEFAULT NULL',
            'pickup_order': 'INT DEFAULT NULL',
            'pickup_time': 'DATETIME DEFAULT NULL',
            'pickup_coords': 'JSON DEFAULT NULL',
            'pickup_address': 'VARCHAR(500) DEFAULT NULL',
            'route_segment_geometry': 'JSON DEFAULT NULL'
        }
        
        for col_name, col_def in required_cols.items():
            if col_name not in existing_cols:
                try:
                    cur.execute(f"ALTER TABLE carpool_reservations ADD COLUMN {col_name} {col_def}")
                    print(f"    ➕ Colonne {col_name} ajoutée")
                except Exception as e:
                    if 'Duplicate column' in str(e):
                        pass  # Un autre worker l'a déjà ajoutée
                    else:
                        raise
        
        # Vérifier et corriger la contrainte UNIQUE
        cur.execute("SHOW INDEX FROM carpool_reservations WHERE Key_name = 'uniq_user_offer_trip'")
        correct_constraint = cur.fetchall()
        
        if not correct_constraint:
            # La nouvelle contrainte n'existe pas, vérifier l'ancienne
            cur.execute("SHOW INDEX FROM carpool_reservations WHERE Key_name = 'uniq_reservation'")
            old_constraint = cur.fetchall()
            
            if old_constraint:
                # Supprimer l'ancienne contrainte incorrecte
                try:
                    cur.execute("ALTER TABLE carpool_reservations DROP INDEX uniq_reservation")
                    print("    ➖ Ancienne contrainte uniq_reservation supprimée")
                except:
                    pass
            
            # Créer la nouvelle contrainte correcte
            try:
                cur.execute("""
                    ALTER TABLE carpool_reservations 
                    ADD UNIQUE KEY uniq_user_offer_trip (offer_id, passenger_user_id, trip_type)
                """)
                print("    ➕ Nouvelle contrainte uniq_user_offer_trip créée")
            except Exception as e:
                if 'Duplicate key' not in str(e):
                    print(f"    ⚠️ Erreur création contrainte: {e}")
    
    print("✅ Initialisation des tables carpool terminée")

if __name__ == "__main__":
    init_carpool_tables()
