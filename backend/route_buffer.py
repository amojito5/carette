"""
Création de buffers (zones tampons) autour des itinéraires pour le matching spatial.
"""
import json
from shapely.geometry import LineString, shape
from shapely.ops import unary_union


def create_buffer_from_route(route_geojson, buffer_km=5):
    """
    Crée un buffer (Polygon GeoJSON) autour d'un itinéraire.
    
    Args:
        route_geojson: Dict contenant la geometry (LineString GeoJSON)
        buffer_km: Distance du buffer en kilomètres
        
    Returns:
        Dict: GeoJSON Polygon ou None si erreur
    """
    if not route_geojson or not isinstance(route_geojson, dict):
        return None
        
    geometry = route_geojson.get('geometry')
    if not geometry:
        return None
    
    try:
        # Convertir en objet Shapely
        line = shape(geometry)
        
        # Créer le buffer (distance en degrés approximatifs: 1° ≈ 111km)
        buffer_deg = buffer_km / 111.0
        buffered = line.buffer(buffer_deg)
        
        # Convertir en GeoJSON
        # Shapely retourne un objet géométrique, on utilise __geo_interface__
        geojson = buffered.__geo_interface__
        
        return geojson
        
    except Exception as e:
        print(f"❌ Error creating buffer: {e}")
        return None


def create_buffer_simple(coordinates, buffer_km=5, simplify=True):
    """
    Crée un buffer directement depuis une liste de coordonnées.
    Compatible avec l'ancienne API.
    
    Args:
        coordinates: Liste de [lon, lat] ou [[lon, lat], ...]
        buffer_km: Distance en kilomètres
        simplify: Si True, simplifie la géométrie pour accélérer (recommandé)
        
    Returns:
        Dict: GeoJSON Polygon ou None
    """
    if not coordinates or not isinstance(coordinates, list):
        return None
    
    try:
        # Si trop de points, simplifier pour éviter les timeouts
        if simplify and len(coordinates) > 200:
            # Garder 1 point sur N (max 200 points)
            step = max(1, len(coordinates) // 200)
            simplified_coords = [coordinates[i] for i in range(0, len(coordinates), step)]
            # Toujours garder le dernier point
            if simplified_coords[-1] != coordinates[-1]:
                simplified_coords.append(coordinates[-1])
            print(f"🔧 Simplification: {len(coordinates)} → {len(simplified_coords)} points")
            coordinates = simplified_coords
        
        # Créer une LineString Shapely
        line = LineString(coordinates)
        
        # Buffer (convertir en float pour éviter les erreurs Decimal)
        buffer_deg = float(buffer_km) / 111.0
        buffered = line.buffer(buffer_deg)
        
        return buffered.__geo_interface__
        
    except Exception as e:
        print(f"❌ Error in create_buffer_simple: {e}")
        return None
