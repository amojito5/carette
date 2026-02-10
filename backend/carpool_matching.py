"""
Module de matching covoiturage pour les emails hebdomadaires RSE.

Trouve des suggestions de covoiturage entre employés d'une même entreprise
basées sur leurs trajets domicile-travail et un détour maximum de 20 minutes.
"""

import json
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import requests

logger = logging.getLogger(__name__)

# Facteur CO2 voiture solo (kg/km)
CO2_VOITURE_SOLO = 0.220


def get_coords_from_cache(address: str, cur) -> Optional[Tuple[float, float]]:
    """
    Récupère les coordonnées d'une adresse depuis le cache de géocodage.
    
    Returns:
        Tuple (lon, lat) ou None si non trouvé
    """
    if not address:
        return None
    
    cur.execute("""
        SELECT latitude, longitude 
        FROM geocoding_cache 
        WHERE address = %s
    """, (address,))
    
    result = cur.fetchone()
    if result and result['latitude'] and result['longitude']:
        return (float(result['longitude']), float(result['latitude']))
    
    return None


def geocode_and_cache(address: str, cur) -> Optional[Tuple[float, float]]:
    """
    Géocode une adresse via Nominatim et la met en cache.
    
    Returns:
        Tuple (lon, lat) ou None si échec
    """
    if not address:
        return None
    
    # Vérifier le cache d'abord
    cached = get_coords_from_cache(address, cur)
    if cached:
        return cached
    
    try:
        # Appel Nominatim
        url = f"https://nominatim.openstreetmap.org/search"
        params = {
            'q': address,
            'format': 'json',
            'limit': 1,
            'countrycodes': 'fr'
        }
        headers = {'User-Agent': 'Carette-RSE/1.0'}
        
        response = requests.get(url, params=params, headers=headers, timeout=5)
        if response.ok and response.json():
            result = response.json()[0]
            lat = float(result['lat'])
            lon = float(result['lon'])
            
            # Mettre en cache
            cur.execute("""
                INSERT INTO geocoding_cache (address, latitude, longitude)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE latitude = %s, longitude = %s
            """, (address, lat, lon, lat, lon))
            
            return (lon, lat)
    except Exception as e:
        logger.warning(f"Geocoding failed for {address}: {e}")
    
    return None


def get_route_duration_osrm(start: Tuple[float, float], end: Tuple[float, float]) -> Optional[float]:
    """
    Calcule la durée du trajet direct via OSRM.
    
    Returns:
        Durée en minutes ou None si erreur
    """
    try:
        url = f"https://router.project-osrm.org/route/v1/driving/{start[0]},{start[1]};{end[0]},{end[1]}?overview=false"
        response = requests.get(url, timeout=5)
        
        if response.ok:
            data = response.json()
            if data.get('code') == 'Ok' and data.get('routes'):
                return data['routes'][0]['duration'] / 60  # en minutes
    except Exception as e:
        logger.warning(f"OSRM error: {e}")
    
    return None


def calculate_detour_duration(
    driver_home: Tuple[float, float],
    passenger_home: Tuple[float, float],
    destination: Tuple[float, float]
) -> Optional[Dict]:
    """
    Calcule le détour pour récupérer un passager.
    
    Trajet avec détour: driver_home → passenger_home → destination
    Trajet direct: driver_home → destination
    
    Returns:
        Dict avec {detour_minutes, total_duration, direct_duration} ou None
    """
    try:
        # Trajet direct
        direct_url = f"https://router.project-osrm.org/route/v1/driving/{driver_home[0]},{driver_home[1]};{destination[0]},{destination[1]}?overview=false"
        direct_resp = requests.get(direct_url, timeout=5)
        
        if not direct_resp.ok:
            return None
        
        direct_data = direct_resp.json()
        if direct_data.get('code') != 'Ok' or not direct_data.get('routes'):
            return None
        
        direct_duration = direct_data['routes'][0]['duration'] / 60
        
        # Trajet avec détour
        detour_url = f"https://router.project-osrm.org/route/v1/driving/{driver_home[0]},{driver_home[1]};{passenger_home[0]},{passenger_home[1]};{destination[0]},{destination[1]}?overview=false"
        detour_resp = requests.get(detour_url, timeout=5)
        
        if not detour_resp.ok:
            return None
        
        detour_data = detour_resp.json()
        if detour_data.get('code') != 'Ok' or not detour_data.get('routes'):
            return None
        
        total_duration = detour_data['routes'][0]['duration'] / 60
        detour_minutes = total_duration - direct_duration
        
        return {
            'detour_minutes': detour_minutes,
            'total_duration': total_duration,
            'direct_duration': direct_duration
        }
        
    except Exception as e:
        logger.warning(f"Error calculating detour: {e}")
        return None


def find_carpool_matches_for_company(company_id: int, cur, max_detour_minutes: int = 20) -> List[Dict]:
    """
    Trouve les suggestions de covoiturage pour une entreprise.
    
    Pour chaque utilisateur qui utilise la voiture au moins 1 jour/semaine,
    cherche les collègues qui pourraient être récupérés avec un détour < max_detour.
    
    Returns:
        Liste de matches: {driver, passenger, detour_minutes, co2_saved, common_days}
    """
    matches = []
    
    # Récupérer tous les utilisateurs actifs avec leurs habitudes et adresses
    cur.execute("""
        SELECT 
            u.id, u.name, u.email, u.departure_address, u.distance_km,
            h.monday, h.tuesday, h.wednesday, h.thursday, h.friday,
            cs.site_coords
        FROM rse_users u
        JOIN rse_user_habits h ON u.id = h.user_id
        LEFT JOIN company_sites cs ON u.company_id = cs.company_id AND cs.active = 1
        WHERE u.company_id = %s AND u.active = 1
    """, (company_id,))
    
    users = cur.fetchall()
    
    if len(users) < 2:
        return []  # Pas assez d'utilisateurs pour matcher
    
    # Parser les coordonnées du site (destination commune)
    destination_coords = None
    for user in users:
        if user['site_coords']:
            try:
                coords = json.loads(user['site_coords']) if isinstance(user['site_coords'], str) else user['site_coords']
                destination_coords = (float(coords['lon']), float(coords['lat']))
                break
            except:
                pass
    
    if not destination_coords:
        logger.warning(f"No site coordinates for company {company_id}")
        return []
    
    # Identifier les jours en voiture pour chaque utilisateur
    car_days = {}
    for user in users:
        days = []
        for day, key in [('monday', 'Lundi'), ('tuesday', 'Mardi'), ('wednesday', 'Mercredi'), 
                         ('thursday', 'Jeudi'), ('friday', 'Vendredi')]:
            if user[day] == 'voiture_solo':
                days.append(key)
        car_days[user['id']] = days
    
    # Géocoder les adresses de départ
    user_coords = {}
    for user in users:
        coords = geocode_and_cache(user['departure_address'], cur)
        if coords:
            user_coords[user['id']] = coords
    
    # Pour chaque conducteur potentiel (au moins 1 jour en voiture)
    for driver in users:
        driver_id = driver['id']
        driver_car_days = car_days.get(driver_id, [])
        
        if not driver_car_days or driver_id not in user_coords:
            continue
        
        driver_coords = user_coords[driver_id]
        
        # Chercher des passagers potentiels
        for passenger in users:
            if passenger['id'] == driver_id:
                continue
            
            if passenger['id'] not in user_coords:
                continue
            
            passenger_coords = user_coords[passenger['id']]
            passenger_car_days = car_days.get(passenger['id'], [])
            
            # Trouver les jours en commun où le conducteur est en voiture
            # et le passager est en voiture (pourrait passer passager)
            common_days = [d for d in driver_car_days if d in passenger_car_days]
            
            if not common_days:
                continue
            
            # Calculer le détour
            detour_info = calculate_detour_duration(
                driver_coords,
                passenger_coords,
                destination_coords
            )
            
            if not detour_info:
                continue
            
            detour_minutes = detour_info['detour_minutes']
            
            # Vérifier si le détour est acceptable
            if detour_minutes <= max_detour_minutes and detour_minutes >= 0:
                # Calculer le CO2 économisé si covoiturage
                # Le passager n'utilise plus sa voiture solo → économie de son trajet
                passenger_distance = float(passenger['distance_km'] or 30)
                co2_saved_per_day = passenger_distance * 2 * CO2_VOITURE_SOLO  # Aller-retour
                co2_saved_week = co2_saved_per_day * len(common_days)
                
                matches.append({
                    'driver_id': driver_id,
                    'driver_name': driver['name'],
                    'driver_email': driver['email'],
                    'passenger_id': passenger['id'],
                    'passenger_name': passenger['name'],
                    'passenger_email': passenger['email'],
                    'passenger_address': passenger['departure_address'],
                    'detour_minutes': round(detour_minutes, 1),
                    'common_days': common_days,
                    'co2_saved_per_day': round(co2_saved_per_day, 2),
                    'co2_saved_week': round(co2_saved_week, 2)
                })
    
    # Trier par détour le plus court
    matches.sort(key=lambda x: x['detour_minutes'])
    
    return matches


def get_carpool_suggestions_for_user(user_id: int, company_id: int, cur, max_detour_minutes: int = 20) -> List[Dict]:
    """
    Trouve les suggestions de covoiturage pour un utilisateur spécifique.
    
    Retourne:
    - Les personnes que cet utilisateur pourrait transporter (s'il est en voiture)
    - Les personnes qui pourraient le transporter (s'il est passager)
    
    Returns:
        Liste de suggestions triées par pertinence
    """
    all_matches = find_carpool_matches_for_company(company_id, cur, max_detour_minutes)
    
    # Filtrer pour cet utilisateur
    user_matches = []
    
    for match in all_matches:
        if match['driver_id'] == user_id:
            # Cet utilisateur est conducteur
            user_matches.append({
                'role': 'driver',
                'match_name': match['passenger_name'],
                'match_email': match['passenger_email'],
                'match_address': match['passenger_address'],
                'detour_minutes': match['detour_minutes'],
                'common_days': match['common_days'],
                'co2_saved_week': match['co2_saved_week']
            })
        elif match['passenger_id'] == user_id:
            # Cet utilisateur pourrait être passager
            user_matches.append({
                'role': 'passenger',
                'match_name': match['driver_name'],
                'match_email': match['driver_email'],
                'match_address': None,  # On ne révèle pas l'adresse du conducteur
                'detour_minutes': match['detour_minutes'],
                'common_days': match['common_days'],
                'co2_saved_week': match['co2_saved_week']
            })
    
    # Limiter à 2 suggestions maximum
    return user_matches[:2]


def generate_carpool_email_section(suggestions: List[Dict]) -> str:
    """
    Génère la section HTML "Et si on covoiturait ?" pour l'email hebdomadaire.
    
    Returns:
        HTML string ou chaîne vide si pas de suggestions
    """
    if not suggestions:
        return ""
    
    # Prendre la meilleure suggestion
    best = suggestions[0]
    
    if best['role'] == 'driver':
        # L'utilisateur pourrait conduire
        title = "🚗 Vous pourriez transporter"
        action = f"Récupérer <strong>{best['match_name']}</strong> sur votre trajet"
        detail = f"+{int(best['detour_minutes'])} min de détour"
        benefit = f"💚 {best['co2_saved_week']:.1f} kg CO₂ économisés/semaine"
    else:
        # L'utilisateur pourrait être passager
        title = "🤝 On peut vous emmener !"
        action = f"<strong>{best['match_name']}</strong> passe près de chez vous"
        detail = f"Seulement +{int(best['detour_minutes'])} min pour lui/elle"
        benefit = f"💚 {best['co2_saved_week']:.1f} kg CO₂ économisés/semaine"
    
    # Jours en commun
    days_str = ", ".join(best['common_days'])
    
    html = f"""
    <!-- Section Covoiturage -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:20px;">
        <tr>
            <td style="background:linear-gradient(135deg, #10b981 0%, #059669 100%);border-radius:12px;padding:24px;">
                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td>
                            <div style="font-size:18px;font-weight:800;color:white;margin-bottom:12px;">
                                {title}
                            </div>
                            <div style="font-size:15px;color:rgba(255,255,255,0.95);margin-bottom:8px;">
                                {action}
                            </div>
                            <div style="display:inline-block;background:rgba(255,255,255,0.2);padding:6px 12px;border-radius:20px;font-size:13px;color:white;margin-bottom:12px;">
                                ⏱️ {detail}
                            </div>
                            <div style="font-size:14px;color:rgba(255,255,255,0.9);margin-bottom:4px;">
                                📅 Jours en commun : <strong>{days_str}</strong>
                            </div>
                            <div style="font-size:14px;color:#bbf7d0;font-weight:600;">
                                {benefit}
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding-top:16px;">
                            <a href="mailto:{best['match_email']}?subject=Covoiturage%20-%20On%20fait%20route%20ensemble%20%3F" 
                               style="display:inline-block;background:white;color:#059669;text-decoration:none;padding:12px 24px;border-radius:8px;font-weight:700;font-size:14px;">
                                ✉️ Contacter {best['match_name'].split()[0]}
                            </a>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
    """
    
    return html


if __name__ == "__main__":
    # Test du module
    import sql
    
    print("🔍 Test du module de matching covoiturage...")
    
    with sql.db_cursor() as cur:
        # Test pour l'entreprise 1
        matches = find_carpool_matches_for_company(1, cur, max_detour_minutes=20)
        
        print(f"\n📊 {len(matches)} matches trouvés pour l'entreprise 1:")
        for m in matches[:5]:
            print(f"  🚗 {m['driver_name']} → {m['passenger_name']}: +{m['detour_minutes']:.1f} min ({', '.join(m['common_days'])})")
            print(f"     💚 {m['co2_saved_week']:.1f} kg CO₂/semaine économisés")
