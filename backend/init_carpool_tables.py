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
        existing_cols = {row['Field'] for row in cur.fetchall()}
        
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
        existing_cols = {row['Field'] for row in cur.fetchall()}
        
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
                active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                INDEX idx_company_id (company_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table company_sites créée/vérifiée")
        
        # Ajouter colonne active si elle n'existe pas (migration)
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM information_schema.columns 
            WHERE table_schema = DATABASE()
            AND table_name = 'company_sites'
            AND column_name = 'active'
        """)
        if cur.fetchone()['count'] == 0:
            cur.execute("ALTER TABLE company_sites ADD COLUMN active BOOLEAN DEFAULT 1")
            print("  ➕ Colonne 'active' ajoutée à company_sites")
        
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
                time_return TIME DEFAULT NULL,
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
                color_outbound VARCHAR(7) DEFAULT '#7c3aed',
                color_return VARCHAR(7) DEFAULT '#f97316',
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
                pickup_time_outbound TIME DEFAULT NULL,
                dropoff_time_return TIME DEFAULT NULL,
                pickup_order INT DEFAULT 0,
                computed_departure_time DATETIME DEFAULT NULL,
                computed_arrival_home_time DATETIME DEFAULT NULL,
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
        
        # Ajouter la colonne pickup_order si elle n'existe pas (pour les tables existantes)
        try:
            cur.execute("SHOW COLUMNS FROM carpool_reservations_recurrent LIKE 'pickup_order'")
            if not cur.fetchone():
                print("  ➕ Ajout colonne pickup_order à carpool_reservations_recurrent")
                cur.execute("""
                    ALTER TABLE carpool_reservations_recurrent 
                    ADD COLUMN pickup_order INT DEFAULT 0 COMMENT 'Ordre chronologique de passage'
                """)
        except Exception as e:
            print(f"  ⚠️ pickup_order: {e}")
        
        # Créer carpool_reservations_ponctual (mode ponctuel)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS carpool_reservations_ponctual (
                id INT AUTO_INCREMENT PRIMARY KEY,
                offer_id INT NOT NULL,
                passenger_user_id VARCHAR(255) DEFAULT NULL,
                passenger_email VARCHAR(255),
                passenger_name VARCHAR(255),
                passenger_phone VARCHAR(50),
                passengers INT NOT NULL DEFAULT 1,
                date DATE NOT NULL,
                trip_type ENUM('outbound', 'return', 'both') NOT NULL DEFAULT 'outbound',
                meeting_point_coords JSON,
                meeting_point_address VARCHAR(500),
                detour_route JSON,
                detour_time_outbound INT DEFAULT NULL,
                detour_time_return INT DEFAULT NULL,
                pickup_time_outbound TIME DEFAULT NULL,
                dropoff_time_return TIME DEFAULT NULL,
                pickup_order INT DEFAULT 0,
                computed_departure_time DATETIME DEFAULT NULL,
                computed_arrival_home_time DATETIME DEFAULT NULL,
                confirmation_token VARCHAR(64) UNIQUE,
                status ENUM('pending', 'confirmed', 'rejected', 'cancelled') NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at DATETIME,
                FOREIGN KEY (offer_id) REFERENCES carpool_offers(id) ON DELETE CASCADE,
                INDEX idx_offer_id (offer_id),
                INDEX idx_passenger_user_id (passenger_user_id),
                INDEX idx_status (status),
                INDEX idx_date (date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table carpool_reservations_ponctual créée/vérifiée")
        
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
        
        # Données de démo désactivées - les entreprises seront créées via l'interface admin
        # cur.execute("SELECT id FROM companies WHERE name = 'Decathlon' LIMIT 1")
        # if not cur.fetchone():
        #     cur.execute("""
        #         INSERT INTO companies (name, email, subscription_status, subscription_started_at)
        #         VALUES ('Decathlon', 'contact@decathlon.fr', 'active', NOW())
        #     """)
        #     company_id = cur.lastrowid
        #     print(f"  ➕ Entreprise Decathlon créée (ID: {company_id})")
        #     print(f"  ℹ️  Les sites seront créés automatiquement lors des soumissions d'offres")
    
    print("✅ Initialisation des tables carpool terminée")


def init_rse_weekly_tables():
    """Crée les tables RSE hebdomadaire si elles n'existent pas"""
    print("🔄 Initialisation des tables RSE...")
    
    with sql.db_cursor() as cur:
        # Table des utilisateurs RSE
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rse_users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            phone VARCHAR(50),
            departure_address TEXT,
            destination_address TEXT,
            distance_km DECIMAL(10, 2) DEFAULT 0,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_email (email),
            INDEX idx_active (active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table rse_users créée/vérifiée")
        
        # Ajouter la colonne phone si elle n'existe pas
        cur.execute("SHOW COLUMNS FROM rse_users LIKE 'phone'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE rse_users ADD COLUMN phone VARCHAR(50) AFTER email")
            print("  ➕ Colonne phone ajoutée à rse_users")
        
        # Table des entreprises
        cur.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            company_code VARCHAR(20) UNIQUE COMMENT 'Code court pour inscription employés (ex: TECH2026)',
            access_key VARCHAR(64) UNIQUE COMMENT 'Clé API sécurisée',
            magic_token_admin VARCHAR(64) UNIQUE COMMENT 'Token magic link pour accès admin dashboard',
            email_domain VARCHAR(255) COMMENT 'Domaine email pour auto-assignation (ex: techcorp.fr)',
            siren VARCHAR(9),
            contact_email VARCHAR(255) NOT NULL COMMENT 'Email du contact principal',
            contact_name VARCHAR(255) NOT NULL COMMENT 'Nom du contact principal',
            address TEXT,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_name (name),
            INDEX idx_active (active),
            INDEX idx_company_code (company_code),
            INDEX idx_access_key (access_key),
            INDEX idx_magic_token (magic_token_admin)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table companies créée/vérifiée")
        
        # Supprimer ou rendre nullable l'ancienne colonne 'email' si elle existe (migration)
        cur.execute("SHOW COLUMNS FROM companies LIKE 'email'")
        old_email_col = cur.fetchone()
        if old_email_col:
            try:
                # Copier les données de 'email' vers 'contact_email' si contact_email est vide
                cur.execute("""
                    UPDATE companies 
                    SET contact_email = email 
                    WHERE contact_email IS NULL OR contact_email = ''
                """)
                # Rendre la vieille colonne nullable
                cur.execute("ALTER TABLE companies MODIFY COLUMN email VARCHAR(255) NULL DEFAULT NULL")
                print("  ⚠️  Migration: données 'email' copiées vers 'contact_email', ancienne colonne rendue nullable")
            except Exception as e:
                print(f"  ⚠️  Erreur migration colonne 'email': {e}")
        
        # Ajouter les nouvelles colonnes si elles n'existent pas
        columns_to_add = [
            ('company_code', "VARCHAR(20) UNIQUE COMMENT 'Code court pour inscription employés' AFTER name"),
            ('access_key', "VARCHAR(64) UNIQUE COMMENT 'Clé API sécurisée' AFTER company_code"),
            ('magic_token_admin', "VARCHAR(64) UNIQUE COMMENT 'Token magic link pour accès admin dashboard' AFTER access_key"),
            ('email_domain', "VARCHAR(255) COMMENT 'Domaine email pour auto-assignation' AFTER magic_token_admin"),
            ('siren', "VARCHAR(9) AFTER email_domain"),
            ('contact_email', "VARCHAR(255) NOT NULL COMMENT 'Email du contact principal' AFTER siren"),
            ('contact_name', "VARCHAR(255) NOT NULL COMMENT 'Nom du contact principal' AFTER contact_email"),
            ('address', "TEXT AFTER contact_name"),
            ('password_hash', "VARCHAR(255) COMMENT 'Mot de passe hashé pour connexion' AFTER address"),
            ('active', "BOOLEAN DEFAULT TRUE AFTER password_hash")
        ]
        
        for col_name, col_def in columns_to_add:
            cur.execute(f"SHOW COLUMNS FROM companies LIKE '{col_name}'")
            if not cur.fetchone():
                cur.execute(f"ALTER TABLE companies ADD COLUMN {col_name} {col_def}")
                print(f"  ➕ Colonne {col_name} ajoutée à companies")
        
        # Ajouter company_id à rse_users si n'existe pas
        cur.execute("SHOW COLUMNS FROM rse_users LIKE 'company_id'")
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE rse_users 
                ADD COLUMN company_id INT DEFAULT NULL AFTER id,
                ADD INDEX idx_company (company_id),
                ADD FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL
            """)
            print("  ➕ Colonne company_id ajoutée à rse_users")
        
        # Table des habitudes par défaut (référence pour générer les semaines)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rse_user_habits (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL UNIQUE,
            monday VARCHAR(50) DEFAULT 'voiture_solo',
            tuesday VARCHAR(50) DEFAULT 'voiture_solo',
            wednesday VARCHAR(50) DEFAULT 'voiture_solo',
            thursday VARCHAR(50) DEFAULT 'voiture_solo',
            friday VARCHAR(50) DEFAULT 'voiture_solo',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES rse_users(id) ON DELETE CASCADE,
            INDEX idx_user (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table rse_user_habits créée/vérifiée")
        
        # Table des données hebdomadaires
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rse_weekly_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            week_start DATE NOT NULL COMMENT 'Lundi de la semaine',
            week_end DATE NOT NULL COMMENT 'Vendredi de la semaine',
            magic_token VARCHAR(255) NOT NULL UNIQUE,
            total_co2 DECIMAL(10, 2) DEFAULT 0,
            total_distance DECIMAL(10, 2) DEFAULT 0,
            confirmed BOOLEAN DEFAULT FALSE,
            confirmed_at TIMESTAMP NULL,
            email_sent BOOLEAN DEFAULT FALSE,
            email_sent_at TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_user_week (user_id, week_start),
            INDEX idx_token (magic_token),
            INDEX idx_confirmed (confirmed),
            UNIQUE KEY unique_user_week (user_id, week_start)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table rse_weekly_data créée/vérifiée")
        
        # Ajouter la clé étrangère si elle n'existe pas déjà
        cur.execute("""
            SELECT COUNT(*) as fk_count
            FROM information_schema.TABLE_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE()
            AND TABLE_NAME = 'rse_weekly_data'
            AND CONSTRAINT_NAME = 'rse_weekly_data_ibfk_1'
        """)
        if cur.fetchone()['fk_count'] == 0:
            try:
                cur.execute("""
                    ALTER TABLE rse_weekly_data
                    ADD CONSTRAINT rse_weekly_data_ibfk_1
                    FOREIGN KEY (user_id) REFERENCES rse_users(id) ON DELETE CASCADE
                """)
                print("  ➕ Clé étrangère user_id ajoutée à rse_weekly_data")
            except Exception as e:
                print(f"  ⚠️  Clé étrangère déjà existante ou erreur: {e}")
        
        # Table des trajets quotidiens
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rse_daily_transports (
            id INT AUTO_INCREMENT PRIMARY KEY,
            weekly_data_id INT NOT NULL,
            date DATE NOT NULL,
            day_name VARCHAR(20) NOT NULL COMMENT 'Lundi, Mardi, etc.',
            transport_mode VARCHAR(50) DEFAULT 'voiture_solo',
            co2_total DECIMAL(10, 3) DEFAULT 0 COMMENT 'CO2 pour aller-retour (distance × 2)',
            distance_total DECIMAL(10, 2) DEFAULT 0 COMMENT 'Distance aller-retour (distance × 2)',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_weekly_data (weekly_data_id),
            INDEX idx_date (date),
            UNIQUE KEY unique_weekly_date (weekly_data_id, date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table rse_daily_transports créée/vérifiée")
        
        # Ajouter la clé étrangère si elle n'existe pas
        cur.execute("""
            SELECT COUNT(*) as fk_count
            FROM information_schema.TABLE_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE()
            AND TABLE_NAME = 'rse_daily_transports'
            AND CONSTRAINT_NAME = 'rse_daily_transports_ibfk_1'
        """)
        if cur.fetchone()['fk_count'] == 0:
            try:
                cur.execute("""
                    ALTER TABLE rse_daily_transports
                    ADD CONSTRAINT rse_daily_transports_ibfk_1
                    FOREIGN KEY (weekly_data_id) REFERENCES rse_weekly_data(id) ON DELETE CASCADE
                """)
                print("  ➕ Clé étrangère weekly_data_id ajoutée à rse_daily_transports")
            except Exception as e:
                print(f"  ⚠️  Clé étrangère déjà existante ou erreur: {e}")
        
        # Table des facteurs d'émission (référentiel)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rse_emission_factors (
            id INT AUTO_INCREMENT PRIMARY KEY,
            transport_code VARCHAR(50) NOT NULL UNIQUE,
            transport_name VARCHAR(100) NOT NULL,
            icon VARCHAR(10),
            co2_per_km DECIMAL(10, 4) NOT NULL COMMENT 'kg CO2 par km',
            color VARCHAR(20),
            display_order INT DEFAULT 0,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_code (transport_code)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table rse_emission_factors créée/vérifiée")
        
        # Insérer les facteurs d'émission par défaut (ADEME) si pas déjà présents
        cur.execute("SELECT COUNT(*) as count FROM rse_emission_factors")
        if cur.fetchone()['count'] == 0:
            cur.execute("""
            INSERT INTO rse_emission_factors 
            (transport_code, transport_name, icon, co2_per_km, color, display_order) 
            VALUES
            ('voiture_solo', 'Voiture solo', '🚗', 0.2200, '#ef4444', 1),
            ('transports_commun', 'Transports en commun', '🚌', 0.0500, '#f97316', 2),
            ('covoiturage', 'Covoiturage', '🚗👥', 0.0550, '#10b981', 3),
            ('velo', 'Vélo', '🚴', 0.0000, '#22c55e', 4),
            ('train', 'Train', '🚄', 0.0250, '#f59e0b', 5),
            ('teletravail', 'Télétravail', '🏠', 0.0000, '#06b6d4', 6),
            ('marche', 'Marche', '🚶', 0.0000, '#84cc16', 7),
            ('absent', 'Absent', '✖️', 0.0000, '#9ca3af', 8)
            """)
            print("  ➕ Facteurs d'émission ADEME insérés (8 modes de transport)")
        else:
            print("  ℹ️  Facteurs d'émission déjà présents")
        
        # Table de cache pour le géocodage des adresses
        cur.execute("""
        CREATE TABLE IF NOT EXISTS geocoding_cache (
            id INT AUTO_INCREMENT PRIMARY KEY,
            address VARCHAR(500) NOT NULL UNIQUE,
            latitude DECIMAL(10, 8),
            longitude DECIMAL(11, 8),
            geocoded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_address (address)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✅ Table geocoding_cache créée/vérifiée")
    
    print("✅ Initialisation des tables RSE terminée")


if __name__ == "__main__":
    init_carpool_tables()
    init_rse_weekly_tables()
