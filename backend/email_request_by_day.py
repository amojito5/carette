"""
Template d'email de demande de covoiturage avec sections par jour
"""
from datetime import timedelta, datetime, time as datetime_time
import urllib.parse
import math
import json


def normalize_time_for_sort(time_value):
    """Normalise une valeur temporelle en string HH:MM pour le tri"""
    if time_value is None:
        return '00:00'
    if isinstance(time_value, str):
        return time_value
    if isinstance(time_value, datetime_time):
        return time_value.strftime('%H:%M')
    if isinstance(time_value, timedelta):
        total_seconds = int(time_value.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f'{hours:02d}:{minutes:02d}'
    return '00:00'


def haversine_distance(coord1: tuple, coord2: tuple) -> float:
    """Calcule la distance en km entre deux points (lon, lat)"""
    lon1, lat1 = coord1
    lon2, lat2 = coord2
    
    R = 6371  # Rayon de la Terre en km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


def sort_pickups_geographically(start_coords: tuple, pickups: list, end_coords: tuple, direction: str = 'outbound') -> list:
    """
    Trie les pickups dans l'ordre géographique optimal entre start et end en utilisant OSRM.
    direction: 'outbound' (domicile → bureau) ou 'return' (bureau → domicile)
    
    Returns: liste de pickups triée
    """
    if not pickups or not start_coords or not end_coords:
        return pickups
    
    # Pour chaque pickup, calculer le temps de trajet depuis le départ via OSRM
    import requests
    pickups_with_time = []
    
    for pickup in pickups:
        coords = pickup.get('coords')
        if not coords or len(coords) != 2:
            # Si pas de coords valides, mettre à la fin
            pickups_with_time.append((pickup, float('inf')))
            continue
        
        try:
            # Calculer le temps départ → pickup via OSRM
            url = f"https://router.project-osrm.org/route/v1/driving/{start_coords[0]},{start_coords[1]};{coords[0]},{coords[1]}?overview=false"
            response = requests.get(url, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 'Ok' and data.get('routes'):
                    duration_seconds = data['routes'][0]['duration']
                    pickups_with_time.append((pickup, duration_seconds))
                else:
                    # Si OSRM échoue, utiliser haversine comme fallback
                    dist = haversine_distance(start_coords, coords)
                    pickups_with_time.append((pickup, dist * 1000))  # Multiplier pour que ce soit après les temps réels
            else:
                dist = haversine_distance(start_coords, coords)
                pickups_with_time.append((pickup, dist * 1000))
        except Exception:
            # En cas d'erreur, utiliser haversine
            dist = haversine_distance(start_coords, coords)
            pickups_with_time.append((pickup, dist * 1000))
    
    # Trier par temps croissant
    sorted_pickups = sorted(pickups_with_time, key=lambda x: x[1])
    
    return [p[0] for p in sorted_pickups]


def create_navigation_links(origin: str, destination: str, color: str = "#10b981") -> str:
    """
    Crée des boutons pour Google Maps et Waze
    """
    # URL encode des adresses
    origin_encoded = urllib.parse.quote(origin)
    destination_encoded = urllib.parse.quote(destination)
    
    # Google Maps URL
    google_maps_url = f"https://www.google.com/maps/dir/?api=1&origin={origin_encoded}&destination={destination_encoded}&travelmode=driving"
    
    # Waze URL
    waze_url = f"https://waze.com/ul?ll=&navigate=yes&q={destination_encoded}"
    
    return f"""
    <div style="text-align:center;margin-top:16px;padding-top:16px;border-top:1px solid #e5e7eb;">
        <div style="font-size:12px;color:#666;margin-bottom:10px;font-weight:600;">📱 Navigation</div>
        <a href="{google_maps_url}" target="_blank" style="display:inline-block;background:#4285f4;color:#fff;text-decoration:none;padding:10px 20px;border-radius:8px;font-weight:600;font-size:13px;margin:4px;box-shadow:0 2px 4px rgba(66,133,244,0.3);">
            🗺️ Google Maps
        </a>
        <a href="{waze_url}" target="_blank" style="display:inline-block;background:#33ccff;color:#fff;text-decoration:none;padding:10px 20px;border-radius:8px;font-weight:600;font-size:13px;margin:4px;box-shadow:0 2px 4px rgba(51,204,255,0.3);">
            🚗 Waze
        </a>
    </div>
    """

def create_dual_navigation_links(origin: str, destination: str, color_outbound: str = "#7c3aed", color_return: str = "#f97316") -> str:
    """
    Encarts Aller et Retour avec Google Maps et Waze, style similaire à "Vos collègues".
    """
    origin_encoded = urllib.parse.quote(origin)
    destination_encoded = urllib.parse.quote(destination)

    gm_outbound = f"https://www.google.com/maps/dir/?api=1&origin={origin_encoded}&destination={destination_encoded}&travelmode=driving"
    gm_return = f"https://www.google.com/maps/dir/?api=1&origin={destination_encoded}&destination={origin_encoded}&travelmode=driving"

    waze_outbound = f"https://waze.com/ul?ll=&navigate=yes&q={destination_encoded}"
    waze_return = f"https://waze.com/ul?ll=&navigate=yes&q={origin_encoded}"

    return f"""
    <div style="border:1px solid #dee2e6;border-radius:8px;padding:20px;background:#fafafa;">
        <div style="font-size:16px;font-weight:700;color:#111;margin-bottom:12px;">📱 Navigation</div>
        <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start;">
            <div style="flex:1;min-width:220px;">
                <div style="font-size:14px;font-weight:700;color:{color_outbound};margin-bottom:8px;">➡️ Aller</div>
                <a href="{gm_outbound}" target="_blank" style="display:inline-block;background:#4285f4;color:#fff;text-decoration:none;padding:10px 20px;border-radius:8px;font-weight:600;font-size:13px;margin:4px;box-shadow:0 2px 4px rgba(66,133,244,0.3);">🗺️ Google Maps</a>
                <a href="{waze_outbound}" target="_blank" style="display:inline-block;background:#33ccff;color:#fff;text-decoration:none;padding:10px 20px;border-radius:8px;font-weight:600;font-size:13px;margin:4px;box-shadow:0 2px 4px rgba(51,204,255,0.3);">🚗 Waze</a>
            </div>
            <div style="flex:1;min-width:220px;">
                <div style="font-size:14px;font-weight:700;color:{color_return};margin-bottom:8px;">⬅️ Retour</div>
                <a href="{gm_return}" target="_blank" style="display:inline-block;background:#4285f4;color:#fff;text-decoration:none;padding:10px 20px;border-radius:8px;font-weight:600;font-size:13px;margin:4px;box-shadow:0 2px 4px rgba(66,133,244,0.3);">🗺️ Google Maps</a>
                <a href="{waze_return}" target="_blank" style="display:inline-block;background:#33ccff;color:#fff;text-decoration:none;padding:10px 20px;border-radius:8px;font-weight:600;font-size:13px;margin:4px;box-shadow:0 2px 4px rgba(51,204,255,0.3);">🚗 Waze</a>
            </div>
        </div>
    </div>
    """

def create_compact_nav_buttons(origin: str, destination: str, waypoints: list = None) -> str:
    """
    Crée des boutons compacts Google Maps et Waze pour un itinéraire avec waypoints optionnels
    waypoints: liste de dictionnaires avec 'address' et optionnellement 'coords'
    """
    origin_encoded = urllib.parse.quote(origin)
    destination_encoded = urllib.parse.quote(destination)
    
    # Construire l'URL Google Maps avec waypoints
    if waypoints:
        # Google Maps supporte les waypoints multiples avec le format: waypoints=addr1|addr2|addr3
        waypoints_str = "|".join([urllib.parse.quote(wp['address']) for wp in waypoints])
        gm_url = f"https://www.google.com/maps/dir/?api=1&origin={origin_encoded}&destination={destination_encoded}&waypoints={waypoints_str}&travelmode=driving"
    else:
        gm_url = f"https://www.google.com/maps/dir/?api=1&origin={origin_encoded}&destination={destination_encoded}&travelmode=driving"
    
    # Waze ne supporte pas les waypoints multiples, on pointe vers la première étape ou la destination
    if waypoints and len(waypoints) > 0:
        first_waypoint_encoded = urllib.parse.quote(waypoints[0]['address'])
        waze_url = f"https://waze.com/ul?ll=&navigate=yes&q={first_waypoint_encoded}"
    else:
        waze_url = f"https://waze.com/ul?ll=&navigate=yes&q={destination_encoded}"
    
    return f"""
    <div style="text-align:center;margin-top:12px;padding-top:12px;border-top:1px solid #e5e7eb;">
        <a href="{gm_url}" target="_blank" style="display:inline-block;background:#4285f4;color:#fff;text-decoration:none;padding:8px 16px;border-radius:6px;font-weight:600;font-size:12px;margin:4px;box-shadow:0 2px 4px rgba(66,133,244,0.2);">🗺️ Google Maps</a>
        <a href="{waze_url}" target="_blank" style="display:inline-block;background:#33ccff;color:#fff;text-decoration:none;padding:8px 16px;border-radius:6px;font-weight:600;font-size:12px;margin:4px;box-shadow:0 2px 4px rgba(51,204,255,0.2);">🚗 Waze</a>
    </div>
    """

def format_time(time_value):
    """Convertit timedelta ou time en string HH:MM"""
    if isinstance(time_value, timedelta):
        total_seconds = int(time_value.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    elif hasattr(time_value, 'strftime'):
        return time_value.strftime('%H:%M')
    return '—'

def generate_request_email_by_day(
    offer_data: dict,
    passenger_name: str,
    passenger_email: str,
    passenger_phone: str,
    pickup_address: str,
    pickup_coords: list,
    days_requested: list,
    days_with_existing_pickup: set,
    detour_outbound: float,
    detour_return: float,
    pickup_time_outbound,
    dropoff_time_return,
    arrival_home_time,
    new_departure_time,
    existing_passengers: list = None,
    reservation_id: int = None,
    confirmation_token: str = None,
    base_url: str = None,
    email_type: str = 'request'
):
    """
    Email de demande avec une section par jour
    - Jours demandés par le passager : comparaison avant/après
    - Autres jours : itinéraire actuel seulement
    """
    from datetime import datetime, timedelta
    import urllib.parse
    
    # Titre et intro selon le type d'email
    if email_type == 'rejected':
        subject = f"❌ Demande refusée - {passenger_name}"
        intro_text = f"Vous avez refusé la demande de <strong>{passenger_name}</strong>."
        header_title = "❌ Demande refusée"
        header_color = "#ef4444"
    else:
        subject = f"🚗 Nouvelle demande de covoiturage de {passenger_name}"
        intro_text = f"Bonjour {offer_data['driver_name']}, <strong>{passenger_name}</strong> souhaite rejoindre votre covoiturage."
        header_title = "🚗 Nouvelle demande de covoiturage"
        header_color = offer_data.get('color_outbound', '#7c3aed')
    
    # Initialiser existing_passengers si None
    if existing_passengers is None:
        existing_passengers = []
    
    # Couleurs
    color_outbound = offer_data.get('color_outbound', '#7c3aed')
    color_return = offer_data.get('color_return', '#f97316')
    
    if color_outbound and len(color_outbound) == 9:
        color_outbound = color_outbound[:7]
    if color_return and len(color_return) == 9:
        color_return = color_return[:7]
    
    # Boutons d'action
    action_buttons = ""
    if email_type == 'request' and reservation_id and confirmation_token and base_url:
        accept_url = f"{base_url}/api/v2/reservations/recurrent/{reservation_id}/accept?token={confirmation_token}"
        reject_url = f"{base_url}/api/v2/reservations/recurrent/{reservation_id}/reject?token={confirmation_token}"
        action_buttons = f"""
        <div style="text-align:center;padding:28px;background:#fff;border-radius:16px;box-shadow:0 4px 16px rgba(0,0,0,0.12);margin-bottom:24px;border:2px solid {color_outbound};">
            <div style="font-size:16px;font-weight:700;color:#333;margin-bottom:16px;">Votre décision</div>
            <a href="{accept_url}" target="_blank" style="display:inline-block;background:#10b981;color:#fff;text-decoration:none;padding:16px 40px;border-radius:12px;font-weight:700;font-size:16px;box-shadow:0 4px 12px rgba(16,185,129,0.3);margin:8px;transition:transform 0.2s;">
                ✅ Accepter la demande
            </a>
            <a href="{reject_url}" target="_blank" style="display:inline-block;background:#ef4444;color:#fff;text-decoration:none;padding:16px 40px;border-radius:12px;font-weight:700;font-size:16px;box-shadow:0 4px 12px rgba(239,68,68,0.3);margin:8px;transition:transform 0.2s;">
                ❌ Refuser la demande
            </a>
        </div>
        """
    
    # Calculer heures de base
    original_departure_time = None
    original_arrival_home_time = None
    
    try:
        # Calculer le trajet direct sans passagers pour avoir les heures "originales"
        # On ne peut PAS utiliser route_outbound/route_return car ils contiennent les passagers existants
        import requests
        
        departure_coords = offer_data.get('departure_coords')
        destination_coords = offer_data.get('destination_coords')
        
        if departure_coords and destination_coords:
            # Trajet ALLER direct : home → bureau
            coord_str_outbound = f"{departure_coords[0]},{departure_coords[1]};{destination_coords[0]},{destination_coords[1]}"
            osrm_url_outbound = f"https://router.project-osrm.org/route/v1/driving/{coord_str_outbound}?overview=false"
            resp_out = requests.get(osrm_url_outbound, timeout=5)
            
            if resp_out.status_code == 200:
                data_out = resp_out.json()
                if data_out.get('routes'):
                    duration_direct_outbound_min = int(data_out['routes'][0]['duration'] / 60)
                    # Convertir recurrent_time en datetime si c'est un timedelta
                    if isinstance(offer_data['recurrent_time'], timedelta):
                        total_sec = int(offer_data['recurrent_time'].total_seconds())
                        hours = total_sec // 3600
                        minutes = (total_sec % 3600) // 60
                        recurrent_time = datetime.min.time().replace(hour=hours, minute=minutes)
                    else:
                        recurrent_time = offer_data['recurrent_time']
                    
                    arrival_outbound = datetime.combine(datetime.today(), recurrent_time)
                    departure_outbound = arrival_outbound - timedelta(minutes=duration_direct_outbound_min)
                    original_departure_time = departure_outbound.time()
            
            # Trajet RETOUR direct : bureau → home
            coord_str_return = f"{destination_coords[0]},{destination_coords[1]};{departure_coords[0]},{departure_coords[1]}"
            osrm_url_return = f"https://router.project-osrm.org/route/v1/driving/{coord_str_return}?overview=false"
            resp_ret = requests.get(osrm_url_return, timeout=5)
            
            if resp_ret.status_code == 200:
                data_ret = resp_ret.json()
                if data_ret.get('routes'):
                    duration_direct_return_min = int(data_ret['routes'][0]['duration'] / 60)
                    # Convertir time_return en datetime si c'est un timedelta
                    if isinstance(offer_data['time_return'], timedelta):
                        total_sec = int(offer_data['time_return'].total_seconds())
                        hours = total_sec // 3600
                        minutes = (total_sec % 3600) // 60
                        time_return = datetime.min.time().replace(hour=hours, minute=minutes)
                    else:
                        time_return = offer_data['time_return']
                    
                    departure_return_dt = datetime.combine(datetime.today(), time_return)
                    arrival_home_dt = departure_return_dt + timedelta(minutes=duration_direct_return_min)
                    original_arrival_home_time = arrival_home_dt.time()
    except Exception as e:
        pass
    
    # Jours
    day_names = {
        'monday': ('Lundi', 'Lun'),
        'tuesday': ('Mardi', 'Mar'),
        'wednesday': ('Mercredi', 'Mer'),
        'thursday': ('Jeudi', 'Jeu'),
        'friday': ('Vendredi', 'Ven'),
        'saturday': ('Samedi', 'Sam'),
        'sunday': ('Dimanche', 'Dim')
    }
    
    max_detour = offer_data.get('max_detour_time', 15)
    
    # Fonction barre de progression
    def progress_bar(used: int, max_val: int) -> str:
        remaining = max_val - used
        percentage = (remaining / max_val * 100) if max_val > 0 else 100
        if percentage >= 66:
            color = '#10b981'
        elif percentage >= 33:
            color = '#f59e0b'
        else:
            color = '#ef4444'
        
        return f'''
        <div style="margin-top:12px;">
            <div style="font-size:12px;color:#666;margin-bottom:6px;text-align:center;">
                ⏱️ Budget détour : <strong style="color:{color};">{remaining} min</strong> / {max_val} min restants
            </div>
            <div style="background:#e5e7eb;height:8px;border-radius:4px;overflow:hidden;box-shadow:inset 0 1px 3px rgba(0,0,0,0.1);">
                <div style="background:{color};height:100%;width:{percentage}%;transition:width 0.3s;box-shadow:0 0 4px {color};"></div>
            </div>
        </div>
        '''
    
    # Générer sections par jour
    days_sections = ""
    
    for day_en, (day_full, day_abbr) in day_names.items():
        # Vérifier si l'offre est active ce jour (support 2 formats)
        if 'days' in offer_data:
            is_offer_active = offer_data['days'].get(day_en, False)
        else:
            is_offer_active = offer_data.get(day_en, False)
        
        if not is_offer_active:
            continue
        
        passenger_requests_day = day_en in days_requested
        
        # Filtrer les passagers existants pour ce jour
        existing_for_day = [p for p in existing_passengers if p['days'].get(day_en, False)]
        
        # Séparer passagers existants par localisation (départ vs autres pickups)
        existing_at_departure = []
        existing_other_pickups = []
        
        for ep in existing_for_day:
            meeting_addr = ep.get('meeting_point_address', '').lower().strip()
            departure_addr = offer_data['departure'].lower().strip()
            
            # Grouper UNIQUEMENT par adresse, pas par détour
            if meeting_addr == departure_addr:
                existing_at_departure.append(ep)
            else:
                existing_other_pickups.append(ep)
        
        # Construire l'état ACTUEL (avec passagers existants uniquement) pour ALLER
        existing_passengers_aller_html = ""
        for ep in existing_at_departure:
            existing_passengers_aller_html += f'''
                                    <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                                        <div style="width:20px;height:20px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                                        <span style="font-size:13px;color:#111;font-weight:600;margin-left:8px;">{ep['passenger_name']}</span>
                                    </div>'''
        
        # Grouper les autres pickups par adresse pour éviter les doublons
        pickups_by_address = {}
        for ep in existing_other_pickups:
            addr = ep.get('meeting_point_address', '').lower().strip()
            if addr not in pickups_by_address:
                pickups_by_address[addr] = []
            pickups_by_address[addr].append(ep)
        
        existing_other_pickups_aller_html = ""
        # Trier les pickups par heure de passage
        sorted_pickups_by_address = sorted(pickups_by_address.items(), key=lambda x: normalize_time_for_sort(x[1][0].get('pickup_time_outbound')))
        for addr, passengers_at_addr in sorted_pickups_by_address:
            first = passengers_at_addr[0]
            # Utiliser l'heure de pickup du premier passager (elles devraient être identiques pour la même adresse)
            pickup_time_str = format_time(first.get('pickup_time_outbound')) if first.get('pickup_time_outbound') else '—'
            passengers_list = ""
            for ep in passengers_at_addr:
                passengers_list += f'''
                                    <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                                        <div style="width:20px;height:20px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                                        <span style="font-size:13px;color:#111;font-weight:600;margin-left:8px;">{ep['passenger_name']}</span>
                                    </div>'''
            
            existing_other_pickups_aller_html += f'''
                            <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                                <div style="display:flex;flex-direction:column;align-items:center;">
                                    <div style="width:32px;height:32px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">📍</div>
                                    <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                                </div>
                                <div style="flex:1;margin-left:16px;">
                                    <div style="font-weight:600;color:#444;font-size:13px;">Pickup</div>
                                    <div style="font-weight:700;color:{color_outbound};font-size:16px;">{pickup_time_str}</div>
                                    <div style="color:#666;font-size:11px;margin-top:2px;">{first['meeting_point_address']}</div>{passengers_list}
                                </div>
                            </div>'''        # Séparer passagers existants par localisation pour le RETOUR (arrivée vs autres dropoffs)
        existing_at_arrival = []
        existing_other_dropoffs = []
        
        for ep in existing_for_day:
            meeting_addr = ep.get('meeting_point_address', '').lower().strip()
            departure_addr = offer_data['departure'].lower().strip()
            
            print(f"🔍 Passager '{ep['passenger_name']}': meeting='{meeting_addr}', depart='{departure_addr}', match={meeting_addr == departure_addr}")
            
            # UNIQUEMENT l'adresse détermine si le passager est déposé au domicile ou ailleurs
            # Le détour ne doit PAS être un critère - un passager sur la route est quand même déposé à SON adresse
            if meeting_addr == departure_addr:
                existing_at_arrival.append(ep)
                print(f"  → Classé en 'arrivée au domicile'")
            else:
                existing_other_dropoffs.append(ep)
                print(f"  → Classé en 'dropoff intermédiaire'")
        
        existing_passengers_retour_html = ""
        for ep in existing_at_arrival:
            existing_passengers_retour_html += f'''
                                    <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                                        <div style="width:20px;height:20px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                                        <span style="font-size:13px;color:#111;font-weight:600;margin-left:8px;">{ep['passenger_name']}</span>
                                    </div>'''
        
        # Grouper les dropoffs par adresse pour éviter les doublons
        dropoffs_by_address = {}
        for ep in existing_other_dropoffs:
            addr = ep.get('meeting_point_address', '').lower().strip()
            if addr not in dropoffs_by_address:
                dropoffs_by_address[addr] = []
            dropoffs_by_address[addr].append(ep)
        
        existing_other_dropoffs_retour_html = ""
        # Trier les dropoffs par heure de passage
        sorted_dropoffs_by_address = sorted(dropoffs_by_address.items(), key=lambda x: normalize_time_for_sort(x[1][0].get('dropoff_time_return')))
        for addr, passengers_at_addr in sorted_dropoffs_by_address:
            first = passengers_at_addr[0]
            # Utiliser l'heure de dropoff du premier passager
            dropoff_time_str = format_time(first.get('dropoff_time_return')) if first.get('dropoff_time_return') else '—'
            passengers_list = ""
            for ep in passengers_at_addr:
                passengers_list += f'''
                                    <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                                        <div style="width:20px;height:20px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                                        <span style="font-size:13px;color:#111;font-weight:600;margin-left:8px;">{ep['passenger_name']}</span>
                                    </div>'''
            
            existing_other_dropoffs_retour_html += f'''
                            <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                                <div style="display:flex;flex-direction:column;align-items:center;">
                                    <div style="width:32px;height:32px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">📍</div>
                                    <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                                </div>
                                <div style="flex:1;margin-left:16px;">
                                    <div style="font-weight:600;color:#444;font-size:13px;">Dropoff</div>
                                    <div style="font-weight:700;color:{color_return};font-size:16px;">{dropoff_time_str}</div>
                                    <div style="color:#666;font-size:11px;margin-top:2px;">{first['meeting_point_address']}</div>{passengers_list}
                                </div>
                            </div>'''
        
        # Déterminer si le pickup est à l'adresse de départ (COMPARAISON D'ADRESSE, pas de détour)
        pickup_addr_normalized = pickup_address.lower().strip()
        departure_addr_normalized = offer_data['departure'].lower().strip()
        is_pickup_at_departure = (pickup_addr_normalized == departure_addr_normalized)
        is_dropoff_at_departure = (pickup_addr_normalized == departure_addr_normalized)  # Même adresse pour retour
        
        # Préparer le contenu conditionnel pour l'aller
        if is_pickup_at_departure:
            # Pas de nouveau pickup - le nouveau passager monte au départ
            # Waypoints pour l'itinéraire "Avec" = pickups existants uniquement
            waypoints_avec_aller = [{'address': ep['meeting_point_address'], 'coords': tuple(json.loads(ep['meeting_point_coords'])) if ep.get('meeting_point_coords') else None} for ep in existing_other_pickups]
            
            # Construire la liste des passagers au départ (existants + nouveau)
            passengers_list_html = ""
            for ep in existing_at_departure:
                passengers_list_html += f'''
                                    <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                                        <div style="width:20px;height:20px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                                        <span style="font-size:13px;color:#111;font-weight:600;margin-left:8px;">{ep['passenger_name']}</span>
                                    </div>'''
            # Ajouter le nouveau passager
            passengers_list_html += f'''
                                    <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                                        <div style="width:20px;height:20px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                                        <span style="font-size:13px;color:#111;font-weight:600;margin-left:8px;">{passenger_name}</span>
                                    </div>'''
            
            aller_avec_content = f'''
                            <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                                <div style="display:flex;flex-direction:column;align-items:center;">
                                    <div style="width:32px;height:32px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏠</div>
                                    <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                                </div>
                                <div style="flex:1;margin-left:16px;">
                                    <div style="font-weight:600;color:#444;font-size:13px;">Départ</div>
                                    <div style="font-weight:700;color:#111;font-size:16px;">{format_time(original_departure_time) if original_departure_time else '—'}</div>
                                    <div style="color:#666;font-size:11px;margin-top:2px;">{offer_data['departure']}</div>{passengers_list_html}
                                </div>
                            </div>{existing_other_pickups_aller_html}
                            <div style="display:flex;align-items:flex-start;">
                                <div style="display:flex;flex-direction:column;align-items:center;">
                                    <div style="width:32px;height:32px;border-radius:50%;background:#10b981;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏢</div>
                                </div>
                                <div style="flex:1;margin-left:16px;">
                                    <div style="font-weight:600;color:#444;font-size:13px;">Arrivée</div>
                                    <div style="font-weight:700;color:#111;font-size:16px;">{format_time(offer_data['recurrent_time'])}</div>
                                    <div style="color:#666;font-size:11px;margin-top:2px;">{offer_data['destination']}</div>
                                </div>
                            </div>'''
        else:
            # Construire la liste des passagers au départ (existants seulement)
            passengers_at_start_html = ""
            for ep in existing_at_departure:
                passengers_at_start_html += f'''
                                    <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                                        <div style="width:20px;height:20px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                                        <span style="font-size:13px;color:#111;font-weight:600;margin-left:8px;">{ep['passenger_name']}</span>
                                    </div>'''
            
            # Grouper les pickups existants par adresse
            pickups_by_addr = {}
            for ep in existing_other_pickups:
                addr = ep.get('meeting_point_address', '').lower().strip()
                if addr not in pickups_by_addr:
                    pickups_by_addr[addr] = []
                pickups_by_addr[addr].append(ep)
            
            # AJOUTER le nouveau passager dans le dictionnaire AVANT le tri
            if pickup_addr_normalized not in pickups_by_addr:
                pickups_by_addr[pickup_addr_normalized] = []
            pickups_by_addr[pickup_addr_normalized].append({
                'passenger_name': passenger_name,
                'meeting_point_address': pickup_address,
                'pickup_time_outbound': pickup_time_outbound,
                'is_new': True  # Marqueur pour identifier le nouveau passager
            })
            
            # Construire les pickups TOUS groupés par adresse
            other_pickups_html = ""
            # Trier TOUS les pickups (existants + nouveau) par heure de passage
            sorted_pickups = sorted(pickups_by_addr.items(), key=lambda x: normalize_time_for_sort(x[1][0].get('pickup_time_outbound')))
            for addr, passengers_at_addr in sorted_pickups:
                first = passengers_at_addr[0]
                # Utiliser l'heure du pickup
                pickup_time_str = format_time(first.get('pickup_time_outbound')) if first.get('pickup_time_outbound') else '—'
                passengers_list = ""
                for ep in passengers_at_addr:
                    passengers_list += f'''
                                    <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                                        <div style="width:20px;height:20px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                                        <span style="font-size:13px;color:#111;font-weight:600;margin-left:8px;">{ep['passenger_name']}</span>
                                    </div>'''
                
                other_pickups_html += f'''
                            <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                                <div style="display:flex;flex-direction:column;align-items:center;">
                                    <div style="width:32px;height:32px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">📍</div>
                                    <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                                </div>
                                <div style="flex:1;margin-left:16px;">
                                    <div style="font-weight:600;color:#444;font-size:13px;">Pickup</div>
                                    <div style="font-weight:700;color:{color_outbound};font-size:16px;">{pickup_time_str}</div>
                                    <div style="color:#666;font-size:11px;margin-top:2px;">{first['meeting_point_address']}</div>{passengers_list}
                                </div>
                            </div>'''
            
            aller_avec_content = f'''
                            <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                                <div style="display:flex;flex-direction:column;align-items:center;">
                                    <div style="width:32px;height:32px;border-radius:50%;background:#fbbf24;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(251,191,36,0.3);">🏠</div>
                                    <div style="width:2px;height:40px;background:#fde68a;margin-top:4px;"></div>
                                </div>
                                <div style="flex:1;margin-left:16px;">
                                    <div style="font-weight:600;color:#92400e;font-size:13px;">⚠️ Nouveau départ</div>
                                    <div style="font-weight:700;color:#78350f;font-size:16px;">{format_time(new_departure_time) if new_departure_time else '—'}</div>
                                    <div style="color:#666;font-size:11px;margin-top:2px;">{offer_data['departure']}</div>
                                    <div style="color:#92400e;font-size:11px;background:#fef3c7;padding:4px 8px;border-radius:4px;display:inline-block;margin-top:4px;">+{int(detour_outbound)} min plus tôt</div>{passengers_at_start_html}
                                </div>
                            </div>{other_pickups_html}
                            <div style="display:flex;align-items:flex-start;">
                                <div style="display:flex;flex-direction:column;align-items:center;">
                                    <div style="width:32px;height:32px;border-radius:50%;background:#10b981;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏢</div>
                                </div>
                                <div style="flex:1;margin-left:16px;">
                                    <div style="font-weight:600;color:#444;font-size:13px;">Arrivée</div>
                                    <div style="font-weight:700;color:#111;font-size:16px;">{format_time(offer_data['recurrent_time'])}</div>
                                    <div style="color:#666;font-size:11px;margin-top:2px;">{offer_data['destination']}</div>
                                </div>
                            </div>
                            {progress_bar(int(detour_outbound), max_detour)}'''
            
            # Préparer les waypoints pour "Avec passager" - TOUS les pickups triés géographiquement
            # Le nouveau passager est déjà inclus dans pickups_by_addr qui a été trié
            all_pickups_aller = []
            
            # Reconstruire à partir du dictionnaire trié (qui inclut déjà le nouveau passager)
            for addr, passengers_at_addr in sorted_pickups:
                first = passengers_at_addr[0]
                coords = None
                if first.get('meeting_point_coords'):
                    try:
                        coords = tuple(json.loads(first['meeting_point_coords']))
                    except:
                        pass
                # Utiliser pickup_coords si c'est le nouveau passager
                if first.get('is_new'):
                    coords = pickup_coords if pickup_coords else None
                    
                all_pickups_aller.append({
                    'address': first.get('meeting_point_address', pickup_address),
                    'coords': coords
                })
            
            waypoints_avec_aller = all_pickups_aller
        
        # Préparer le contenu conditionnel pour le retour
        # Séparer passagers existants par localisation (arrivée vs autres dropoffs)
        existing_at_arrival = []
        existing_other_dropoffs = []
        
        for ep in existing_for_day:
            meeting_addr = ep.get('meeting_point_address', '').lower().strip()
            departure_addr = offer_data['departure'].lower().strip()
            
            # UNIQUEMENT l'adresse détermine si le passager est déposé au domicile ou ailleurs
            # Le détour ne doit PAS être un critère - un passager sur la route est quand même déposé à SON adresse
            if meeting_addr == departure_addr:
                existing_at_arrival.append(ep)
            else:
                existing_other_dropoffs.append(ep)
        
        if is_dropoff_at_departure:
            # Pas de nouveau dropoff - le nouveau passager descend au domicile
            # Waypoints pour l'itinéraire "Avec" retour = dropoffs existants uniquement
            waypoints_avec_retour = [{'address': ep['meeting_point_address'], 'coords': tuple(json.loads(ep['meeting_point_coords'])) if ep.get('meeting_point_coords') else None} for ep in existing_other_dropoffs]
            
            # Construire la liste des passagers à l'arrivée (existants + nouveau)
            passengers_list_html = ""
            for ep in existing_at_arrival:
                passengers_list_html += f'''
                                    <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                                        <div style="width:20px;height:20px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                                        <span style="font-size:13px;color:#111;font-weight:600;margin-left:8px;">{ep['passenger_name']}</span>
                                    </div>'''
            # Ajouter le nouveau passager
            passengers_list_html += f'''
                                    <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                                        <div style="width:20px;height:20px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                                        <span style="font-size:13px;color:#111;font-weight:600;margin-left:8px;">{passenger_name}</span>
                                    </div>'''
            
            retour_avec_content = f'''
                            <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                                <div style="display:flex;flex-direction:column;align-items:center;">
                                    <div style="width:32px;height:32px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏢</div>
                                    <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                                </div>
                                <div style="flex:1;margin-left:16px;">
                                    <div style="font-weight:600;color:#444;font-size:13px;">Départ</div>
                                    <div style="font-weight:700;color:#111;font-size:16px;">{format_time(offer_data['time_return'])}</div>
                                    <div style="color:#666;font-size:11px;margin-top:2px;">{offer_data['destination']}</div>
                                </div>
                            </div>{existing_other_dropoffs_retour_html}
                            <div style="display:flex;align-items:flex-start;">
                                <div style="display:flex;flex-direction:column;align-items:center;">
                                    <div style="width:32px;height:32px;border-radius:50%;background:#10b981;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏠</div>
                                </div>
                                <div style="flex:1;margin-left:16px;">
                                    <div style="font-weight:600;color:#444;font-size:13px;">Arrivée</div>
                                    <div style="font-weight:700;color:#111;font-size:16px;">{format_time(original_arrival_home_time) if original_arrival_home_time else '—'}</div>
                                    <div style="color:#666;font-size:11px;margin-top:2px;">{offer_data['departure']}</div>{passengers_list_html}
                                </div>
                            </div>'''
        else:
            # Grouper les dropoffs existants par adresse
            dropoffs_by_addr = {}
            for ep in existing_other_dropoffs:
                addr = ep.get('meeting_point_address', '').lower().strip()
                if addr not in dropoffs_by_addr:
                    dropoffs_by_addr[addr] = []
                dropoffs_by_addr[addr].append(ep)
            
            # AJOUTER le nouveau passager dans le dictionnaire AVANT le tri (sauf s'il arrive au domicile)
            is_dropoff_at_home = pickup_addr_normalized == offer_data['departure'].lower().strip()
            if not is_dropoff_at_home:
                if pickup_addr_normalized not in dropoffs_by_addr:
                    dropoffs_by_addr[pickup_addr_normalized] = []
                dropoffs_by_addr[pickup_addr_normalized].append({
                    'passenger_name': passenger_name,
                    'meeting_point_address': pickup_address,
                    'dropoff_time_return': dropoff_time_return,
                    'is_new': True
                })
            
            # Construire TOUS les dropoffs groupés par adresse
            other_dropoffs_html = ""
            # Trier TOUS les dropoffs (existants + nouveau) par heure de passage
            sorted_dropoffs = sorted(dropoffs_by_addr.items(), key=lambda x: normalize_time_for_sort(x[1][0].get('dropoff_time_return')))
            for addr, passengers_at_addr in sorted_dropoffs:
                first = passengers_at_addr[0]
                # Utiliser l'heure du dropoff
                dropoff_time_str = format_time(first.get('dropoff_time_return')) if first.get('dropoff_time_return') else '—'
                passengers_list = ""
                for ep in passengers_at_addr:
                    passengers_list += f'''
                                    <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                                        <div style="width:20px;height:20px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                                        <span style="font-size:13px;color:#111;font-weight:600;margin-left:8px;">{ep['passenger_name']}</span>
                                    </div>'''
                
                other_dropoffs_html += f'''
                            <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                                <div style="display:flex;flex-direction:column;align-items:center;">
                                    <div style="width:32px;height:32px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">📍</div>
                                    <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                                </div>
                                <div style="flex:1;margin-left:16px;">
                                    <div style="font-weight:600;color:#444;font-size:13px;">Dropoff</div>
                                    <div style="font-weight:700;color:{color_return};font-size:16px;">{dropoff_time_str}</div>
                                    <div style="color:#666;font-size:11px;margin-top:2px;">{first['meeting_point_address']}</div>{passengers_list}
                                </div>
                            </div>'''
            
            # Construire la liste des passagers à l'arrivée au domicile (existants + nouveau si applicable)
            passengers_at_end_html = ""
            for ep in existing_at_arrival:
                passengers_at_end_html += f'''
                                    <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                                        <div style="width:20px;height:20px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                                        <span style="font-size:13px;color:#111;font-weight:600;margin-left:8px;">{ep['passenger_name']}</span>
                                    </div>'''
            
            # Si le nouveau passager arrive au domicile, l'ajouter
            if is_dropoff_at_home:
                passengers_at_end_html += f'''
                                    <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                                        <div style="width:20px;height:20px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                                        <span style="font-size:13px;color:#111;font-weight:600;margin-left:8px;">{passenger_name}</span>
                                    </div>'''
            
            retour_avec_content = f'''
                            <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                                <div style="display:flex;flex-direction:column;align-items:center;">
                                    <div style="width:32px;height:32px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏢</div>
                                    <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                                </div>
                                <div style="flex:1;margin-left:16px;">
                                    <div style="font-weight:600;color:#444;font-size:13px;">Départ</div>
                                    <div style="font-weight:700;color:#111;font-size:16px;">{format_time(offer_data['time_return'])}</div>
                                    <div style="color:#666;font-size:11px;margin-top:2px;">{offer_data['destination']}</div>
                                </div>
                            </div>{other_dropoffs_html}
                            <div style="display:flex;align-items:flex-start;">
                                <div style="display:flex;flex-direction:column;align-items:center;">
                                    <div style="width:32px;height:32px;border-radius:50%;background:#fbbf24;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(251,191,36,0.3);">🏠</div>
                                </div>
                                <div style="flex:1;margin-left:16px;">
                                    <div style="font-weight:600;color:#92400e;font-size:13px;">⚠️ Nouvelle arrivée</div>
                                    <div style="font-weight:700;color:#78350f;font-size:16px;">{format_time(arrival_home_time) if arrival_home_time else '—'}</div>
                                    <div style="color:#666;font-size:11px;margin-top:2px;">{offer_data['departure']}</div>
                                    <div style="color:#92400e;font-size:11px;background:#fef3c7;padding:4px 8px;border-radius:4px;display:inline-block;margin-top:4px;">+{int(detour_return)} min plus tard</div>{passengers_at_end_html}
                                </div>
                            </div>
                            {progress_bar(int(detour_return), max_detour)}'''
            
            # Préparer les waypoints pour "Avec passager" - TOUS les dropoffs triés géographiquement
            # Le nouveau passager est déjà inclus dans dropoffs_by_addr qui a été trié
            all_dropoffs_retour = []
            
            # Reconstruire à partir du dictionnaire trié (qui inclut déjà le nouveau passager)
            for addr, passengers_at_addr in sorted_dropoffs:
                first = passengers_at_addr[0]
                coords = None
                if first.get('meeting_point_coords'):
                    try:
                        coords = tuple(json.loads(first['meeting_point_coords']))
                    except:
                        pass
                # Utiliser pickup_coords si c'est le nouveau passager
                if first.get('is_new'):
                    coords = pickup_coords if pickup_coords else None
                    
                all_dropoffs_retour.append({
                    'address': first.get('meeting_point_address', pickup_address),
                    'coords': coords
                })
            
            waypoints_avec_retour = all_dropoffs_retour
        
        # Afficher la section "Avec passager" pour tous les jours demandés
        # Même si le pickup existe déjà, on montre le passager ajouté à l'étape existante
        if passenger_requests_day:
            # Initialiser les waypoints si pas déjà fait
            if 'waypoints_avec_aller' not in locals():
                waypoints_avec_aller = []
            if 'waypoints_avec_retour' not in locals():
                waypoints_avec_retour = []
            
            # AVEC PASSAGER - Comparaison avant/après
            days_sections += f'''
            <div style="background:#fff;border-radius:16px;box-shadow:0 4px 16px rgba(0,0,0,0.1);padding:24px;margin-bottom:24px;border:2px solid #fbbf24;">
                <div style="display:inline-block;background:linear-gradient(135deg, #fbbf24, #f59e0b);color:#000;padding:10px 24px;border-radius:20px;font-size:15px;font-weight:700;margin-bottom:20px;box-shadow:0 4px 12px rgba(251,191,36,0.4);">
                    ⚠️ {day_full.upper()}
                    <span style="margin-left:8px;background:rgba(0,0,0,0.15);color:#000;padding:4px 10px;border-radius:12px;font-size:13px;">
                        Avec {passenger_name}
                    </span>
                </div>
                
                <div style="display:flex;gap:20px;flex-wrap:wrap;">
                    <!-- ALLER -->
                    <div style="flex:1;min-width:280px;">
                        <div style="background:linear-gradient(to bottom, #ffffff, #fafafa);border-radius:12px;padding:20px;border:1px solid #e5e7eb;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:16px;">
                            <div style="font-size:14px;font-weight:700;color:{color_outbound};margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid {color_outbound};">➡️ ALLER - Actuel</div>
                            <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                                <div style="display:flex;flex-direction:column;align-items:center;">
                                    <div style="width:32px;height:32px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏠</div>
                                    <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                                </div>
                                <div style="flex:1;margin-left:16px;">
                                    <div style="font-weight:600;color:#444;font-size:13px;">Départ</div>
                                    <div style="font-weight:700;color:#111;font-size:16px;">{format_time(original_departure_time) if original_departure_time else '—'}</div>
                                    <div style="color:#666;font-size:11px;margin-top:2px;">{offer_data['departure']}</div>{existing_passengers_aller_html}
                                </div>
                            </div>{existing_other_pickups_aller_html}
                            <div style="display:flex;align-items:flex-start;">
                                <div style="display:flex;flex-direction:column;align-items:center;">
                                    <div style="width:32px;height:32px;border-radius:50%;background:#10b981;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏢</div>
                                </div>
                                <div style="flex:1;margin-left:16px;">
                                    <div style="font-weight:600;color:#444;font-size:13px;">Arrivée</div>
                                    <div style="font-weight:700;color:#111;font-size:16px;">{format_time(offer_data['recurrent_time'])}</div>
                                    <div style="color:#666;font-size:11px;margin-top:2px;">{offer_data['destination']}</div>
                                </div>
                            </div>
                            {create_compact_nav_buttons(offer_data['departure'], offer_data['destination'])}
                        </div>
                        
                        <div style="background:linear-gradient(to bottom, #fffbeb, #fef3c7);border-radius:12px;padding:20px;border:2px solid #fbbf24;box-shadow:0 2px 8px rgba(251,191,36,0.2);">
                            <div style="font-size:14px;font-weight:700;color:#92400e;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid #fbbf24;">➡️ ALLER - Avec {passenger_name}</div>
                            {aller_avec_content}
                            {create_compact_nav_buttons(offer_data['departure'], offer_data['destination'], waypoints_avec_aller)}
                        </div>
                    </div>
                    
                    <!-- RETOUR -->
                    <div style="flex:1;min-width:280px;">
                        <div style="background:linear-gradient(to bottom, #ffffff, #fafafa);border-radius:12px;padding:20px;border:1px solid #e5e7eb;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:16px;">
                            <div style="font-size:14px;font-weight:700;color:{color_return};margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid {color_return};">⬅️ RETOUR - Actuel</div>
                            <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                                <div style="display:flex;flex-direction:column;align-items:center;">
                                    <div style="width:32px;height:32px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏢</div>
                                    <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                                </div>
                                <div style="flex:1;margin-left:16px;">
                                    <div style="font-weight:600;color:#444;font-size:13px;">Départ</div>
                                    <div style="font-weight:700;color:#111;font-size:16px;">{format_time(offer_data['time_return'])}</div>
                                    <div style="color:#666;font-size:11px;margin-top:2px;">{offer_data['destination']}</div>
                                </div>
                            </div>{existing_other_dropoffs_retour_html}
                            <div style="display:flex;align-items:flex-start;">
                                <div style="display:flex;flex-direction:column;align-items:center;">
                                    <div style="width:32px;height:32px;border-radius:50%;background:#10b981;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏠</div>
                                </div>
                                <div style="flex:1;margin-left:16px;">
                                    <div style="font-weight:600;color:#444;font-size:13px;">Arrivée</div>
                                    <div style="font-weight:700;color:#111;font-size:16px;">{format_time(original_arrival_home_time) if original_arrival_home_time else '—'}</div>
                                    <div style="color:#666;font-size:11px;margin-top:2px;">{offer_data['departure']}</div>{existing_passengers_retour_html}
                                </div>
                            </div>
                            {create_compact_nav_buttons(offer_data['destination'], offer_data['departure'])}
                        </div>
                        
                        <div style="background:linear-gradient(to bottom, #fffbeb, #fef3c7);border-radius:12px;padding:20px;border:2px solid #fbbf24;box-shadow:0 2px 8px rgba(251,191,36,0.2);">
                            <div style="font-size:14px;font-weight:700;color:#92400e;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid #fbbf24;">⬅️ RETOUR - Avec {passenger_name}</div>
                            {retour_avec_content}
                            {create_compact_nav_buttons(offer_data['destination'], offer_data['departure'], waypoints_avec_retour)}
                        </div>
                    </div>
                </div>
            </div>
            '''
        else:
            # SANS PASSAGER - Itinéraire normal (jours non demandés)
            days_sections += f'''
            <div style="background:#fff;border-radius:16px;box-shadow:0 4px 16px rgba(0,0,0,0.1);padding:24px;margin-bottom:24px;border:2px solid #e5e7eb;">
                <div style="display:inline-block;background:linear-gradient(135deg, #f3f4f6, #e5e7eb);color:#374151;padding:10px 24px;border-radius:20px;font-size:15px;font-weight:700;margin-bottom:20px;box-shadow:0 4px 12px rgba(0,0,0,0.1);">
                    📅 {day_full.upper()}
                    <span style="margin-left:8px;background:rgba(255,255,255,0.6);color:#374151;padding:4px 10px;border-radius:12px;font-size:13px;">
                        Sans modification
                    </span>
                </div>
                
                <div style="display:flex;gap:20px;flex-wrap:wrap;">
                    <div style="flex:1;min-width:280px;background:linear-gradient(to bottom, #ffffff, #fafafa);border-radius:12px;padding:20px;border:1px solid #e5e7eb;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                        <div style="font-size:14px;font-weight:700;color:{color_outbound};margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid {color_outbound};">➡️ ALLER</div>
                        <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                            <div style="display:flex;flex-direction:column;align-items:center;">
                                <div style="width:32px;height:32px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏠</div>
                                <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                            </div>
                            <div style="flex:1;margin-left:16px;">
                                <div style="font-weight:600;color:#444;font-size:13px;">Départ</div>
                                <div style="font-weight:700;color:#111;font-size:16px;">{format_time(original_departure_time) if original_departure_time else '—'}</div>
                                <div style="color:#666;font-size:11px;margin-top:2px;">{offer_data['departure']}</div>{existing_passengers_aller_html}
                            </div>
                        </div>{existing_other_pickups_aller_html}
                        <div style="display:flex;align-items:flex-start;">
                            <div style="display:flex;flex-direction:column;align-items:center;">
                                <div style="width:32px;height:32px;border-radius:50%;background:#10b981;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏢</div>
                            </div>
                            <div style="flex:1;margin-left:16px;">
                                <div style="font-weight:600;color:#444;font-size:13px;">Arrivée</div>
                                <div style="font-weight:700;color:#111;font-size:16px;">{format_time(offer_data['recurrent_time'])}</div>
                                <div style="color:#666;font-size:11px;margin-top:2px;">{offer_data['destination']}</div>
                            </div>
                        </div>
                        {create_compact_nav_buttons(offer_data['departure'], offer_data['destination'])}
                    </div>
                    
                    <div style="flex:1;min-width:280px;background:linear-gradient(to bottom, #ffffff, #fafafa);border-radius:12px;padding:20px;border:1px solid #e5e7eb;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                        <div style="font-size:14px;font-weight:700;color:{color_return};margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid {color_return};">⬅️ RETOUR</div>
                        <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                            <div style="display:flex;flex-direction:column;align-items:center;">
                                <div style="width:32px;height:32px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏢</div>
                                <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                            </div>
                            <div style="flex:1;margin-left:16px;">
                                <div style="font-weight:600;color:#444;font-size:13px;">Départ</div>
                                <div style="font-weight:700;color:#111;font-size:16px;">{format_time(offer_data['time_return'])}</div>
                                <div style="color:#666;font-size:11px;margin-top:2px;">{offer_data['destination']}</div>
                            </div>
                        </div>{existing_other_dropoffs_retour_html}
                        <div style="display:flex;align-items:flex-start;">
                            <div style="display:flex;flex-direction:column;align-items:center;">
                                <div style="width:32px;height:32px;border-radius:50%;background:#10b981;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏠</div>
                            </div>
                            <div style="flex:1;margin-left:16px;">
                                <div style="font-weight:600;color:#444;font-size:13px;">Arrivée</div>
                                <div style="font-weight:700;color:#111;font-size:16px;">{format_time(original_arrival_home_time) if original_arrival_home_time else '—'}</div>
                                <div style="color:#666;font-size:11px;margin-top:2px;">{offer_data['departure']}</div>{existing_passengers_retour_html}
                            </div>
                        </div>
                        {create_compact_nav_buttons(offer_data['destination'], offer_data['departure'])}
                    </div>
                </div>
            </div>
            '''
    
    # HTML complet
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">
        <div style="max-width:900px;margin:40px auto;padding:20px;">
            <!-- Encart d'alerte jaune avec toutes les infos -->
            <div style="background:linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);border-radius:16px;box-shadow:0 8px 24px rgba(251,191,36,0.3);padding:32px;margin-bottom:32px;border:3px solid #fbbf24;">
                <div style="text-align:center;margin-bottom:24px;">
                    <h1 style="color:#78350f;font-size:28px;margin:0 0 12px 0;font-weight:800;">🚗 Nouvelle demande de covoiturage</h1>
                    <p style="color:#92400e;font-size:16px;margin:0;line-height:1.5;font-weight:600;">Bonjour {offer_data['driver_name']}, <strong>{passenger_name}</strong> souhaite rejoindre votre covoiturage.</p>
                </div>
                
                <div style="background:#fff;border-radius:12px;padding:24px;margin-bottom:16px;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                    <div style="font-size:13px;font-weight:600;color:#78350f;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px;">👤 Passager</div>
                    <div style="font-size:20px;font-weight:700;color:#111;margin-bottom:8px;">{passenger_name}</div>
                    <div style="font-size:14px;color:#666;margin-bottom:4px;">✉️ {passenger_email}</div>
                    {f'<div style="font-size:14px;color:#666;">📱 {passenger_phone}</div>' if passenger_phone else ''}
                </div>
                
                <div style="background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                    <div style="font-size:13px;font-weight:600;color:#78350f;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px;">📍 Point de prise en charge</div>
                    <div style="font-size:16px;font-weight:700;color:#111;line-height:1.4;">{pickup_address}</div>
                </div>
            </div>
            
            {action_buttons}
            
            <!-- Sections par jour -->
            {days_sections}
            
            <!-- Footer -->
            <div style="text-align:center;padding:28px;background:#fff;border-radius:16px;box-shadow:0 2px 12px rgba(0,0,0,0.08);margin-top:32px;">
                <p style="font-size:13px;color:#999;margin:0;line-height:1.6;">
                    Cet email a été envoyé automatiquement par <strong style="color:#666;">Carette Covoiturage</strong>
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
{header_title}

{intro_text}

Passager : {passenger_name}
Email : {passenger_email}
{f'Téléphone : {passenger_phone}' if passenger_phone else ''}

Point de prise en charge : {pickup_address}

Jours demandés : {', '.join([day_names[d][0] for d in days_requested])}

Détour aller : +{int(detour_outbound)} min
Détour retour : +{int(detour_return)} min

---
Carette - Plateforme de covoiturage RSE
    """
    
    return (subject, html_body, text_body)
