"""
Script d'initialisation automatique des tables carpool au démarrage.
Crée les tables si elles n'existent pas, puis ajoute les colonnes manquantes.
"""

import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

import sql

def init_carpool_tables():
    """Crée les tables carpool si elles n'existent pas"""
    print("🔄 Initialisation des tables carpool...")
    
    with sql.db_cursor() as cur:
        # Créer carpool_offers
        cur.execute("""
            CREATE TABLE IF NOT EXISTS carpool_offers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(255) DEFAULT NULL,
                company_id INT DEFAULT NULL,
                site_id INT DEFAULT NULL,
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
                driver_email VARCHAR(255),
                driver_name VARCHAR(255),
                driver_phone VARCHAR(50),
                departure_coords JSON,
                destination_coords JSON,
                seats_available INT,
                expires_at DATETIME,
                INDEX idx_user_id (user_id),
                INDEX idx_datetime (datetime),
                INDEX idx_driver_email (driver_email),
                INDEX idx_company_site (company_id, site_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table carpool_offers créée/vérifiée")
        
        # Vérifier et ajouter les colonnes manquantes (si table existait déjà)
        cur.execute("SHOW COLUMNS FROM carpool_offers")
        existing_cols = {row[0] for row in cur.fetchall()}
        
        required_cols = {
            'company_id': 'INT DEFAULT NULL',
            'site_id': 'INT DEFAULT NULL',
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
            'page_url': 'VARCHAR(500)',
            'driver_email': 'VARCHAR(255)',
            'driver_name': 'VARCHAR(255)',
            'driver_phone': 'VARCHAR(50)',
            'departure_coords': 'JSON',
            'destination_coords': 'JSON',
            'seats_available': 'INT',
            'expires_at': 'DATETIME'
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
                passenger_user_id VARCHAR(255) DEFAULT NULL,
                passenger_email VARCHAR(255),
                passenger_name VARCHAR(255),
                passenger_phone VARCHAR(50),
                passengers INT NOT NULL DEFAULT 1,
                trip_type ENUM('outbound', 'return', 'both') NOT NULL DEFAULT 'outbound',
                meeting_point_coords JSON,
                meeting_point_address VARCHAR(500),
                detour_route JSON,
                detour_time_outbound INT DEFAULT NULL,
                detour_time_return INT DEFAULT NULL,
                confirmation_token VARCHAR(64) UNIQUE,
                status ENUM('pending', 'confirmed', 'rejected', 'cancelled', 'expired') NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at DATETIME,
                pickup_order INT,
                pickup_time DATETIME,
                pickup_coords JSON,
                pickup_address VARCHAR(500),
                route_segment_geometry JSON,
                FOREIGN KEY (offer_id) REFERENCES carpool_offers(id) ON DELETE CASCADE,
                INDEX idx_offer_id (offer_id),
                INDEX idx_passenger_user_id (passenger_user_id),
                INDEX idx_passenger_email (passenger_email),
                INDEX idx_confirmation_token (confirmation_token),
                INDEX idx_status (status)
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
            'passenger_user_id': 'VARCHAR(255) DEFAULT NULL',
            'passenger_email': 'VARCHAR(255)',
            'passenger_name': 'VARCHAR(255)',
            'passenger_phone': 'VARCHAR(50)',
            'meeting_point_coords': 'JSON DEFAULT NULL',
            'meeting_point_address': 'VARCHAR(500) DEFAULT NULL',
            'detour_route': 'JSON DEFAULT NULL',
            'detour_time_outbound': 'INT DEFAULT NULL',
            'detour_time_return': 'INT DEFAULT NULL',
            'confirmation_token': 'VARCHAR(64) UNIQUE DEFAULT NULL',
            'confirmed_at': 'DATETIME DEFAULT NULL',
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
        
        # Créer companies (1 abonnement = tous les sites)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                subscription_status ENUM('active', 'cancelled', 'trial') DEFAULT 'trial',
                subscription_started_at DATETIME,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_email (email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table companies créée/vérifiée")
        
        # Créer company_sites (sites d'une entreprise)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS company_sites (
                id INT AUTO_INCREMENT PRIMARY KEY,
                company_id INT NOT NULL,
                site_name VARCHAR(255) NOT NULL,
                site_address TEXT,
                site_coords JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                INDEX idx_company_id (company_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table company_sites créée/vérifiée")
        
        # Créer carpool_offers_recurrent (mode récurrent)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS carpool_offers_recurrent (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(255) DEFAULT NULL,
                company_id INT NOT NULL,
                site_id INT NOT NULL,
                departure VARCHAR(255) NOT NULL,
                destination VARCHAR(255) NOT NULL,
                departure_coords JSON,
                destination_coords JSON,
                recurrent_time TIME NOT NULL,
                monday BOOLEAN DEFAULT 0,
                tuesday BOOLEAN DEFAULT 0,
                wednesday BOOLEAN DEFAULT 0,
                thursday BOOLEAN DEFAULT 0,
                friday BOOLEAN DEFAULT 0,
                saturday BOOLEAN DEFAULT 0,
                sunday BOOLEAN DEFAULT 0,
                seats INT NOT NULL DEFAULT 1,
                comment TEXT,
                route_outbound JSON,
                route_return JSON,
                max_detour_time INT DEFAULT 25,
                detour_zone_outbound JSON,
                detour_zone_return JSON,
                driver_email VARCHAR(255),
                driver_name VARCHAR(255),
                driver_phone VARCHAR(50),
                status ENUM('active', 'cancelled') DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY (site_id) REFERENCES company_sites(id) ON DELETE CASCADE,
                INDEX idx_company_site (company_id, site_id),
                INDEX idx_user_id (user_id),
                INDEX idx_status (status),
                INDEX idx_days (monday, tuesday, wednesday, thursday, friday)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table carpool_offers_recurrent créée/vérifiée")
        
        # Créer carpool_reservations_recurrent (mode récurrent)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS carpool_reservations_recurrent (
                id INT AUTO_INCREMENT PRIMARY KEY,
                offer_id INT NOT NULL,
                passenger_user_id VARCHAR(255) DEFAULT NULL,
                passenger_email VARCHAR(255),
                passenger_name VARCHAR(255),
                passenger_phone VARCHAR(50),
                passengers INT NOT NULL DEFAULT 1,
                monday BOOLEAN DEFAULT 0,
                tuesday BOOLEAN DEFAULT 0,
                wednesday BOOLEAN DEFAULT 0,
                thursday BOOLEAN DEFAULT 0,
                friday BOOLEAN DEFAULT 0,
                saturday BOOLEAN DEFAULT 0,
                sunday BOOLEAN DEFAULT 0,
                trip_type ENUM('outbound', 'return', 'both') NOT NULL DEFAULT 'outbound',
                meeting_point_coords JSON,
                meeting_point_address VARCHAR(500),
                detour_route JSON,
                detour_time_outbound INT DEFAULT NULL,
                detour_time_return INT DEFAULT NULL,
                confirmation_token VARCHAR(64) UNIQUE,
                status ENUM('pending', 'confirmed', 'rejected', 'cancelled') NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at DATETIME,
                FOREIGN KEY (offer_id) REFERENCES carpool_offers_recurrent(id) ON DELETE CASCADE,
                INDEX idx_offer_id (offer_id),
                INDEX idx_passenger_user_id (passenger_user_id),
                INDEX idx_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table carpool_reservations_recurrent créée/vérifiée")
        
        # Créer confirmation_tokens
        cur.execute("""
            CREATE TABLE IF NOT EXISTS confirmation_tokens (
                id INT AUTO_INCREMENT PRIMARY KEY,
                reservation_id INT NOT NULL,
                token VARCHAR(64) NOT NULL UNIQUE,
                action ENUM('confirm', 'reject') NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (reservation_id) REFERENCES carpool_reservations(id) ON DELETE CASCADE,
                INDEX idx_token (token),
                INDEX idx_expires (expires_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table confirmation_tokens créée/vérifiée")
        
        # Initialiser seats_available pour les offres existantes (migration automatique)
        cur.execute("""
            UPDATE carpool_offers
            SET seats_available = seats
            WHERE seats_available IS NULL AND seats IS NOT NULL
        """)
        updated = cur.rowcount
        if updated > 0:
            print(f"  🔄 {updated} offre(s) mise(s) à jour avec seats_available")
        
        # Insérer l'entreprise de démo Decathlon si elle n'existe pas
        cur.execute("SELECT id FROM companies WHERE name = 'Decathlon' LIMIT 1")
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO companies (name, email, subscription_status, subscription_started_at)
                VALUES ('Decathlon', 'contact@decathlon.fr', 'active', NOW())
            """)
            company_id = cur.lastrowid
            print(f"  ➕ Entreprise Decathlon créée (ID: {company_id})")
            print(f"  ℹ️  Les sites seront créés automatiquement lors des soumissions d'offres")
    
    print("✅ Initialisation des tables carpool terminée")

if __name__ == "__main__":
    init_carpool_tables()
