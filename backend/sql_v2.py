"""
Carette - Module SQL Simplifié v2
Gestion BDD sans comptes utilisateurs (email/téléphone uniquement)
"""
import pymysql
from contextlib import contextmanager
import os
import sys

# Configuration DB
DB_NAME = os.getenv('CARETTE_DB_NAME', 'carette_db')
DB_HOST = os.getenv('CARETTE_DB_HOST', 'localhost')
DB_USER = os.getenv('CARETTE_DB_USER', 'carette_user')
DB_PASSWORD = os.getenv('CARETTE_DB_PASSWORD')
DB_ROOT_PASSWORD = os.getenv('CARETTE_DB_ROOT_PASSWORD')

# Validation mots de passe
if not DB_PASSWORD:
    print("❌ ERREUR: Variable d'environnement CARETTE_DB_PASSWORD non définie")
    sys.exit(1)

if not DB_ROOT_PASSWORD:
    print("❌ ERREUR: Variable d'environnement CARETTE_DB_ROOT_PASSWORD non définie")
    sys.exit(1)


def get_connection(user='app', autocommit=True):
    """Obtenir une connexion MySQL"""
    if user == 'root':
        return pymysql.connect(
            host=DB_HOST,
            user='root',
            password=DB_ROOT_PASSWORD,
            autocommit=autocommit,
            charset='utf8mb4'
        )
    else:
        return pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            autocommit=autocommit,
            charset='utf8mb4'
        )


@contextmanager
def db_cursor(root=False, autocommit=True):
    """Context manager pour exécuter des requêtes SQL"""
    conn = get_connection('root' if root else 'app', autocommit=autocommit)
    cursor = conn.cursor()
    try:
        yield cursor
    finally:
        cursor.close()
        conn.close()


def bootstrap_database():
    """Créer la base de données et l'utilisateur"""
    print("🔧 Bootstrap de la base de données Carette...")
    
    with db_cursor(root=True) as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"  ✓ Base {DB_NAME} créée/vérifiée")
        
        cur.execute(f"CREATE USER IF NOT EXISTS '{DB_USER}'@'localhost' IDENTIFIED BY '{DB_PASSWORD}'")
        cur.execute(f"GRANT ALL PRIVILEGES ON {DB_NAME}.* TO '{DB_USER}'@'localhost'")
        cur.execute("FLUSH PRIVILEGES")
        print(f"  ✓ Utilisateur {DB_USER} créé/vérifié")


def create_simplified_tables():
    """Créer les tables simplifiées v2"""
    print("🔄 Création des tables simplifiées v2...")
    
    with db_cursor() as cur:
        # Table offres simplifiée
        cur.execute("""
            CREATE TABLE IF NOT EXISTS carpool_offers_v2 (
                id INT AUTO_INCREMENT PRIMARY KEY,
                
                driver_email VARCHAR(255) NOT NULL,
                driver_phone VARCHAR(20) NOT NULL,
                driver_name VARCHAR(100),
                
                departure VARCHAR(255) NOT NULL,
                destination VARCHAR(255) NOT NULL,
                departure_coords JSON,
                destination_coords JSON,
                datetime DATETIME NOT NULL,
                seats_available INT NOT NULL DEFAULT 1,
                
                -- Colonnes compatibles avec le widget Lemur
                details JSON DEFAULT NULL,
                route_outbound JSON DEFAULT NULL,
                route_return JSON DEFAULT NULL,
                route_geometry JSON,
                detour_zone JSON,
                detour_zone_outbound JSON DEFAULT NULL,
                detour_zone_return JSON DEFAULT NULL,
                max_detour_km INT DEFAULT 10,
                max_detour_time INT DEFAULT 15,
                accept_passengers_on_route TINYINT(1) DEFAULT 1,
                seats_outbound INT DEFAULT NULL,
                seats_return INT DEFAULT NULL,
                return_datetime DATETIME DEFAULT NULL,
                page_url VARCHAR(500) DEFAULT NULL,
                
                event_id VARCHAR(255),
                event_name VARCHAR(255),
                event_location VARCHAR(255),
                event_date DATE,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                status ENUM('active', 'full', 'expired', 'cancelled') DEFAULT 'active',
                
                INDEX idx_datetime (datetime),
                INDEX idx_event_id (event_id),
                INDEX idx_status (status),
                INDEX idx_driver_email (driver_email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✓ Table carpool_offers_v2 créée")
        
        # Table réservations simplifiée
        cur.execute("""
            CREATE TABLE IF NOT EXISTS carpool_reservations_v2 (
                id INT AUTO_INCREMENT PRIMARY KEY,
                offer_id INT NOT NULL,
                
                passenger_email VARCHAR(255) NOT NULL,
                passenger_phone VARCHAR(20) NOT NULL,
                passenger_name VARCHAR(100),
                passengers_count INT DEFAULT 1,
                
                status ENUM('pending', 'confirmed', 'rejected', 'cancelled') DEFAULT 'pending',
                
                payment_status ENUM('none', 'simulated', 'paid') DEFAULT 'simulated',
                payment_amount DECIMAL(5,2) DEFAULT 1.00,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at DATETIME,
                cancelled_at DATETIME,
                
                FOREIGN KEY (offer_id) REFERENCES carpool_offers_v2(id) ON DELETE CASCADE,
                INDEX idx_offer_id (offer_id),
                INDEX idx_passenger_email (passenger_email),
                INDEX idx_status (status),
                UNIQUE KEY uniq_passenger_offer (offer_id, passenger_email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✓ Table carpool_reservations_v2 créée")
        
        # Table tokens de confirmation
        cur.execute("""
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
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✓ Table confirmation_tokens créée")


def init_simplified_db():
    """Initialiser la base simplifiée complète"""
    print("🚀 Initialisation Carette v2 (Simplifié)...")
    bootstrap_database()
    create_simplified_tables()
    print("✅ Base de données v2 prête !")


if __name__ == '__main__':
    init_simplified_db()
