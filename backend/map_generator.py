"""
Générateur de cartes statiques avec itinéraires OSM
"""
import os
from staticmap import StaticMap, Line, CircleMarker
import polyline
import hashlib
from PIL import Image, ImageDraw

def generate_map_image(
    departure_coords: dict,
    destination_coords: dict,
    route_outbound: dict = None,
    route_return: dict = None,
    width: int = 700,
    height: int = 400,
    color_outbound: str = "#7c3aed",
    color_return: str = "#f97316"
) -> str:
    """
    Génère une image de carte avec les itinéraires aller et/ou retour
    
    Args:
        departure_coords: {"lat": float, "lon": float}
        destination_coords: {"lat": float, "lon": float}
        route_outbound: dict avec "geometry" (polyline encodé)
        route_return: dict avec "geometry" (polyline encodé)
        width: largeur de l'image
        height: hauteur de l'image
    
    Returns:
        Chemin relatif de l'image générée (ex: "maps/abc123.png")
    """
    try:
        # Créer la carte avec le style CartoDB Voyager (même que le widget)
        # Note: CartoDB Voyager est plus esthétique que les tuiles OSM standard
        m = StaticMap(
            width, 
            height, 
            url_template='https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png'
        )
        
        # Note: Les couleurs sont maintenant passées en paramètres depuis le widget
        
        # Ajouter l'itinéraire ALLER
        if route_outbound and 'geometry' in route_outbound:
            try:
                geometry = route_outbound['geometry']
                line_coords = None
                
                # Vérifier le format de la geometry
                if isinstance(geometry, str):
                    # Format polyline encodé
                    coords = polyline.decode(geometry)
                    line_coords = [(lon, lat) for lat, lon in coords]
                elif isinstance(geometry, dict) and 'coordinates' in geometry:
                    # Format GeoJSON {type: 'LineString', coordinates: [[lon, lat], ...]}
                    line_coords = [(lon, lat) for lon, lat in geometry['coordinates']]
                
                if line_coords:
                    line = Line(line_coords, color_outbound, 4)
                    m.add_line(line)
                    print(f"✅ Route aller ajoutée: {len(line_coords)} points")
                else:
                    print(f"⚠️ Format geometry aller non reconnu: {type(geometry)}")
            except Exception as e:
                print(f"❌ Erreur décodage route aller: {e}")
                import traceback
                traceback.print_exc()
        
        # Ajouter l'itinéraire RETOUR (ligne continue comme l'aller)
        if route_return and 'geometry' in route_return:
            try:
                geometry = route_return['geometry']
                line_coords = None
                
                # Vérifier le format de la geometry
                if isinstance(geometry, str):
                    # Format polyline encodé
                    coords = polyline.decode(geometry)
                    line_coords = [(lon, lat) for lat, lon in coords]
                elif isinstance(geometry, dict) and 'coordinates' in geometry:
                    # Format GeoJSON {type: 'LineString', coordinates: [[lon, lat], ...]}
                    line_coords = [(lon, lat) for lon, lat in geometry['coordinates']]
                
                if line_coords:
                    line = Line(line_coords, color_return, 4)
                    m.add_line(line)
                    print(f"✅ Route retour ajoutée: {len(line_coords)} points")
                else:
                    print(f"⚠️ Format geometry retour non reconnu: {type(geometry)}")
            except Exception as e:
                print(f"❌ Erreur décodage route retour: {e}")
                import traceback
                traceback.print_exc()
        
        # Ajouter les marqueurs de départ et d'arrivée
        dep_marker = CircleMarker(
            (departure_coords['lon'], departure_coords['lat']),
            color_outbound,
            12
        )
        m.add_marker(dep_marker)
        
        dest_marker = CircleMarker(
            (destination_coords['lon'], destination_coords['lat']),
            'red',
            12
        )
        m.add_marker(dest_marker)
        
        # Générer un nom de fichier unique basé sur les coordonnées
        coords_str = f"{departure_coords['lat']},{departure_coords['lon']}-{destination_coords['lat']},{destination_coords['lon']}"
        filename = hashlib.md5(coords_str.encode()).hexdigest() + '.png'
        
        # Créer le dossier maps s'il n'existe pas
        maps_dir = '/home/ubuntu/projects/carette/static/maps'
        os.makedirs(maps_dir, exist_ok=True)
        
        # Chemin complet
        filepath = os.path.join(maps_dir, filename)
        
        # Rendre l'image
        image = m.render()
        image.save(filepath)
        
        print(f"✅ Carte générée: {filepath}")
        
        # Retourner le chemin relatif
        return f"maps/{filename}"
        
    except Exception as e:
        print(f"❌ Erreur génération carte: {e}")
        import traceback
        traceback.print_exc()
        return None
