"""
Calcul de zones de détour basées sur le temps (temporal buffer)
au lieu de la distance géographique.

Principe :
- Échantillonne des points autour de la route
- Pour chaque point : calcule le temps A → point → B via OSRM
- Garde seulement les points où temps_détour ≤ budget_temps
- Génère un polygone (convex hull ou alpha shape) de ces points
"""

import requests
from typing import List, Tuple, Optional, Dict
import json
import math
from scipy.spatial import ConvexHull
import numpy as np


def haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """
    Calcule la distance en mètres entre deux points (lon, lat).
    """
    lon1, lat1 = coord1
    lon2, lat2 = coord2
    
    R = 6371000  # Rayon de la Terre en mètres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


def sample_points_around_route(route_coords: List[List[float]], 
                                 sample_distance_km: float = 2.0,
                                 lateral_distance_km: float = 10.0,
                                 points_per_segment: int = 5) -> List[Tuple[float, float]]:
    """
    Échantillonne des points autour d'une route.
    
    Args:
        route_coords: Liste de [lon, lat] de la route
        sample_distance_km: Distance entre échantillons le long de la route (km)
        lateral_distance_km: Distance latérale d'échantillonnage (km)
        points_per_segment: Nombre de points de chaque côté de la route
    
    Returns:
        Liste de (lon, lat) des points échantillonnés
    """
    sampled_points = []
    
    # Échantillonner le long de la route - échantillonner TOUS les points réduits
    # (pas de pas supplémentaire car on a déjà réduit la route)
    for i in range(0, len(route_coords) - 1):
        lon, lat = route_coords[i]
        
        # Générer des points de chaque côté de la route
        for j in range(-points_per_segment, points_per_segment + 1):
            if j == 0:
                continue  # Skip le point exact sur la route
            
            # Calculer un offset perpendiculaire
            offset_km = (j / points_per_segment) * lateral_distance_km
            
            # Approximation simple : déplacement en longitude/latitude
            # 1 degré de latitude ≈ 111 km
            # 1 degré de longitude ≈ 111 km * cos(latitude)
            lat_offset = (offset_km / 111.0)
            lon_offset = (offset_km / (111.0 * math.cos(math.radians(lat))))
            
            # Alterner gauche/droite
            if i % 2 == 0:
                new_point = (lon + lon_offset, lat + lat_offset)
            else:
                new_point = (lon - lon_offset, lat - lat_offset)
            
            sampled_points.append(new_point)
    
    return sampled_points


def calculate_detour_time_osrm(start: Tuple[float, float], 
                                 via: Tuple[float, float], 
                                 end: Tuple[float, float]) -> Optional[float]:
    """
    Calcule le temps de détour via OSRM : (A → via → B) - (A → B).
    
    Returns:
        Temps de détour en minutes, ou None si erreur
    """
    try:
        # Route avec détour : A → via → B
        detour_url = f"https://router.project-osrm.org/route/v1/driving/{start[0]},{start[1]};{via[0]},{via[1]};{end[0]},{end[1]}?overview=false"
        detour_resp = requests.get(detour_url, timeout=5)
        
        if not detour_resp.ok:
            return None
        
        detour_data = detour_resp.json()
        if detour_data.get('code') != 'Ok' or not detour_data.get('routes'):
            return None
        
        detour_duration = detour_data['routes'][0]['duration'] / 60  # en minutes
        
        # Route directe : A → B
        direct_url = f"https://router.project-osrm.org/route/v1/driving/{start[0]},{start[1]};{end[0]},{end[1]}?overview=false"
        direct_resp = requests.get(direct_url, timeout=5)
        
        if not direct_resp.ok:
            return None
        
        direct_data = direct_resp.json()
        if direct_data.get('code') != 'Ok' or not direct_data.get('routes'):
            return None
        
        direct_duration = direct_data['routes'][0]['duration'] / 60  # en minutes
        
        # Temps de détour = différence
        return detour_duration - direct_duration
        
    except Exception as e:
        print(f"Error calculating detour time: {e}")
        return None



def calculate_detour_time_osrm_fast(start: Tuple[float, float],
                                     via: Tuple[float, float],
                                     end: Tuple[float, float],
                                     direct_duration_min: float) -> Optional[float]:
    """
    Version optimisée : direct_duration déjà calculé, on ne calcule que le détour.
    Économise 1 appel OSRM par point (15 appels pour route directe → 1 seul appel).
    """
    try:
        detour_url = f"https://router.project-osrm.org/route/v1/driving/{start[0]},{start[1]};{via[0]},{via[1]};{end[0]},{end[1]}?overview=false"
        detour_resp = requests.get(detour_url, timeout=5)
        
        if not detour_resp.ok:
            return None
        
        detour_data = detour_resp.json()
        if detour_data.get('code') != 'Ok' or not detour_data.get('routes'):
            return None
        
        detour_duration = detour_data['routes'][0]['duration'] / 60
        return detour_duration - direct_duration_min
        
    except Exception as e:
        return None

def create_temporal_buffer(route_coords: List[List[float]], 
                             max_detour_time_minutes: int = 60,
                             sample_distance_km: float = 5.0,
                             lateral_distance_km: float = 15.0) -> Optional[Dict]:
    """
    Crée une zone de détour basée sur le temps.
    
    Args:
        route_coords: Coordonnées de la route [[lon, lat], ...]
        max_detour_time_minutes: Budget temps maximum en minutes
        sample_distance_km: Distance d'échantillonnage le long de la route
        lateral_distance_km: Distance d'échantillonnage latérale
    
    Returns:
        GeoJSON Polygon de la zone temporelle, ou None si erreur
    """
    if not route_coords or len(route_coords) < 2:
        return None
    
    start = tuple(route_coords[0])
    end = tuple(route_coords[-1])
    
    print(f"🕐 Calculating temporal buffer: {max_detour_time_minutes} min budget")
    
    # Pour les longues routes, sous-échantillonner d'abord
    total_route_points = len(route_coords)
    if total_route_points > 100:
        # Route très longue : prendre 1 point sur 10
        step = total_route_points // 20
        route_coords = route_coords[::step]
        print(f"📏 Long route detected ({total_route_points} points), reduced to {len(route_coords)} points")
    elif total_route_points > 50:
        # Route longue : prendre 1 point sur 5
        step = total_route_points // 30
        route_coords = route_coords[::step]
        print(f"📏 Long route detected ({total_route_points} points), reduced to {len(route_coords)} points")
    
    # Échantillonner des points autour de la route
    sample_points = sample_points_around_route(
        route_coords, 
        sample_distance_km=sample_distance_km,
        lateral_distance_km=lateral_distance_km,
        points_per_segment=3  # 3 points de chaque côté = 6 points par segment
    )
    
    # Limiter à 15 points maximum pour rester dans le timeout (chaque appel OSRM ~2-3s)
    if len(sample_points) > 8:
        import random
        sample_points = random.sample(sample_points, 8)
        print(f"⚠️ Too many sample points, reduced to 15 for performance")
    
    print(f"📍 Sampled {len(sample_points)} points around route")
    
    # 🚀 OPTIMISATION : Calculer route directe UNE SEULE FOIS
    print(f"🔍 Calculating direct route once...")
    direct_url = f"https://router.project-osrm.org/route/v1/driving/{start[0]},{start[1]};{end[0]},{end[1]}?overview=false"
    try:
        direct_resp = requests.get(direct_url, timeout=5)
        if direct_resp.ok:
            direct_data = direct_resp.json()
            if direct_data.get('code') == 'Ok' and direct_data.get('routes'):
                direct_duration_min = direct_data['routes'][0]['duration'] / 60
                print(f"✅ Direct route: {direct_duration_min:.1f} min")
            else:
                direct_duration_min = None
        else:
            direct_duration_min = None
    except Exception as e:
        print(f"❌ Direct route error: {e}")
        direct_duration_min = None
    
    # Filtrer les points selon le temps de détour
    valid_points = []
    
    for i, point in enumerate(sample_points):
        if i % 5 == 0:  # Log tous les 5 points
            print(f"⏱ Processing point {i+1}/{len(sample_points)}...")
        
        # Utiliser fonction optimisée si possible
        if direct_duration_min is not None:
            detour_time = calculate_detour_time_osrm_fast(start, point, end, direct_duration_min)
        else:
            detour_time = calculate_detour_time_osrm(start, point, end)
        
        
        detour_time = calculate_detour_time_osrm(start, point, end)
        
        if detour_time is not None and detour_time <= max_detour_time_minutes:
            valid_points.append(point)
            print(f"  ✅ Point valid: +{detour_time:.1f} min")
        elif detour_time is not None:
            print(f"  ❌ Point rejected: +{detour_time:.1f} min > {max_detour_time_minutes} min")
    
    print(f"✅ Found {len(valid_points)} valid points within time budget")
    
    if len(valid_points) < 3:
        print("⚠️ Not enough valid points to create polygon")
        return None
    
    # Créer un polygone (convex hull) avec les points valides
    try:
        points_array = np.array(valid_points)
        hull = ConvexHull(points_array)
        
        # Extraire les coordonnées du hull
        hull_points = [valid_points[i] for i in hull.vertices]
        hull_points.append(hull_points[0])  # Fermer le polygone
        
        polygon = {
            "type": "Polygon",
            "coordinates": [hull_points]
        }
        
        print(f"🎯 Temporal buffer created with {len(hull_points)} vertices")
        return polygon
        
    except Exception as e:
        print(f"❌ Error creating polygon: {e}")
        # Si trop peu de points ou points coplanaires, créer un buffer simple
        if len(valid_points) >= 3:
            # Créer un polygone simple sans ConvexHull
            # Trier les points par angle depuis le centre
            center_lon = sum(p[0] for p in valid_points) / len(valid_points)
            center_lat = sum(p[1] for p in valid_points) / len(valid_points)
            
            import math
            def angle_from_center(point):
                return math.atan2(point[1] - center_lat, point[0] - center_lon)
            
            sorted_points = sorted(valid_points, key=angle_from_center)
            sorted_points.append(sorted_points[0])  # Fermer le polygone
            
            polygon = {
                "type": "Polygon",
                "coordinates": [sorted_points]
            }
            print(f"🎯 Temporal buffer created (simple polygon) with {len(sorted_points)} vertices")
            return polygon
        
        return None


def calculate_temporal_buffer_batch(route_coords: List[List[float]], 
                                      max_detour_time_minutes: int = 60) -> Optional[Dict]:
    """
    Version optimisée utilisant l'API OSRM table pour des calculs par batch.
    Plus rapide mais nécessite plus de mémoire.
    """
    # TODO: Implémenter avec OSRM Table API pour améliorer les performances
    # http://project-osrm.org/docs/v5.24.0/api/#table-service
    pass


def create_buffer_simple(route_coords: List[List[float]], buffer_km: float) -> Optional[Dict]:
    """
    Crée un buffer géographique qui suit précisément la route.
    Version optimisée : crée des points perpendiculaires de chaque côté de la route.
    
    Args:
        route_coords: Liste de [lon, lat] de la route
        buffer_km: Rayon du buffer en kilomètres
    
    Returns:
        GeoJSON Polygon du buffer, ou None si erreur
    """
    if not route_coords or len(route_coords) < 2:
        return None
    
    try:
        buffer_m = buffer_km * 1000
        
        # Sous-échantillonner modérément pour performance (garder plus de points)
        step = max(1, len(route_coords) // 100)  # Max 100 points (au lieu de 50)
        sampled = route_coords[::step]
        
        # Créer des points perpendiculaires de chaque côté de la route
        left_side = []
        right_side = []
        
        for i in range(len(sampled)):
            lon, lat = sampled[i]
            
            # Calculer la direction de la route à ce point
            if i == 0:
                # Premier point : direction vers le suivant
                next_lon, next_lat = sampled[i + 1]
                dx = next_lon - lon
                dy = next_lat - lat
            elif i == len(sampled) - 1:
                # Dernier point : direction depuis le précédent
                prev_lon, prev_lat = sampled[i - 1]
                dx = lon - prev_lon
                dy = lat - prev_lat
            else:
                # Point intermédiaire : moyenne des directions
                prev_lon, prev_lat = sampled[i - 1]
                next_lon, next_lat = sampled[i + 1]
                dx = next_lon - prev_lon
                dy = next_lat - prev_lat
            
            # Normaliser et créer un vecteur perpendiculaire
            length = math.sqrt(dx*dx + dy*dy)
            if length > 0:
                dx /= length
                dy /= length
            
            # Vecteur perpendiculaire (rotation 90°)
            perp_dx = -dy
            perp_dy = dx
            
            # Convertir buffer en degrés (approximation)
            lat_offset = (buffer_m / 111000) * perp_dy
            lon_offset = (buffer_m / (111000 * math.cos(math.radians(lat)))) * perp_dx
            
            # Points gauche et droite
            left_side.append([lon + lon_offset, lat + lat_offset])
            right_side.append([lon - lon_offset, lat - lat_offset])
        
        # Construire le polygone : gauche (avant→arrière) + droite (arrière→avant)
        polygon_coords = left_side + right_side[::-1] + [left_side[0]]
        
        if len(polygon_coords) < 4:
            return None
        
        return {
            "type": "Polygon",
            "coordinates": [polygon_coords]
        }
        
    except Exception as e:
        print(f"Error creating simple buffer: {e}")
        return None
