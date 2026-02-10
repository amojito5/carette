"""
Carette - Module SQL autonome pour le widget covoiturage
Gestion simplifiée de la base de données MySQL
"""
import pymysql
from contextlib import contextmanager
import os
import sys

# Configuration DB (variables d'environnement - OBLIGATOIRES)
DB_NAME = os.getenv('CARETTE_DB_NAME', 'carette_db')
DB_HOST = os.getenv('CARETTE_DB_HOST', 'localhost')
DB_USER = os.getenv('CARETTE_DB_USER', 'carette_user')
DB_PASSWORD = os.getenv('CARETTE_DB_PASSWORD')
DB_ROOT_PASSWORD = os.getenv('CARETTE_DB_ROOT_PASSWORD')

# Validation: Les mots de passe DOIVENT être définis via variables d'environnement
if not DB_PASSWORD:
    print("❌ ERREUR: Variable d'environnement CARETTE_DB_PASSWORD non définie")
    print("   Créez un fichier .env basé sur .env.example avec un mot de passe sécurisé")
    sys.exit(1)

if not DB_ROOT_PASSWORD:
    print("❌ ERREUR: Variable d'environnement CARETTE_DB_ROOT_PASSWORD non définie")
    print("   Créez un fichier .env basé sur .env.example avec un mot de passe sécurisé")
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
    """Context manager pour exécuter des requêtes SQL avec curseur dictionnaire"""
    conn = get_connection('root' if root else 'app', autocommit=autocommit)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        yield cursor
    finally:
        cursor.close()
        conn.close()


def bootstrap_database():
    """Créer la base de données et l'utilisateur si nécessaire"""
    print("🔧 Bootstrap de la base de données Carette...")
    
    with db_cursor(root=True) as cur:
        # Créer la base
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"  ✓ Base {DB_NAME} créée/vérifiée")
        
        # Créer l'utilisateur
        cur.execute(f"CREATE USER IF NOT EXISTS '{DB_USER}'@'localhost' IDENTIFIED BY '{DB_PASSWORD}'")
        cur.execute(f"GRANT ALL PRIVILEGES ON {DB_NAME}.* TO '{DB_USER}'@'localhost'")
        cur.execute("FLUSH PRIVILEGES")
        print(f"  ✓ Utilisateur {DB_USER} créé/vérifié")


def create_carpool_offers_table():
    """Créer la table des offres de covoiturage"""
    with db_cursor() as cur:
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
                INDEX idx_datetime (datetime),
                INDEX idx_event_id (event_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✓ Table carpool_offers créée/vérifiée")


def create_carpool_reservations_table():
    """Créer la table des réservations"""
    with db_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS carpool_reservations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                offer_id INT NOT NULL,
                passenger_user_id VARCHAR(255) NOT NULL,
                passenger_email VARCHAR(255),
                passenger_name VARCHAR(100),
                passenger_phone VARCHAR(20),
                passengers INT NOT NULL DEFAULT 1,
                trip_type ENUM('outbound', 'return', 'both') NOT NULL DEFAULT 'outbound',
                meeting_point_coords JSON,
                meeting_point_address VARCHAR(500),
                detour_route JSON,
                detour_time INT,
                confirmation_token VARCHAR(64) UNIQUE,
                status ENUM('pending', 'confirmed', 'rejected', 'cancelled') NOT NULL DEFAULT 'pending',
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
                INDEX idx_status (status),
                UNIQUE KEY uniq_user_offer_trip (offer_id, passenger_user_id, trip_type)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✓ Table carpool_reservations créée/vérifiée")


def init_all_tables():
    """Initialiser toutes les tables nécessaires"""
    print("🔄 Initialisation des tables Carette...")
    bootstrap_database()
    create_carpool_offers_table()
    create_carpool_reservations_table()
    print("✅ Toutes les tables sont prêtes!")


if __name__ == '__main__':
    init_all_tables()
