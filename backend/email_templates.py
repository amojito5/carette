"""
Templates d'emails HTML avec le design des cartes du widget Carette
"""
import os
import urllib.parse

def format_time(dt_str: str) -> str:
    """Formate une date en HH:MM"""
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%H:%M')
    except:
        return dt_str

def detour_progress_bar(remaining_minutes: int, max_minutes: int) -> str:
    """
    Génère une barre de progression pour le temps de détour
    Couleur: vert (>66%), orange (33-66%), rouge (<33%)
    """
    percentage = (remaining_minutes / max_minutes * 100) if max_minutes > 0 else 100
    if percentage >= 66:
        color = '#10b981'  # Vert
    elif percentage >= 33:
        color = '#f59e0b'  # Orange
    else:
        color = '#ef4444'  # Rouge
    
    return f'''
    <div style="margin-top:12px;">
        <div style="font-size:11px;color:#666;margin-bottom:4px;text-align:center;">
            ⏱️ Détour disponible : <strong style="color:{color};">{remaining_minutes} min</strong>
        </div>
        <div style="background:#e5e7eb;height:6px;border-radius:3px;overflow:hidden;">
            <div style="background:{color};height:100%;width:{percentage}%;transition:width 0.3s;"></div>
        </div>
    </div>
    '''

def generate_static_map_url(
    departure_coords: dict,
    destination_coords: dict,
    route_geometry: str = None,
    width: int = 600,
    height: int = 300
) -> str:
    """
    Génère une URL de carte statique publique compatible avec les clients email
    Utilise l'API Geoapify (gratuite, pas de clé nécessaire pour usage basique)
    """
    try:
        # Coordonnées de départ et arrivée
        dep_lat = departure_coords.get('lat', 0)
        dep_lon = departure_coords.get('lon', 0)
        dest_lat = destination_coords.get('lat', 0)
        dest_lon = destination_coords.get('lon', 0)
        
        # Calculer le centre et le zoom
        center_lat = (dep_lat + dest_lat) / 2
        center_lon = (dep_lon + dest_lon) / 2
        
        # Calculer la distance approximative pour déterminer le zoom
        import math
        lat_diff = abs(dep_lat - dest_lat)
        lon_diff = abs(dep_lon - dest_lon)
        max_diff = max(lat_diff, lon_diff)
        
        # Zoom adaptatif
        if max_diff > 2:
            zoom = 7
        elif max_diff > 1:
            zoom = 8
        elif max_diff > 0.5:
            zoom = 9
        elif max_diff > 0.2:
            zoom = 10
        else:
            zoom = 11
        
        # Utiliser l'API OpenStreetMap Static Map (via open.mapquestapi.com - sans clé pour affichage basique)
        # Ajouter les marqueurs pour départ (vert) et destination (rouge)
        marker_start = f"{dep_lat},{dep_lon}"
        marker_end = f"{dest_lat},{dest_lon}"
        
        # Construire l'URL avec les marqueurs
        url = f"https://open.mapquestapi.com/staticmap/v5/map?locations={marker_start}|{marker_end}&size={width},{height}@2x&zoom={zoom}&defaultMarker=marker-sm"
        
        return url
    except Exception as e:
        print(f"Erreur génération URL carte: {e}")
        return None

def email_card_template(
    departure: str,
    destination: str,
    datetime_str: str,
    return_datetime_str: str = None,
    seats_outbound: int = 0,
    seats_return: int = 0,
    reserved_outbound: int = 0,
    reserved_return: int = 0,
    driver_name: str = '',
    driver_email: str = '',
    driver_phone: str = '',
    price: str = None,
    meeting_address: str = None,
    passengers: list = None,
    offer_details: dict = None
) -> str:
    """
    Template de carte d'offre stylée comme dans le widget "Mes trajets"
    Avec timeline verticale et tableau aller/retour
    """
    passengers = passengers or []
    offer_details = offer_details or {}
    
    # Couleurs aller/retour
    color_outbound = '#1f8f56'
    color_return = '#3b82f6'
    
    # Indicateurs de places ALLER
    seat_icons_outbound = ""
    for i in range(seats_outbound):
        taken = i < reserved_outbound
        bg_color = "#d1d5db" if taken else "#10b981"
        seat_icons_outbound += f'<span style="display:inline-block;width:18px;height:18px;border-radius:4px;margin-right:4px;background:{bg_color};"></span>'
    
    # Indicateurs de places RETOUR
    seat_icons_return = ""
    for i in range(seats_return):
        taken = i < reserved_return
        bg_color = "#d1d5db" if taken else "#10b981"
        seat_icons_return += f'<span style="display:inline-block;width:18px;height:18px;border-radius:4px;margin-right:4px;background:{bg_color};"></span>'
    
    # Timeline verticale ALLER
    passengers_outbound = [p for p in passengers if p.get('trip_type', 'outbound') == 'outbound']
    timeline_outbound_steps = []
    
    # Départ
    timeline_outbound_steps.append(f'''
        <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
            <div style="display:flex;flex-direction:column;align-items:center;">
                <div style="width:32px;height:32px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏠</div>
                <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
            </div>
            <div style="flex:1;margin-left:20px;">
                <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:2px;">Départ</div>
                <div style="font-weight:700;color:#111;font-size:14px;margin-bottom:2px;">{format_time(datetime_str) if datetime_str else '—'}</div>
                <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{departure}</div>
            </div>
        </div>
    ''')
    
    # Passagers aller
    for p in passengers_outbound:
        pax_name = p.get('passenger_name', 'Passager')
        pax_address = p.get('meeting_point_address', p.get('pickup_address', 'Point de rendez-vous'))
        pax_time = format_time(p.get('pickup_time', '')) if p.get('pickup_time') else '—'
        is_last_pax = (p == passengers_outbound[-1] and not destination)
        connector = '' if is_last_pax else '<div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>'
        
        timeline_outbound_steps.append(f'''
            <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                <div style="display:flex;flex-direction:column;align-items:center;">
                    <div style="width:32px;height:32px;border-radius:50%;background:#f59e0b;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">👤</div>
                    {connector}
                </div>
                <div style="flex:1;margin-left:20px;">
                    <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:2px;">{pax_name}</div>
                    <div style="font-weight:700;color:#111;font-size:14px;margin-bottom:2px;">{pax_time}</div>
                    <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{pax_address}</div>
                </div>
            </div>
        ''')
    
    # Arrivée
    timeline_outbound_steps.append(f'''
        <div style="display:flex;align-items:flex-start;">
            <div style="display:flex;flex-direction:column;align-items:center;">
                <div style="width:32px;height:32px;border-radius:50%;background:#10b981;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏁</div>
            </div>
            <div style="flex:1;margin-left:20px;">
                <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:2px;">Arrivée</div>
                <div style="font-weight:700;color:#111;font-size:14px;margin-bottom:2px;">{format_time(datetime_str) if datetime_str else '—'}</div>
                <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{destination}</div>
            </div>
        </div>
    ''')
    
    timeline_outbound = ''.join(timeline_outbound_steps)
    
    # Timeline verticale RETOUR
    passengers_return = [p for p in passengers if p.get('trip_type') == 'return']
    timeline_return_steps = []
    
    if return_datetime_str:
        # Départ retour
        timeline_return_steps.append(f'''
            <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                <div style="display:flex;flex-direction:column;align-items:center;">
                    <div style="width:32px;height:32px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏠</div>
                    <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                </div>
                <div style="flex:1;margin-left:20px;">
                    <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:2px;">Départ</div>
                    <div style="font-weight:700;color:#111;font-size:14px;margin-bottom:2px;">{format_time(return_datetime_str)}</div>
                    <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{destination}</div>
                </div>
            </div>
        ''')
        
        # Passagers retour
        for p in passengers_return:
            pax_name = p.get('passenger_name', 'Passager')
            pax_address = p.get('meeting_point_address', p.get('pickup_address', 'Point de rendez-vous'))
            pax_time = format_time(p.get('pickup_time', '')) if p.get('pickup_time') else '—'
            is_last_pax = (p == passengers_return[-1])
            connector = '' if is_last_pax else '<div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>'
            
            timeline_return_steps.append(f'''
                <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                    <div style="display:flex;flex-direction:column;align-items:center;">
                        <div style="width:32px;height:32px;border-radius:50%;background:#f59e0b;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">👤</div>
                        {connector}
                    </div>
                    <div style="flex:1;margin-left:20px;">
                        <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:2px;">{pax_name}</div>
                        <div style="font-weight:700;color:#111;font-size:14px;margin-bottom:2px;">{pax_time}</div>
                        <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{pax_address}</div>
                    </div>
                </div>
            ''')
        
        # Arrivée retour
        timeline_return_steps.append(f'''
            <div style="display:flex;align-items:flex-start;">
                <div style="display:flex;flex-direction:column;align-items:center;">
                    <div style="width:32px;height:32px;border-radius:50%;background:#10b981;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏁</div>
                </div>
                <div style="flex:1;margin-left:20px;">
                    <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:2px;">Arrivée</div>
                    <div style="font-weight:700;color:#111;font-size:14px;margin-bottom:2px;">—</div>
                    <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{departure}</div>
                </div>
            </div>
        ''')
    
    timeline_return = ''.join(timeline_return_steps) if return_datetime_str else '<div style="color:#999;font-size:14px;text-align:center;padding:20px;">Pas de trajet retour</div>'
    
    # Prix
    price_html = f'<div style="font-size:22px;font-weight:800;color:{color_outbound};">{price}</div>' if price else ''
    
    # Construction de la carte complète
    return f"""
    <div style="max-width:700px;margin:20px auto;padding:24px;background:#ffffff;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.12);font-family:Arial,sans-serif;">
        <!-- En-tête conducteur -->
        <div style="margin-bottom:20px;padding-bottom:16px;border-bottom:2px solid #e5e7eb;">
            <div style="font-size:20px;font-weight:700;color:#111;margin-bottom:6px;">🚗 {driver_name}</div>
            <div style="font-size:14px;color:#666;">✉️ {driver_email} · 📞 {driver_phone}</div>
        </div>
        
        <!-- Tableau Aller / Retour -->
        <div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:10px;padding:20px;margin-bottom:20px;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                    <!-- Colonne ALLER -->
                    <td width="48%" valign="top">
                        <div style="font-size:15px;font-weight:700;color:{color_outbound};margin-bottom:12px;display:flex;align-items:center;gap:8px;">
                            <span>➡️ ALLER</span>
                        </div>
                        <div style="margin-bottom:14px;">{seat_icons_outbound}</div>
                        <div style="background:#fff;border-radius:8px;padding:16px;">
                            {timeline_outbound}
                        </div>
                    </td>
                    <!-- Espace central -->
                    <td width="4%"></td>
                    <!-- Colonne RETOUR -->
                    <td width="48%" valign="top">
                        <div style="font-size:15px;font-weight:700;color:{color_return};margin-bottom:12px;display:flex;align-items:center;gap:8px;">
                            <span>⬅️ RETOUR</span>
                        </div>
                        <div style="margin-bottom:14px;">{seat_icons_return if return_datetime_str else ''}</div>
                        <div style="background:#fff;border-radius:8px;padding:16px;">
                            {timeline_return if timeline_return else '<div style="text-align:center;color:#999;padding:20px;font-size:13px;">Pas de trajet retour</div>'}
                        </div>
                    </td>
                </tr>
            </table>
        </div>
        
        <!-- Prix et point de RDV -->
        <div style="display:flex;justify-content:space-between;align-items:center;padding:16px;background:#f8f9fa;border-radius:8px;">
            <div>
                {f'<div style="font-size:13px;color:#666;margin-bottom:4px;">📍 Point de rendez-vous</div><div style="font-size:14px;font-weight:600;color:#222;">{meeting_address}</div>' if meeting_address else '<div style="font-size:13px;color:#999;">Détails à confirmer</div>'}
            </div>
            {price_html}
        </div>
    </div>
    """


def email_offer_published(driver_email: str, driver_name: str, offer: dict, base_url: str) -> tuple:
    """
    Email de confirmation après création d'offre
    Reproduit exactement le design de "Mes trajets" avec timeline et gestion passagers
    Returns: (subject, html_body, text_body)
    """
    # Récupérer les détails de l'offre
    has_return = offer.get('has_return', False)
    seats_outbound = offer.get('seats_outbound', offer.get('seats', 4))
    seats_return = offer.get('seats_return', seats_outbound) if has_return else 0
    max_detour = offer.get('max_detour_time', 15)
    
    departure = offer.get('departure', '')
    destination = offer.get('destination', '')
    
    # Heures ALLER : departure_time (départ) → datetime (arrivée)
    departure_time = offer.get('departure_time', offer.get('datetime', ''))
    arrival_time = offer.get('datetime', '')
    
    # Heures RETOUR : return_datetime (départ) → return_arrival_time (arrivée)
    return_departure_time = offer.get('return_datetime', '')
    return_arrival_time = offer.get('return_arrival_time', '')
    
    # Prix
    price_val = offer.get('price')
    if price_val and isinstance(price_val, (int, float)):
        price = f"{price_val:.2f} €".replace('.', ',')
    else:
        price = "—"
    
    # Couleurs
    color_outbound = '#1f8f56'
    color_return = '#3b82f6'
    
    # Générer la carte statique
    map_image_path = offer.get('map_image_path')
    departure_coords = offer.get('departure_coords')
    destination_coords = offer.get('destination_coords')
    
    # Parser les coordonnées si elles sont en JSON string
    import json
    if isinstance(departure_coords, str):
        try:
            departure_coords = json.loads(departure_coords)
        except:
            departure_coords = None
    
    if isinstance(destination_coords, str):
        try:
            destination_coords = json.loads(destination_coords)
        except:
            destination_coords = None
    
    # Créer l'HTML de la carte
    map_html = ""
    if map_image_path:
        # Utiliser CID (Content-ID) pour l'image inline
        # L'image sera attachée au mail avec ce CID
        
        # Lien Google Maps pour ouvrir dans le navigateur
        gmaps_url = ""
        if departure_coords and destination_coords:
            dep_lat = departure_coords.get('lat', 0)
            dep_lon = departure_coords.get('lon', 0)
            dest_lat = destination_coords.get('lat', 0)
            dest_lon = destination_coords.get('lon', 0)
            gmaps_url = f"https://www.google.com/maps/dir/{dep_lat},{dep_lon}/{dest_lat},{dest_lon}"
        
        map_html = f'''
            <!-- Carte avec itinéraires (image inline) -->
            <div style="margin-bottom:24px;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.15);">
                <div style="background:linear-gradient(135deg, #1f8f56 0%, #15b365 100%);padding:16px;text-align:center;">
                    <span style="font-size:16px;font-weight:700;color:#1a1a1a;">🗺️ Itinéraire de votre trajet</span>
                </div>
                <img src="cid:map_image" alt="Carte du trajet" style="width:100%;height:auto;display:block;" />
                <div style="background:#f8f9fa;padding:14px;text-align:center;border-top:2px solid #1f8f56;">
                    <div style="font-size:13px;color:#666;margin-bottom:10px;">
                        <span style="display:inline-block;width:12px;height:3px;background:#1f8f56;margin-right:6px;"></span>
                        <span style="font-weight:600;">Aller</span>
                        {' · <span style="display:inline-block;width:12px;height:3px;background:#3b82f6;margin:0 6px;"></span><span style="font-weight:600;">Retour</span>' if has_return else ''}
                    </div>
                    {f'<a href="{gmaps_url}" target="_blank" style="display:inline-block;background:#1f8f56;color:#fff;text-decoration:none;padding:10px 20px;border-radius:8px;font-weight:600;font-size:14px;">📍 Ouvrir dans Google Maps</a>' if gmaps_url else ''}
                </div>
            </div>
        '''
    elif departure_coords and destination_coords:
        # Fallback si pas d'image : juste le bouton Google Maps
        dep_lat = departure_coords.get('lat', 0)
        dep_lon = departure_coords.get('lon', 0)
        dest_lat = destination_coords.get('lat', 0)
        dest_lon = destination_coords.get('lon', 0)
        gmaps_url = f"https://www.google.com/maps/dir/{dep_lat},{dep_lon}/{dest_lat},{dest_lon}"
        
        map_html = f'''
            <div style="margin-bottom:24px;background:linear-gradient(135deg, #1f8f56 0%, #15b365 100%);border-radius:12px;padding:20px;text-align:center;box-shadow:0 4px 12px rgba(31,143,86,0.3);">
                <div style="font-size:16px;font-weight:700;color:#fff;margin-bottom:12px;">🗺️ Visualiser l'itinéraire</div>
                <a href="{gmaps_url}" target="_blank" style="display:inline-block;background:#fff;color:#1f8f56;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:700;font-size:15px;box-shadow:0 2px 6px rgba(0,0,0,0.15);">
                    📍 Ouvrir dans Google Maps
                </a>
                <div style="margin-top:12px;font-size:13px;color:rgba(255,255,255,0.9);">{departure} → {destination}</div>
            </div>
        '''
    
    # Indicateurs de places ALLER (toutes vertes = aucune réservation)
    seat_icons_outbound = ""
    for i in range(seats_outbound):
        seat_icons_outbound += f'<span style="display:inline-block;width:18px;height:18px;border-radius:4px;margin-right:4px;background:#10b981;"></span>'
    
    # Indicateurs de places RETOUR
    seat_icons_return = ""
    if has_return:
        for i in range(seats_return):
            seat_icons_return += f'<span style="display:inline-block;width:18px;height:18px;border-radius:4px;margin-right:4px;background:#10b981;"></span>'
    
    # Timeline ALLER
    timeline_aller = f'''
        <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
            <div style="display:flex;flex-direction:column;align-items:center;">
                <div style="width:32px;height:32px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏠</div>
                <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
            </div>
            <div style="flex:1;margin-left:20px;">
                <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:2px;">Départ</div>
                <div style="font-weight:700;color:#111;font-size:14px;margin-bottom:2px;">{format_time(departure_time)}</div>
                <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{departure}</div>
            </div>
        </div>
        <div style="display:flex;align-items:flex-start;">
            <div style="display:flex;flex-direction:column;align-items:center;">
                <div style="width:32px;height:32px;border-radius:50%;background:#10b981;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏁</div>
            </div>
            <div style="flex:1;margin-left:20px;">
                <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:2px;">Arrivée</div>
                <div style="font-weight:700;color:#111;font-size:14px;margin-bottom:2px;">{format_time(arrival_time)}</div>
                <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{destination}</div>
            </div>
        </div>
    '''
    
    # Timeline RETOUR
    if has_return and return_departure_time:
        timeline_retour = f'''
            <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                <div style="display:flex;flex-direction:column;align-items:center;">
                    <div style="width:32px;height:32px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏠</div>
                    <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                </div>
                <div style="flex:1;margin-left:20px;">
                    <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:2px;">Départ</div>
                    <div style="font-weight:700;color:#111;font-size:14px;margin-bottom:2px;">{format_time(return_departure_time)}</div>
                    <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{destination}</div>
                </div>
            </div>
            <div style="display:flex;align-items:flex-start;">
                <div style="display:flex;flex-direction:column;align-items:center;">
                    <div style="width:32px;height:32px;border-radius:50%;background:#10b981;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏁</div>
                </div>
                <div style="flex:1;margin-left:20px;">
                    <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:2px;">Arrivée</div>
                    <div style="font-weight:700;color:#111;font-size:14px;margin-bottom:2px;">{format_time(return_arrival_time) if return_arrival_time else '—'}</div>
                    <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{departure}</div>
                </div>
            </div>
        '''
    else:
        timeline_retour = '<div style="color:#999;font-size:14px;text-align:center;padding:32px 20px;background:#f8f9fa;border-radius:8px;">Pas de trajet retour</div>'
    
    subject = f"✅ Votre offre {departure} → {destination} est publiée"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif;">
        <div style="max-width:800px;margin:40px auto;padding:20px;">
            <h2 style="color:#1f8f56;text-align:center;margin-bottom:8px;">🚗 Offre publiée avec succès !</h2>
            <p style="text-align:center;color:#666;margin-bottom:32px;font-size:15px;">Bonjour {driver_name}, votre trajet est maintenant visible par les passagers.</p>
            
            {map_html}
            
            <!-- Carte récapitulative style "Mes trajets" -->
            <div style="background:#fff;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.12);padding:24px;margin-bottom:24px;">
                <!-- En-tête conducteur -->
                <div style="margin-bottom:20px;padding-bottom:16px;border-top:4px solid {color_outbound};padding-top:16px;">
                    <div style="font-size:20px;font-weight:700;color:#111;margin-bottom:6px;">🚗 {driver_name}</div>
                    <div style="font-size:14px;color:#666;">✉️ {driver_email} · 📞 {offer.get('driver_phone', '')}</div>
                </div>
                
                <!-- Tableau Aller / Retour -->
                <div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:10px;padding:10px;margin-bottom:20px;">
                    
                    <!-- Version mobile-friendly : blocs empilés -->
                    <!--[if mso]>
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                        <tr>
                            <td width="49%" valign="top" style="padding-right:8px;">
                    <![endif]-->
                    
                    <!-- ALLER -->
                    <div style="display:inline-block;width:49%;min-width:260px;max-width:100%;vertical-align:top;margin-bottom:16px;padding-right:1%;">
                        <div style="font-size:14px;font-weight:700;color:{color_outbound};margin-bottom:8px;">➡️ ALLER</div>
                        <div style="margin-bottom:8px;">{seat_icons_outbound}</div>
                        {detour_progress_bar(max_detour, max_detour)}
                        <div style="background:#fff;border-radius:8px;padding:10px;margin-top:8px;overflow:hidden;">
                            {timeline_aller}
                        </div>
                    </div>
                    
                    <!--[if mso]>
                            </td>
                            <td width="49%" valign="top" style="padding-left:8px;">
                    <![endif]-->
                    
                    <!-- RETOUR -->
                    <div style="display:inline-block;width:49%;min-width:260px;max-width:100%;vertical-align:top;margin-bottom:16px;{'' if has_return else 'opacity:0.5;'}">
                        <div style="font-size:14px;font-weight:700;color:{color_return};margin-bottom:8px;">⬅️ RETOUR</div>
                        <div style="margin-bottom:8px;">{seat_icons_return if has_return else ''}</div>
                        {detour_progress_bar(max_detour, max_detour) if has_return else ''}
                        <div style="background:#fff;border-radius:8px;padding:10px;margin-top:8px;overflow:hidden;">
                            {timeline_retour if has_return else '<div style="text-align:center;color:#999;padding:15px;font-size:12px;">Pas de trajet retour</div>'}
                        </div>
                    </div>
                    
                    <!--[if mso]>
                            </td>
                        </tr>
                    </table>
                    <![endif]-->
                    
                </div>
                
                <!-- Prix -->
                <div style="display:flex;justify-content:space-between;align-items:center;padding:16px;background:#f8f9fa;border-radius:8px;margin-bottom:20px;">
                    <div style="font-size:14px;color:#666;">💰 Prix par passager</div>
                    <div style="font-size:24px;font-weight:800;color:{color_outbound};">{price}</div>
                </div>
                
                <!-- Section Passagers (vide pour l'instant) -->
                <div style="border:1px solid #dee2e6;border-radius:8px;padding:20px;background:#fafafa;">
                    <div style="font-size:16px;font-weight:700;color:#111;margin-bottom:12px;">👥 Gestion des passagers</div>
                    <div style="text-align:center;color:#999;padding:20px;font-size:14px;">
                        Aucune réservation pour le moment.<br/>
                        <span style="font-weight:600;color:#666;">Vous recevrez un email dès qu'un passager réservera !</span>
                    </div>
                </div>
            </div>
            
            <!-- Info pratique -->
            <div style="text-align:center;padding:24px;background:white;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                <p style="color:#666;margin-bottom:16px;font-size:15px;">📧 Vous recevrez un email avec les détails à chaque nouvelle réservation.</p>
                <p style="font-size:13px;color:#999;margin-top:24px;">Cet email a été envoyé automatiquement par Carette Covoiturage</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
Offre publiée avec succès !

➡️ ALLER
Trajet: {departure} → {destination}
Départ: {format_time(departure_time)}
Arrivée: {format_time(arrival_time)}
Places: {seats_outbound}

{'⬅️ RETOUR' if has_return else ''}
{'Trajet: ' + destination + ' → ' + departure if has_return else ''}
{'Départ: ' + format_time(return_departure_time) if has_return and return_departure_time else ''}
{'Arrivée: ' + (format_time(return_arrival_time) if return_arrival_time else '—') if has_return else ''}
{'Places: ' + str(seats_return) if has_return else ''}

Prix: {price}

Vous recevrez un email dès qu'un passager réservera.
"""
    
    return (subject, html_body, text_body)


def email_reservation_confirmed_to_passenger(
    passenger_email: str, 
    passenger_name: str, 
    driver_name: str, 
    driver_phone: str, 
    driver_email_contact: str, 
    offer: dict, 
    meeting_address: str, 
    price: str, 
    cancel_url: str
) -> tuple:
    """
    Email au passager après réservation (avant acceptation conducteur)
    Returns: (subject, html_body, text_body)
    """
    # Déterminer le type de trajet
    trip_type = offer.get('trip_type', 'outbound')
    has_return = offer.get('return_datetime') is not None
    
    # Seats info
    seats_outbound = offer.get('seats_outbound', offer.get('seats', 4))
    seats_return = offer.get('seats_return', seats_outbound) if has_return else 0
    reserved_outbound = offer.get('reserved_count_outbound', 0)
    reserved_return = offer.get('reserved_count_return', 0)
    
    # Construire la carte avec le passager en attente
    passengers_data = [{
        'trip_type': trip_type,
        'passenger_name': passenger_name,
        'meeting_point_address': meeting_address,
        'pickup_time': offer.get('datetime') if trip_type == 'outbound' else offer.get('return_datetime'),
        'status': 'pending'
    }]
    
    card_html = email_card_template(
        departure=offer.get('departure', ''),
        destination=offer.get('destination', ''),
        datetime_str=offer.get('datetime', ''),
        return_datetime_str=offer.get('return_datetime'),
        seats_outbound=0,  # Ne pas afficher les sièges au passager
        seats_return=0,
        reserved_outbound=0,
        reserved_return=0,
        driver_name=driver_name,
        driver_email=driver_email_contact,
        driver_phone=driver_phone,
        price=price,
        meeting_address=meeting_address,
        passengers=passengers_data
    )
    
    trip_label = "➡️ ALLER" if trip_type == 'outbound' else "⬅️ RETOUR"
    subject = f"🎉 Réservation {trip_label} pour {offer.get('departure', '')} → {offer.get('destination', '')}"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif;">
        <div style="max-width:700px;margin:40px auto;padding:20px;">
            <h2 style="color:#10b981;text-align:center;margin-bottom:8px;">🎉 Réservation acceptée !</h2>
            <p style="text-align:center;color:#666;margin-bottom:32px;font-size:15px;">Bonjour {passenger_name}, <strong>{driver_name}</strong> a accepté votre demande de covoiturage.</p>
            
            {card_html}
            
            <!-- Statut confirmé -->
            <div style="text-align:center;margin-top:32px;padding:20px;background:#d1fae5;border-radius:12px;border-left:5px solid #10b981;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                <p style="color:#065f46;margin:0;font-weight:700;font-size:16px;">✅ Votre place est confirmée</p>
                <p style="color:#047857;margin:12px 0 0 0;font-size:14px;">Vous recevrez un rappel 24h avant le départ.</p>
            </div>
            
            <!-- Bouton annulation -->
            <div style="text-align:center;margin-top:24px;">
                <a href="{cancel_url}" style="display:inline-block;padding:14px 32px;background:#dc3545;color:white;text-decoration:none;border-radius:10px;font-weight:700;font-size:15px;box-shadow:0 2px 8px rgba(220,53,69,0.3);">
                    ✗ Annuler ma réservation
                </a>
            </div>
            
            <div style="text-align:center;margin-top:32px;padding:20px;background:white;border-radius:10px;">
                <p style="font-size:13px;color:#999;">Cet email a été envoyé automatiquement par Carette Covoiturage</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
Réservation envoyée !

Trajet {trip_label}: {offer.get('departure', '')} → {offer.get('destination', '')}
Date: {offer.get('datetime', '') if trip_type == 'outbound' else offer.get('return_datetime', '')}
Conducteur: {driver_name} ({driver_phone})
Prix: {price}
Point de RDV: {meeting_address}

⏳ En attente de confirmation du conducteur.
Vous recevrez un email dès qu'il aura accepté.

Annuler: {cancel_url}
"""
    
    return (subject, html_body, text_body)


# ============================================================================
# NOUVEAUX TEMPLATES POUR MAGIC LINKS
# ============================================================================

def email_new_reservation_request(
    driver_email: str,
    driver_name: str,
    passenger_name: str,
    passenger_email: str,
    passenger_phone: str,
    offer: dict,
    trip_type: str = 'outbound',
    meeting_address: str = '',
    detour_minutes: int = 0,
    accept_url: str = '',
    refuse_url: str = '',
    base_url: str = ''
) -> tuple:
    """
    Template : Nouvelle demande de réservation reçue (envoyé au conducteur)
    Contient les boutons [Accepter] [Refuser]
    
    Args:
        driver_email: Email du conducteur
        driver_name: Nom du conducteur
        passenger_name: Nom du passager demandeur
        passenger_email: Email du passager
        passenger_phone: Téléphone du passager
        offer: Dict avec les données de l'offre
        trip_type: 'outbound' ou 'return'
        meeting_address: Adresse de prise en charge
        detour_minutes: Détour estimé en minutes
        accept_url: URL magic link pour accepter
        refuse_url: URL magic link pour refuser
        base_url: URL de base du site
    
    Returns:
        Tuple (subject, html_body, text_body)
    """
    trip_label = "ALLER" if trip_type == 'outbound' else "RETOUR"
    color = '#c47cff' if trip_type == 'outbound' else '#ff9c3f'
    
    subject = f"📬 Nouvelle demande de {passenger_name}"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
        <div style="max-width:600px;margin:40px auto;background:white;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);overflow:hidden;">
            
            <!-- Header -->
            <div style="background:linear-gradient(135deg, {color} 0%, {color}dd 100%);padding:32px;text-align:center;">
                <div style="font-size:48px;margin-bottom:12px;">📬</div>
                <h1 style="color:white;margin:0;font-size:28px;font-weight:700;">Nouvelle demande</h1>
                <p style="color:rgba(255,255,255,0.95);margin:8px 0 0 0;font-size:16px;">Un passager souhaite vous rejoindre</p>
            </div>
            
            <!-- Body -->
            <div style="padding:32px;">
                
                <!-- Passager -->
                <div style="background:#f8f9fa;padding:20px;border-radius:12px;margin-bottom:24px;border-left:4px solid {color};">
                    <h2 style="margin:0 0 12px 0;font-size:20px;color:#2d3748;">👤 {passenger_name}</h2>
                    <p style="margin:0;color:#4a5568;font-size:14px;">📧 {passenger_email}</p>
                    <p style="margin:4px 0 0 0;color:#4a5568;font-size:14px;">📱 {passenger_phone}</p>
                </div>
                
                <!-- Détails trajet -->
                <div style="background:#fff;border:2px solid #e2e8f0;padding:20px;border-radius:12px;margin-bottom:24px;">
                    <div style="margin-bottom:16px;">
                        <span style="display:inline-block;background:{color};color:white;padding:4px 12px;border-radius:6px;font-size:12px;font-weight:700;">{trip_label}</span>
                    </div>
                    <p style="margin:0 0 8px 0;color:#2d3748;font-size:16px;font-weight:600;">
                        🏠 {offer.get('departure', '')} → 🏁 {offer.get('destination', '')}
                    </p>
                    <p style="margin:0 0 8px 0;color:#4a5568;font-size:14px;">
                        📅 {offer.get('datetime', '') if trip_type == 'outbound' else offer.get('return_datetime', '')}
                    </p>
                    {f'<p style="margin:0 0 8px 0;color:#4a5568;font-size:14px;">📍 Prise en charge : {meeting_address}</p>' if meeting_address else ''}
                    {f'<p style="margin:0;color:#d97706;font-size:14px;font-weight:600;">⏱️ Détour : +{detour_minutes} min</p>' if detour_minutes > 0 else ''}
                </div>
                
                <!-- Info timeout -->
                <div style="background:#fef3c7;border:1px solid #fbbf24;padding:16px;border-radius:8px;margin-bottom:24px;">
                    <p style="margin:0;color:#78350f;font-size:13px;text-align:center;">
                        ⏰ <strong>Vous avez 24 heures</strong> pour répondre à cette demande
                    </p>
                </div>
                
                <!-- Boutons d'action -->
                <div style="display:flex;gap:12px;margin-bottom:24px;">
                    <a href="{accept_url}" style="flex:1;display:block;padding:16px;background:#10b981;color:white;text-align:center;text-decoration:none;border-radius:10px;font-weight:700;font-size:16px;box-shadow:0 2px 8px rgba(16,185,129,0.3);">
                        ✓ Accepter
                    </a>
                    <a href="{refuse_url}" style="flex:1;display:block;padding:16px;background:#ef4444;color:white;text-align:center;text-decoration:none;border-radius:10px;font-weight:700;font-size:16px;box-shadow:0 2px 8px rgba(239,68,68,0.3);">
                        ✗ Refuser
                    </a>
                </div>
                
            </div>
            
            <!-- Footer -->
            <div style="text-align:center;padding:20px;background:#f8f9fa;">
                <p style="margin:0;font-size:13px;color:#999;">Carette Covoiturage</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
📬 Nouvelle demande de réservation

Passager: {passenger_name}
Email: {passenger_email}
Téléphone: {passenger_phone}

Trajet {trip_label}: {offer.get('departure', '')} → {offer.get('destination', '')}
Date: {offer.get('datetime', '') if trip_type == 'outbound' else offer.get('return_datetime', '')}
{f'Prise en charge: {meeting_address}' if meeting_address else ''}
{f'Détour: +{detour_minutes} min' if detour_minutes > 0 else ''}

⏰ Vous avez 24 heures pour répondre

Accepter: {accept_url}
Refuser: {refuse_url}
"""
    
    return (subject, html_body, text_body)


def email_request_sent_to_passenger(
    passenger_email: str,
    passenger_name: str,
    driver_name: str,
    offer: dict,
    trip_type: str = 'outbound',
    meeting_address: str = ''
) -> tuple:
    """
    Template : Demande envoyée (confirmation au passager)
    Info : Le conducteur a 24h pour répondre
    """
    trip_label = "ALLER" if trip_type == 'outbound' else "RETOUR"
    color = '#c47cff' if trip_type == 'outbound' else '#ff9c3f'
    
    subject = f"✅ Demande envoyée à {driver_name}"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
        <div style="max-width:600px;margin:40px auto;background:white;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);overflow:hidden;">
            
            <!-- Header -->
            <div style="background:linear-gradient(135deg, #10b981 0%, #059669 100%);padding:32px;text-align:center;">
                <div style="font-size:48px;margin-bottom:12px;">✅</div>
                <h1 style="color:white;margin:0;font-size:28px;font-weight:700;">Demande envoyée</h1>
                <p style="color:rgba(255,255,255,0.95);margin:8px 0 0 0;font-size:16px;">Votre demande a bien été transmise</p>
            </div>
            
            <!-- Body -->
            <div style="padding:32px;">
                
                <p style="margin:0 0 20px 0;color:#2d3748;font-size:16px;">
                    Bonjour <strong>{passenger_name}</strong>,
                </p>
                
                <p style="margin:0 0 20px 0;color:#4a5568;font-size:15px;">
                    Votre demande de réservation a été envoyée à <strong>{driver_name}</strong>.
                </p>
                
                <!-- Trajet -->
                <div style="background:#f8f9fa;padding:20px;border-radius:12px;margin-bottom:24px;">
                    <div style="margin-bottom:12px;">
                        <span style="display:inline-block;background:{color};color:white;padding:4px 12px;border-radius:6px;font-size:12px;font-weight:700;">{trip_label}</span>
                    </div>
                    <p style="margin:0 0 8px 0;font-size:16px;color:#2d3748;font-weight:600;">
                        {offer.get('departure', '')} → {offer.get('destination', '')}
                    </p>
                    <p style="margin:0 0 8px 0;color:#4a5568;font-size:14px;">
                        📅 {offer.get('datetime', '') if trip_type == 'outbound' else offer.get('return_datetime', '')}
                    </p>
                    {f'<p style="margin:0;color:#4a5568;font-size:14px;">📍 Point de prise en charge : <strong>{meeting_address}</strong></p>' if meeting_address else ''}
                </div>
                
                <!-- Timeout info -->
                <div style="background:#fef3c7;border:1px solid #fbbf24;padding:20px;border-radius:8px;margin-bottom:24px;">
                    <p style="margin:0 0 8px 0;color:#78350f;font-size:14px;font-weight:600;">⏰ Le conducteur a 24 heures pour répondre</p>
                    <p style="margin:0;color:#92400e;font-size:13px;">
                        Si vous ne recevez pas de réponse dans ce délai, votre demande sera automatiquement refusée et vous pourrez en faire une nouvelle.
                    </p>
                </div>
                
                <p style="margin:0;color:#4a5568;font-size:14px;text-align:center;">
                    Vous recevrez un email dès que le conducteur aura répondu.
                </p>
                
            </div>
            
            <!-- Footer -->
            <div style="text-align:center;padding:20px;background:#f8f9fa;">
                <p style="margin:0;font-size:13px;color:#999;">Carette Covoiturage</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
✅ Demande envoyée

Bonjour {passenger_name},

Votre demande de réservation a été envoyée à {driver_name}.

Trajet {trip_label}: {offer.get('departure', '')} → {offer.get('destination', '')}
Date: {offer.get('datetime', '') if trip_type == 'outbound' else offer.get('return_datetime', '')}

⏰ Le conducteur a 24 heures pour répondre.
Si pas de réponse dans ce délai, votre demande sera automatiquement refusée.

Vous recevrez un email dès qu'il aura répondu.
"""
    
    return (subject, html_body, text_body)


def email_reservation_refused(
    passenger_email: str,
    passenger_name: str,
    driver_name: str,
    offer: dict,
    trip_type: str = 'outbound'
) -> tuple:
    """
    Template : Réservation refusée par le conducteur
    """
    trip_label = "ALLER" if trip_type == 'outbound' else "RETOUR"
    
    subject = f"Demande refusée - {offer.get('departure', '')} → {offer.get('destination', '')}"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
        <div style="max-width:600px;margin:40px auto;background:white;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);overflow:hidden;">
            
            <!-- Header -->
            <div style="background:linear-gradient(135deg, #ef4444 0%, #dc2626 100%);padding:32px;text-align:center;">
                <div style="font-size:48px;margin-bottom:12px;">😔</div>
                <h1 style="color:white;margin:0;font-size:28px;font-weight:700;">Demande refusée</h1>
            </div>
            
            <!-- Body -->
            <div style="padding:32px;">
                
                <p style="margin:0 0 20px 0;color:#2d3748;font-size:16px;">
                    Bonjour <strong>{passenger_name}</strong>,
                </p>
                
                <p style="margin:0 0 20px 0;color:#4a5568;font-size:15px;">
                    Malheureusement, <strong>{driver_name}</strong> n'a pas pu accepter votre demande pour le trajet suivant :
                </p>
                
                <!-- Trajet -->
                <div style="background:#f8f9fa;padding:20px;border-radius:12px;margin-bottom:24px;border-left:4px solid #ef4444;">
                    <div style="margin-bottom:12px;">
                        <span style="display:inline-block;background:#6b7280;color:white;padding:4px 12px;border-radius:6px;font-size:12px;font-weight:700;">{trip_label}</span>
                    </div>
                    <p style="margin:0 0 8px 0;font-size:16px;color:#2d3748;">
                        {offer.get('departure', '')} → {offer.get('destination', '')}
                    </p>
                    <p style="margin:0;color:#4a5568;font-size:14px;">
                        📅 {offer.get('datetime', '') if trip_type == 'outbound' else offer.get('return_datetime', '')}
                    </p>
                </div>
                
                <p style="margin:0 0 20px 0;color:#4a5568;font-size:14px;">
                    Les raisons peuvent être multiples : véhicule complet, changement de plans, incompatibilité d'horaires...
                </p>
                
                <p style="margin:0;color:#2d3748;font-size:15px;font-weight:600;text-align:center;">
                    💡 N'hésitez pas à chercher d'autres trajets disponibles !
                </p>
                
            </div>
            
            <!-- Footer -->
            <div style="text-align:center;padding:20px;background:#f8f9fa;">
                <p style="margin:0;font-size:13px;color:#999;">Carette Covoiturage</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
Demande refusée

Bonjour {passenger_name},

Malheureusement, {driver_name} n'a pas pu accepter votre demande pour le trajet :

{trip_label}: {offer.get('departure', '')} → {offer.get('destination', '')}
Date: {offer.get('datetime', '') if trip_type == 'outbound' else offer.get('return_datetime', '')}

N'hésitez pas à chercher d'autres trajets disponibles !
"""
    
    return (subject, html_body, text_body)


def email_driver_route_updated(
    driver_email: str,
    driver_name: str,
    offer: dict,
    all_passengers: list,
    map_image_path: str = None,
    seats_available: int = 0,
    reason: str = "Nouveau passager ajouté",
    detour_outbound: int = 0,
    detour_return: int = 0,
    detour_remaining_outbound: int = None,
    detour_remaining_return: int = None,
    view_reservations_url: str = '',
    cancel_offer_url: str = '',
    base_url: str = ''
) -> tuple:
    """
    Template : Itinéraire mis à jour (envoyé au conducteur)
    Après acceptation d'un passager ou annulation
    
    Args:
        all_passengers: Liste des passagers confirmés avec leurs infos
        map_image_path: Chemin vers l'image de carte (ex: "maps/abc123.png")
        seats_available: Nombre de places restantes
        reason: Raison de la mise à jour
        detour_outbound: Détour total utilisé pour l'aller (en minutes)
        detour_return: Détour total utilisé pour le retour (en minutes)
        detour_remaining_outbound: Temps de détour restant pour l'aller (en minutes)
        detour_remaining_return: Temps de détour restant pour le retour (en minutes)
    """
    subject = f"🗺️ Itinéraire mis à jour - {len(all_passengers)} passager(s)"
    
    # Générer la liste des passagers HTML
    passengers_html = ""
    for idx, p in enumerate(all_passengers, 1):
        emoji = "1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣8️⃣"[idx-1] if idx <= 8 else f"{idx}️⃣"
        remove_url = p.get('remove_url', '#')
        passengers_html += f"""
        <div style="background:#f8f9fa;padding:16px;border-radius:8px;margin-bottom:12px;border-left:4px solid #c47cff;">
            <div style="display:flex;justify-content:space-between;align-items:start;">
                <div style="flex:1;margin-left:20px;">
                    <p style="margin:0 0 8px 0;font-size:16px;font-weight:700;color:#2d3748;">
                        {emoji} {p.get('name', 'Passager')}
                    </p>
                    <p style="margin:0 0 4px 0;font-size:13px;color:#4a5568;">
                        📍 {p.get('pickup_time', '')} - {p.get('pickup_address', '')}
                    </p>
                    <p style="margin:0;font-size:13px;color:#4a5568;">
                        📱 {p.get('phone', '')}
                    </p>
                </div>
                <a href="{remove_url}" style="display:inline-block;padding:6px 12px;background:#ef4444;color:white;text-decoration:none;border-radius:6px;font-size:12px;font-weight:600;">
                    Retirer
                </a>
            </div>
        </div>
        """
    
    # Image de carte
    map_html = ""
    if map_image_path:
        map_url = f"{base_url}/static/{map_image_path}"
        map_html = f"""
        <div style="margin:24px 0;">
            <img src="cid:map_image" alt="Carte du trajet" style="width:100%;max-width:600px;border-radius:12px;display:block;" />
        </div>
        """
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
        <div style="max-width:600px;margin:40px auto;background:white;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);overflow:hidden;">
            
            <!-- Header -->
            <div style="background:linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);padding:32px;text-align:center;">
                <div style="font-size:48px;margin-bottom:12px;">🗺️</div>
                <h1 style="color:white;margin:0;font-size:28px;font-weight:700;">Itinéraire mis à jour</h1>
                <p style="color:rgba(255,255,255,0.95);margin:8px 0 0 0;font-size:16px;">{reason}</p>
            </div>
            
            <!-- Body -->
            <div style="padding:32px;">
                
                <p style="margin:0 0 20px 0;color:#2d3748;font-size:16px;">
                    Bonjour <strong>{driver_name}</strong>,
                </p>
                
                <!-- Trajet -->
                <div style="background:#f8f9fa;padding:20px;border-radius:12px;margin-bottom:24px;">
                    <p style="margin:0 0 8px 0;font-size:18px;font-weight:700;color:#2d3748;">
                        🚗 {offer.get('departure', '')} → {offer.get('destination', '')}
                    </p>
                    <p style="margin:0 0 8px 0;font-size:14px;color:#4a5568;">
                        📅 {offer.get('datetime', '')}
                    </p>
                    <p style="margin:0{' 0 8px 0' if detour_outbound or detour_return or detour_remaining_outbound is not None or detour_remaining_return is not None else ''};font-size:14px;color:#2d3748;font-weight:600;">
                        💺 <span style="color:#10b981;">{seats_available} place(s) restante(s)</span> / {offer.get('seats', 4)}
                    </p>
                    {f'''
                    <div style="margin-top:12px;padding-top:12px;border-top:1px solid #e2e8f0;">
                        {f'<p style="margin:0 0 6px 0;font-size:14px;color:#111;font-weight:700;">➡️ ALLER</p>' if detour_outbound or detour_remaining_outbound is not None else ''}
                        {f'<p style="margin:0 0 4px 0;font-size:13px;color:#4a5568;">⏱️ Détour utilisé : <strong style="color:#f59e0b;">{detour_outbound} min</strong></p>' if detour_outbound else ''}
                        {f'<p style="margin:0 0 8px 0;font-size:13px;color:#4a5568;">🎯 Temps restant : <strong style="color:#10b981;">{detour_remaining_outbound} min</strong></p>' if detour_remaining_outbound is not None else ''}
                        {f'<p style="margin:12px 0 6px 0;font-size:14px;color:#111;font-weight:700;">⬅️ RETOUR</p>' if detour_return or detour_remaining_return is not None else ''}
                        {f'<p style="margin:0 0 4px 0;font-size:13px;color:#4a5568;">⏱️ Détour utilisé : <strong style="color:#f59e0b;">{detour_return} min</strong></p>' if detour_return else ''}
                        {f'<p style="margin:0;font-size:13px;color:#4a5568;">🎯 Temps restant : <strong style="color:#10b981;">{detour_remaining_return} min</strong></p>' if detour_remaining_return is not None else ''}
                    </div>
                    ''' if detour_outbound or detour_return or detour_remaining_outbound is not None or detour_remaining_return is not None else ''}
                </div>
                
                {map_html}
                
                <!-- Liste des passagers -->
                <h2 style="margin:24px 0 16px 0;font-size:20px;color:#2d3748;">👥 Vos passagers</h2>
                
                {passengers_html}
                
                <!-- Actions -->
                <div style="margin-top:32px;padding-top:24px;border-top:2px solid #e2e8f0;">
                    <div style="display:flex;gap:12px;margin-bottom:16px;">
                        <a href="{view_reservations_url}" style="flex:1;display:block;padding:14px;background:#3b82f6;color:white;text-align:center;text-decoration:none;border-radius:8px;font-weight:600;font-size:14px;">
                            📩 Voir les demandes en attente
                        </a>
                    </div>
                    <div style="text-align:center;">
                        <a href="{cancel_offer_url}" style="color:#ef4444;text-decoration:underline;font-size:13px;">
                            Annuler mon offre
                        </a>
                    </div>
                </div>
                
            </div>
            
            <!-- Footer -->
            <div style="text-align:center;padding:20px;background:#f8f9fa;">
                <p style="margin:0;font-size:13px;color:#999;">Carette Covoiturage</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    passengers_text = "\n".join([
        f"{idx}. {p.get('name', '')} - {p.get('pickup_time', '')} - {p.get('phone', '')}"
        for idx, p in enumerate(all_passengers, 1)
    ])
    
    text_body = f"""
🗺️ Itinéraire mis à jour

Bonjour {driver_name},

{reason}

Trajet: {offer.get('departure', '')} → {offer.get('destination', '')}
Date: {offer.get('datetime', '')}
Places restantes: {seats_available} / {offer.get('seats', 4)}

Vos passagers:
{passengers_text}

Voir les demandes: {view_reservations_url}
Annuler l'offre: {cancel_offer_url}
"""
    
    return (subject, html_body, text_body)


def email_passenger_route_updated(
    passenger_email: str,
    passenger_name: str,
    new_pickup_time: str,
    old_pickup_time: str = None,
    pickup_address: str = '',
    driver_name: str = '',
    driver_phone: str = '',
    reason: str = "Un nouveau passager a été ajouté",
    map_image_path: str = None,
    cancel_url: str = '',
    base_url: str = ''
) -> tuple:
    """
    Template : Itinéraire modifié (envoyé aux passagers existants)
    Quand l'horaire de pickup change suite à ajout/retrait d'un passager
    """
    subject = f"⚠️ Votre heure de RDV a changé"
    
    # Calcul du changement d'horaire
    time_change_html = ""
    if old_pickup_time and old_pickup_time != new_pickup_time:
        time_change_html = f"""
        <div style="background:#fef3c7;border:2px solid #f59e0b;padding:20px;border-radius:12px;margin-bottom:24px;">
            <p style="margin:0 0 12px 0;color:#78350f;font-size:16px;font-weight:700;">⏰ Changement d'horaire</p>
            <p style="margin:0;color:#92400e;font-size:14px;">
                <span style="text-decoration:line-through;">{old_pickup_time}</span>
                <span style="font-weight:700;color:#78350f;margin-left:8px;">→ {new_pickup_time}</span>
            </p>
        </div>
        """
    
    # Image de carte
    map_html = ""
    if map_image_path:
        map_html = f"""
        <div style="margin:24px 0;">
            <img src="cid:map_image" alt="Carte du trajet" style="width:100%;max-width:600px;border-radius:12px;display:block;" />
        </div>
        """
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
        <div style="max-width:600px;margin:40px auto;background:white;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);overflow:hidden;">
            
            <!-- Header -->
            <div style="background:linear-gradient(135deg, #f59e0b 0%, #d97706 100%);padding:32px;text-align:center;">
                <div style="font-size:48px;margin-bottom:12px;">⚠️</div>
                <h1 style="color:white;margin:0;font-size:28px;font-weight:700;">Itinéraire modifié</h1>
                <p style="color:rgba(255,255,255,0.95);margin:8px 0 0 0;font-size:16px;">{reason}</p>
            </div>
            
            <!-- Body -->
            <div style="padding:32px;">
                
                <p style="margin:0 0 20px 0;color:#2d3748;font-size:16px;">
                    Bonjour <strong>{passenger_name}</strong>,
                </p>
                
                <p style="margin:0 0 24px 0;color:#4a5568;font-size:15px;">
                    L'itinéraire de votre covoiturage a été modifié.
                </p>
                
                {time_change_html}
                
                <!-- Nouveau RDV -->
                <div style="background:#f8f9fa;padding:24px;border-radius:12px;margin-bottom:24px;border-left:4px solid #c47cff;">
                    <h2 style="margin:0 0 16px 0;font-size:18px;color:#2d3748;">📍 Votre rendez-vous</h2>
                    <p style="margin:0 0 8px 0;font-size:16px;font-weight:700;color:#2d3748;">
                        🕐 {new_pickup_time}
                    </p>
                    <p style="margin:0;font-size:14px;color:#4a5568;">
                        📍 {pickup_address}
                    </p>
                </div>
                
                {map_html}
                
                <!-- Conducteur -->
                <div style="background:#f8f9fa;padding:20px;border-radius:12px;margin-bottom:24px;">
                    <h3 style="margin:0 0 12px 0;font-size:16px;color:#2d3748;">🚗 Conducteur</h3>
                    <p style="margin:0 0 4px 0;font-size:15px;font-weight:600;color:#2d3748;">{driver_name}</p>
                    <p style="margin:0;font-size:14px;color:#4a5568;">📱 {driver_phone}</p>
                    <a href="https://wa.me/{driver_phone.replace(' ', '').replace('+', '')}" style="display:inline-block;margin-top:12px;padding:10px 20px;background:#25d366;color:white;text-decoration:none;border-radius:8px;font-size:14px;font-weight:600;">
                        💬 WhatsApp
                    </a>
                </div>
                
                <!-- Annulation -->
                <div style="text-align:center;margin-top:24px;">
                    <a href="{cancel_url}" style="display:inline-block;padding:12px 28px;background:#ef4444;color:white;text-decoration:none;border-radius:8px;font-size:14px;font-weight:600;">
                        ✗ Annuler ma réservation
                    </a>
                    <p style="margin:12px 0 0 0;font-size:12px;color:#999;">
                        (Possible jusqu'à 24h avant le départ)
                    </p>
                </div>
                
            </div>
            
            <!-- Footer -->
            <div style="text-align:center;padding:20px;background:#f8f9fa;">
                <p style="margin:0;font-size:13px;color:#999;">Carette Covoiturage</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
⚠️ Itinéraire modifié

Bonjour {passenger_name},

{reason}

Votre nouveau rendez-vous:
🕐 {new_pickup_time}
📍 {pickup_address}

Conducteur: {driver_name}
📱 {driver_phone}

Annuler: {cancel_url}
(Possible jusqu'à 24h avant)
"""
    
    return (subject, html_body, text_body)


def email_cancellation_confirmed_passenger(
    passenger_email: str,
    passenger_name: str,
    offer: dict
) -> tuple:
    """
    Template : Confirmation d'annulation par le passager
    """
    subject = f"✅ Annulation confirmée"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
        <div style="max-width:600px;margin:40px auto;background:white;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);overflow:hidden;">
            
            <!-- Header -->
            <div style="background:linear-gradient(135deg, #10b981 0%, #059669 100%);padding:32px;text-align:center;">
                <div style="font-size:48px;margin-bottom:12px;">✅</div>
                <h1 style="color:white;margin:0;font-size:28px;font-weight:700;">Annulation confirmée</h1>
            </div>
            
            <!-- Body -->
            <div style="padding:32px;">
                
                <p style="margin:0 0 20px 0;color:#2d3748;font-size:16px;">
                    Bonjour <strong>{passenger_name}</strong>,
                </p>
                
                <p style="margin:0 0 24px 0;color:#4a5568;font-size:15px;">
                    Votre réservation a bien été annulée pour le trajet suivant :
                </p>
                
                <!-- Trajet -->
                <div style="background:#f8f9fa;padding:20px;border-radius:12px;margin-bottom:24px;border-left:4px solid #6b7280;">
                    <p style="margin:0 0 8px 0;font-size:16px;color:#2d3748;">
                        {offer.get('departure', '')} → {offer.get('destination', '')}
                    </p>
                    <p style="margin:0;color:#4a5568;font-size:14px;">
                        📅 {offer.get('datetime', '')}
                    </p>
                </div>
                
                <p style="margin:0;color:#4a5568;font-size:14px;">
                    Le conducteur et les autres passagers ont été prévenus. L'itinéraire a été recalculé.
                </p>
                
            </div>
            
            <!-- Footer -->
            <div style="text-align:center;padding:20px;background:#f8f9fa;">
                <p style="margin:0;font-size:13px;color:#999;">Carette Covoiturage</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
✅ Annulation confirmée

Bonjour {passenger_name},

Votre réservation a bien été annulée:

{offer.get('departure', '')} → {offer.get('destination', '')}
📅 {offer.get('datetime', '')}

Le conducteur et les autres passagers ont été prévenus.
"""
    
    return (subject, html_body, text_body)


def email_offer_cancelled_by_driver(
    passenger_email: str,
    passenger_name: str,
    driver_name: str,
    offer: dict
) -> tuple:
    """
    Template : Trajet annulé par le conducteur
    Envoyé à tous les passagers confirmés
    """
    subject = f"❌ Trajet annulé par le conducteur"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
        <div style="max-width:600px;margin:40px auto;background:white;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);overflow:hidden;">
            
            <!-- Header -->
            <div style="background:linear-gradient(135deg, #ef4444 0%, #dc2626 100%);padding:32px;text-align:center;">
                <div style="font-size:48px;margin-bottom:12px;">❌</div>
                <h1 style="color:white;margin:0;font-size:28px;font-weight:700;">Trajet annulé</h1>
            </div>
            
            <!-- Body -->
            <div style="padding:32px;">
                
                <p style="margin:0 0 20px 0;color:#2d3748;font-size:16px;">
                    Bonjour <strong>{passenger_name}</strong>,
                </p>
                
                <p style="margin:0 0 24px 0;color:#4a5568;font-size:15px;">
                    Nous sommes désolés de vous informer que <strong>{driver_name}</strong> a dû annuler le trajet suivant :
                </p>
                
                <!-- Trajet -->
                <div style="background:#fee2e2;padding:20px;border-radius:12px;margin-bottom:24px;border-left:4px solid #ef4444;">
                    <p style="margin:0 0 8px 0;font-size:16px;font-weight:600;color:#991b1b;">
                        {offer.get('departure', '')} → {offer.get('destination', '')}
                    </p>
                    <p style="margin:0;color:#7f1d1d;font-size:14px;">
                        📅 {offer.get('datetime', '')}
                    </p>
                </div>
                
                <p style="margin:0 0 20px 0;color:#4a5568;font-size:14px;">
                    Les imprévus peuvent arriver à tout le monde. Nous vous invitons à rechercher un autre covoiturage pour votre trajet.
                </p>
                
                <div style="background:#f8f9fa;padding:20px;border-radius:8px;text-align:center;">
                    <p style="margin:0;color:#2d3748;font-size:15px;font-weight:600;">
                        💡 Cherchez d'autres trajets disponibles
                    </p>
                </div>
                
            </div>
            
            <!-- Footer -->
            <div style="text-align:center;padding:20px;background:#f8f9fa;">
                <p style="margin:0;font-size:13px;color:#999;">Carette Covoiturage</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
❌ Trajet annulé par le conducteur

Bonjour {passenger_name},

Nous sommes désolés, {driver_name} a dû annuler le trajet:

{offer.get('departure', '')} → {offer.get('destination', '')}
📅 {offer.get('datetime', '')}

Nous vous invitons à rechercher un autre covoiturage.
"""
    
    return (subject, html_body, text_body)


def email_request_expired(
    passenger_email: str,
    passenger_name: str,
    driver_name: str,
    offer: dict
) -> tuple:
    """
    Template : Demande expirée (timeout 24h)
    Envoyé au passager quand le conducteur n'a pas répondu dans les 24h
    """
    subject = f"⏰ Demande expirée - Pas de réponse"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
        <div style="max-width:600px;margin:40px auto;background:white;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);overflow:hidden;">
            
            <!-- Header -->
            <div style="background:linear-gradient(135deg, #6b7280 0%, #4b5563 100%);padding:32px;text-align:center;">
                <div style="font-size:48px;margin-bottom:12px;">⏰</div>
                <h1 style="color:white;margin:0;font-size:28px;font-weight:700;">Demande expirée</h1>
            </div>
            
            <!-- Body -->
            <div style="padding:32px;">
                
                <p style="margin:0 0 20px 0;color:#2d3748;font-size:16px;">
                    Bonjour <strong>{passenger_name}</strong>,
                </p>
                
                <p style="margin:0 0 24px 0;color:#4a5568;font-size:15px;">
                    Votre demande de réservation pour le trajet ci-dessous a expiré, car <strong>{driver_name}</strong> n'a pas répondu dans les 24 heures.
                </p>
                
                <!-- Trajet -->
                <div style="background:#f8f9fa;padding:20px;border-radius:12px;margin-bottom:24px;border-left:4px solid #6b7280;">
                    <p style="margin:0 0 8px 0;font-size:16px;color:#2d3748;">
                        {offer.get('departure', '')} → {offer.get('destination', '')}
                    </p>
                    <p style="margin:0;color:#4a5568;font-size:14px;">
                        📅 {offer.get('datetime', '')}
                    </p>
                </div>
                
                <p style="margin:0 0 20px 0;color:#4a5568;font-size:14px;">
                    Cela peut arriver si le conducteur n'a pas consulté ses emails ou est indisponible.
                </p>
                
                <div style="background:#dbeafe;border:1px solid #3b82f6;padding:20px;border-radius:8px;text-align:center;">
                    <p style="margin:0 0 8px 0;color:#1e40af;font-size:15px;font-weight:600;">
                        💡 Vous pouvez faire une nouvelle demande
                    </p>
                    <p style="margin:0;color:#1e3a8a;font-size:13px;">
                        Ou chercher d'autres trajets disponibles
                    </p>
                </div>
                
            </div>
            
            <!-- Footer -->
            <div style="text-align:center;padding:20px;background:#f8f9fa;">
                <p style="margin:0;font-size:13px;color:#999;">Carette Covoiturage</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
⏰ Demande expirée

Bonjour {passenger_name},

Votre demande pour le trajet ci-dessous a expiré (pas de réponse du conducteur dans les 24h):

{offer.get('departure', '')} → {offer.get('destination', '')}
📅 {offer.get('datetime', '')}

Vous pouvez faire une nouvelle demande ou chercher d'autres trajets.
"""
    
    return (subject, html_body, text_body)


def email_reminder_24h(
    recipient_email: str,
    recipient_name: str,
    role: str,  # 'driver' ou 'passenger'
    offer: dict,
    pickup_time: str = None,
    pickup_address: str = None,
    passengers: list = None,
    driver_name: str = None,
    driver_phone: str = None,
    cancel_url: str = '',
    view_reservations_url: str = ''
) -> tuple:
    """
    Template : Rappel J-1 avant le départ
    Envoyé au conducteur avec liste des passagers
    Envoyé aux passagers avec infos de RDV
    """
    
    if role == 'driver':
        subject = f"🔔 Demain : {len(passengers)} passager(s) vous attend(ent)"
        
        passengers_html = ""
        for idx, p in enumerate(passengers, 1):
            emoji = "1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣8️⃣"[idx-1] if idx <= 8 else f"{idx}️⃣"
            passengers_html += f"""
            <div style="background:#f8f9fa;padding:16px;border-radius:8px;margin-bottom:12px;border-left:4px solid #c47cff;">
                <p style="margin:0 0 8px 0;font-size:16px;font-weight:700;color:#2d3748;">
                    {emoji} {p.get('name', 'Passager')}
                </p>
                <p style="margin:0 0 4px 0;font-size:13px;color:#4a5568;">
                    📍 {p.get('pickup_time', '')} - {p.get('pickup_address', '')}
                </p>
                <p style="margin:0;font-size:13px;color:#4a5568;">
                    📱 {p.get('phone', '')}
                </p>
            </div>
            """
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
            <div style="max-width:600px;margin:40px auto;background:white;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);overflow:hidden;">
                
                <!-- Header -->
                <div style="background:linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);padding:32px;text-align:center;">
                    <div style="font-size:48px;margin-bottom:12px;">🔔</div>
                    <h1 style="color:white;margin:0;font-size:28px;font-weight:700;">Rappel : Demain c'est le grand départ !</h1>
                </div>
                
                <!-- Body -->
                <div style="padding:32px;">
                    
                    <p style="margin:0 0 20px 0;color:#2d3748;font-size:16px;">
                        Bonjour <strong>{recipient_name}</strong>,
                    </p>
                    
                    <p style="margin:0 0 24px 0;color:#4a5568;font-size:15px;">
                        Votre covoiturage a lieu <strong>demain</strong> !
                    </p>
                    
                    <!-- Trajet -->
                    <div style="background:#f8f9fa;padding:20px;border-radius:12px;margin-bottom:24px;">
                        <p style="margin:0 0 8px 0;font-size:18px;font-weight:700;color:#2d3748;">
                            🚗 {offer.get('departure', '')} → {offer.get('destination', '')}
                        </p>
                        <p style="margin:0;color:#4a5568;font-size:14px;">
                            📅 {offer.get('datetime', '')}
                        </p>
                    </div>
                    
                    <!-- Passagers -->
                    <h2 style="margin:24px 0 16px 0;font-size:20px;color:#2d3748;">👥 Vos passagers</h2>
                    
                    {passengers_html}
                    
                    <!-- Actions -->
                    <div style="margin-top:32px;padding-top:24px;border-top:2px solid #e2e8f0;">
                        <div style="background:#fef3c7;border:2px solid #f59e0b;padding:20px;border-radius:12px;text-align:center;">
                            <p style="margin:0 0 8px 0;color:#78350f;font-size:15px;font-weight:700;">
                                ⚠️ Dernier moment pour annuler
                            </p>
                            <p style="margin:0;color:#92400e;font-size:13px;">
                                Après cette période, il ne sera plus possible d'annuler
                            </p>
                        </div>
                        
                        <div style="text-align:center;margin-top:20px;">
                            <a href="{view_reservations_url}" style="display:inline-block;padding:14px 28px;background:#3b82f6;color:white;text-decoration:none;border-radius:8px;font-weight:600;font-size:14px;">
                                📩 Voir les détails
                            </a>
                        </div>
                    </div>
                    
                </div>
                
                <!-- Footer -->
                <div style="text-align:center;padding:20px;background:#f8f9fa;">
                    <p style="margin:0;font-size:13px;color:#999;">Carette Covoiturage</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        passengers_text = "\n".join([
            f"{idx}. {p.get('name', '')} - {p.get('pickup_time', '')} - {p.get('phone', '')}"
            for idx, p in enumerate(passengers, 1)
        ])
        
        text_body = f"""
🔔 Rappel : Demain c'est le grand départ !

Bonjour {recipient_name},

Votre covoiturage a lieu demain !

Trajet: {offer.get('departure', '')} → {offer.get('destination', '')}
Date: {offer.get('datetime', '')}

Vos passagers:
{passengers_text}

⚠️ Dernier moment pour annuler

Voir les détails: {view_reservations_url}
"""
    
    else:  # passenger
        subject = f"🔔 Demain : RDV à {pickup_time}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
            <div style="max-width:600px;margin:40px auto;background:white;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);overflow:hidden;">
                
                <!-- Header -->
                <div style="background:linear-gradient(135deg, #10b981 0%, #059669 100%);padding:32px;text-align:center;">
                    <div style="font-size:48px;margin-bottom:12px;">🔔</div>
                    <h1 style="color:white;margin:0;font-size:28px;font-weight:700;">Rappel : Demain c'est le grand jour !</h1>
                </div>
                
                <!-- Body -->
                <div style="padding:32px;">
                    
                    <p style="margin:0 0 20px 0;color:#2d3748;font-size:16px;">
                        Bonjour <strong>{recipient_name}</strong>,
                    </p>
                    
                    <p style="margin:0 0 24px 0;color:#4a5568;font-size:15px;">
                        Votre covoiturage a lieu <strong>demain</strong> !
                    </p>
                    
                    <!-- RDV -->
                    <div style="background:#f8f9fa;padding:24px;border-radius:12px;margin-bottom:24px;border-left:4px solid #c47cff;">
                        <h2 style="margin:0 0 16px 0;font-size:18px;color:#2d3748;">�� Votre rendez-vous</h2>
                        <p style="margin:0 0 8px 0;font-size:18px;font-weight:700;color:#2d3748;">
                            🕐 {pickup_time}
                        </p>
                        <p style="margin:0;font-size:14px;color:#4a5568;">
                            📍 {pickup_address}
                        </p>
                    </div>
                    
                    <!-- Trajet -->
                    <div style="background:#f8f9fa;padding:20px;border-radius:12px;margin-bottom:24px;">
                        <p style="margin:0 0 8px 0;font-size:16px;color:#2d3748;">
                            🚗 {offer.get('departure', '')} → {offer.get('destination', '')}
                        </p>
                        <p style="margin:0;color:#4a5568;font-size:14px;">
                            📅 {offer.get('datetime', '')}
                        </p>
                    </div>
                    
                    <!-- Conducteur -->
                    <div style="background:#f8f9fa;padding:20px;border-radius:12px;margin-bottom:24px;">
                        <h3 style="margin:0 0 12px 0;font-size:16px;color:#2d3748;">🚗 Conducteur</h3>
                        <p style="margin:0 0 4px 0;font-size:15px;font-weight:600;color:#2d3748;">{driver_name}</p>
                        <p style="margin:0;font-size:14px;color:#4a5568;">📱 {driver_phone}</p>
                        <a href="https://wa.me/{driver_phone.replace(' ', '').replace('+', '')}" style="display:inline-block;margin-top:12px;padding:10px 20px;background:#25d366;color:white;text-decoration:none;border-radius:8px;font-size:14px;font-weight:600;">
                            💬 WhatsApp
                        </a>
                    </div>
                    
                    <!-- Avertissement -->
                    <div style="background:#fef3c7;border:2px solid #f59e0b;padding:20px;border-radius:12px;text-align:center;">
                        <p style="margin:0 0 8px 0;color:#78350f;font-size:15px;font-weight:700;">
                            ⚠️ Trop tard pour annuler
                        </p>
                        <p style="margin:0;color:#92400e;font-size:13px;">
                            Le délai d'annulation de 24h est dépassé
                        </p>
                    </div>
                    
                </div>
                
                <!-- Footer -->
                <div style="text-align:center;padding:20px;background:#f8f9fa;">
                    <p style="margin:0;font-size:13px;color:#999;">Carette Covoiturage</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
🔔 Rappel : Demain c'est le grand jour !

Bonjour {recipient_name},

Votre covoiturage a lieu demain !

Rendez-vous:
🕐 {pickup_time}
📍 {pickup_address}

Trajet: {offer.get('departure', '')} → {offer.get('destination', '')}

Conducteur: {driver_name}
📱 {driver_phone}

⚠️ Trop tard pour annuler (délai 24h dépassé)
"""
    
    return (subject, html_body, text_body)


def email_recurrent_offer_published(driver_email: str, driver_name: str, offer: dict, base_url: str = 'http://51.178.30.246:9000') -> tuple:
    """
    Email de confirmation après création d'offre récurrente B2B
    Returns: (subject, html_body, text_body)
    """
    departure = offer.get('departure', '')
    destination = offer.get('destination', '')
    time_outbound = offer.get('time_outbound', '')
    time_return = offer.get('time_return', '')
    seats = offer.get('seats', 4)
    max_detour = offer.get('max_detour_time', 5)
    offer_id = offer.get('offer_id', 0)
    
    # Récupérer les coordonnées et routes
    departure_coords = offer.get('departure_coords')
    destination_coords = offer.get('destination_coords')
    route_outbound = offer.get('route_outbound')
    route_return = offer.get('route_return')
    
    # Couleurs définies par l'utilisateur dans le widget
    color_outbound = offer.get('color_outbound', '#7c3aed')
    color_return = offer.get('color_return', '#f97316')
    
    import json
    if isinstance(departure_coords, str):
        try:
            departure_coords = json.loads(departure_coords)
        except:
            departure_coords = None
    
    if isinstance(destination_coords, str):
        try:
            destination_coords = json.loads(destination_coords)
        except:
            destination_coords = None
    
    # Créer l'encart Google Maps
    map_html = ""
    if departure_coords and destination_coords:
        dep_lat = departure_coords.get('lat', 0) if isinstance(departure_coords, dict) else departure_coords[1]
        dep_lon = departure_coords.get('lon', 0) if isinstance(departure_coords, dict) else departure_coords[0]
        dest_lat = destination_coords.get('lat', 0) if isinstance(destination_coords, dict) else destination_coords[1]
        dest_lon = destination_coords.get('lon', 0) if isinstance(destination_coords, dict) else destination_coords[0]
        gmaps_url = f"https://www.google.com/maps/dir/{dep_lat},{dep_lon}/{dest_lat},{dest_lon}"
        
        map_html = f'''
            <div style="margin-bottom:24px;background:{color_outbound};border-radius:12px;padding:20px;text-align:center;box-shadow:0 4px 12px rgba(0,0,0,0.15);">
                <div style="font-size:16px;font-weight:700;color:#fff;margin-bottom:12px;">🗺️ Visualiser l'itinéraire</div>
                <a href="{gmaps_url}" target="_blank" style="display:inline-block;background:#fff;color:{color_outbound};text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:700;font-size:15px;box-shadow:0 2px 6px rgba(0,0,0,0.15);">
                    📍 Ouvrir dans Google Maps
                </a>
                <div style="margin-top:12px;font-size:13px;color:rgba(255,255,255,0.9);">{departure} ↔ {destination}</div>
            </div>
        '''
    
    # Badges de jours de la semaine
    days_badges = ""
    days_data = [
        ('monday', 'Lun'),
        ('tuesday', 'Mar'),
        ('wednesday', 'Mer'),
        ('thursday', 'Jeu'),
        ('friday', 'Ven'),
        ('saturday', 'Sam'),
        ('sunday', 'Dim')
    ]
    
    for day_en, day_abbr in days_data:
        is_selected = offer.get(day_en, False)
        bg_color = color_outbound if is_selected else '#e5e7eb'
        text_color = '#fff' if is_selected else '#9ca3af'
        font_weight = '700' if is_selected else '500'
        
        days_badges += f'''
            <div style="display:inline-block;background:{bg_color};color:{text_color};padding:8px 12px;border-radius:8px;margin:4px;font-size:13px;font-weight:{font_weight};min-width:45px;text-align:center;">
                {day_abbr}
            </div>
        '''
    
    # Indicateurs de places (toutes vertes = disponibles)
    seat_icons = ""
    for i in range(seats):
        seat_icons += f'<span style="display:inline-block;width:18px;height:18px;border-radius:4px;margin-right:4px;background:#10b981;"></span>'
    
    # Calculer les heures de départ/arrivée à partir de la durée de route
    # Pour l'aller : arrivée = time_outbound, départ = arrivée - durée
    # Pour le retour : départ = time_return, arrivée = départ + durée
    
    duration_outbound_min = 0
    duration_return_min = 0
    
    if route_outbound and isinstance(route_outbound, dict):
        duration_outbound_min = int(route_outbound.get('duration', 0) / 60)
    
    if route_return and isinstance(route_return, dict):
        duration_return_min = int(route_return.get('duration', 0) / 60)
    
    # Formater les heures
    from datetime import datetime, timedelta
    
    # ALLER : arrivée connue, calculer départ
    try:
        arrival_outbound = datetime.strptime(time_outbound, '%H:%M')
        departure_outbound = arrival_outbound - timedelta(minutes=duration_outbound_min)
        time_departure_outbound = departure_outbound.strftime('%H:%M')
        time_arrival_outbound = time_outbound
    except:
        time_departure_outbound = "—"
        time_arrival_outbound = time_outbound
    
    # RETOUR : départ connu, calculer arrivée
    try:
        departure_return_time = datetime.strptime(time_return, '%H:%M')
        arrival_return = departure_return_time + timedelta(minutes=duration_return_min)
        time_departure_return = time_return
        time_arrival_return = arrival_return.strftime('%H:%M')
    except:
        time_departure_return = time_return
        time_arrival_return = "—"
    
    # Timeline ALLER
    timeline_aller = f'''
        <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
            <div style="display:flex;flex-direction:column;align-items:center;">
                <div style="width:32px;height:32px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏠</div>
                <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
            </div>
            <div style="flex:1;margin-left:20px;">
                <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:2px;">Départ</div>
                <div style="font-weight:700;color:#111;font-size:14px;margin-bottom:2px;">{time_departure_outbound}</div>
                <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{departure}</div>
            </div>
        </div>
        <div style="display:flex;align-items:flex-start;">
            <div style="display:flex;flex-direction:column;align-items:center;">
                <div style="width:32px;height:32px;border-radius:50%;background:#10b981;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏢</div>
            </div>
            <div style="flex:1;margin-left:20px;">
                <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:2px;">Arrivée</div>
                <div style="font-weight:700;color:#111;font-size:14px;margin-bottom:2px;">{time_arrival_outbound}</div>
                <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{destination}</div>
            </div>
        </div>
    '''
    
    # Timeline RETOUR
    timeline_retour = f'''
        <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
            <div style="display:flex;flex-direction:column;align-items:center;">
                <div style="width:32px;height:32px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏢</div>
                <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
            </div>
            <div style="flex:1;margin-left:20px;">
                <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:2px;">Départ</div>
                <div style="font-weight:700;color:#111;font-size:14px;margin-bottom:2px;">{time_departure_return}</div>
                <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{destination}</div>
            </div>
        </div>
        <div style="display:flex;align-items:flex-start;">
            <div style="display:flex;flex-direction:column;align-items:center;">
                <div style="width:32px;height:32px;border-radius:50%;background:#10b981;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏠</div>
            </div>
            <div style="flex:1;margin-left:20px;">
                <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:2px;">Arrivée</div>
                <div style="font-weight:700;color:#111;font-size:14px;margin-bottom:2px;">{time_arrival_return}</div>
                <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{departure}</div>
            </div>
        </div>
    '''
    
    subject = f"✅ Votre covoiturage récurrent {departure} ↔ {destination} est publié"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif;">
        <div style="max-width:800px;margin:40px auto;padding:20px;">
            <h2 style="color:{color_outbound};text-align:center;margin-bottom:8px;">🚗 Covoiturage récurrent publié !</h2>
            <p style="text-align:center;color:#666;margin-bottom:32px;font-size:15px;">Bonjour {driver_name}, votre trajet est maintenant visible par vos collègues.</p>
            
            {map_html}
            
            <!-- Carte récapitulative -->
            <div style="background:#fff;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.12);padding:24px;margin-bottom:24px;">
                <!-- En-tête conducteur -->
                <div style="margin-bottom:20px;padding-bottom:16px;border-top:4px solid {color_outbound};padding-top:16px;">
                    <div style="font-size:20px;font-weight:700;color:#111;margin-bottom:6px;">🚗 {driver_name}</div>
                    <div style="font-size:14px;color:#666;">✉️ {driver_email}</div>
                </div>
                
                <!-- Jours de la semaine -->
                <div style="background:#f8f9fa;border-radius:10px;padding:16px;margin-bottom:20px;text-align:center;">
                    <div style="font-size:14px;font-weight:700;color:#666;margin-bottom:12px;">📅 JOURS DE COVOITURAGE</div>
                    {days_badges}
                </div>
                
                <!-- Tableau Aller / Retour -->
                <div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:10px;padding:10px;margin-bottom:20px;">
                    
                    <!-- ALLER -->
                    <div style="display:inline-block;width:49%;min-width:260px;max-width:100%;vertical-align:top;margin-bottom:16px;padding-right:1%;">
                        <div style="font-size:14px;font-weight:700;color:{color_outbound};margin-bottom:8px;">➡️ ALLER</div>
                        <div style="margin-bottom:8px;">{seat_icons}</div>
                        {detour_progress_bar(max_detour, max_detour)}
                        <div style="background:#fff;border-radius:8px;padding:10px;margin-top:8px;overflow:hidden;">
                            {timeline_aller}
                        </div>
                    </div>
                    
                    <!-- RETOUR -->
                    <div style="display:inline-block;width:49%;min-width:260px;max-width:100%;vertical-align:top;margin-bottom:16px;">
                        <div style="font-size:14px;font-weight:700;color:{color_return};margin-bottom:8px;">⬅️ RETOUR</div>
                        <div style="margin-bottom:8px;">{seat_icons}</div>
                        {detour_progress_bar(max_detour, max_detour)}
                        <div style="background:#fff;border-radius:8px;padding:10px;margin-top:8px;overflow:hidden;">
                            {timeline_retour}
                        </div>
                    </div>
                    
                </div>
                
                <!-- Section Collègues -->
                <div style="border:1px solid #dee2e6;border-radius:8px;padding:20px;background:#fafafa;">
                    <div style="font-size:16px;font-weight:700;color:#111;margin-bottom:12px;">👥 Vos collègues</div>
                    <div style="text-align:center;color:#999;padding:20px;font-size:14px;">
                        Aucune réservation pour le moment.<br/>
                        <span style="font-weight:600;color:#666;">Vous recevrez un email dès qu'un collègue réservera !</span>
                    </div>
                </div>
            </div>
            
            <!-- Bouton de désactivation -->
            <div style="text-align:center;padding:24px;background:white;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.08);margin-bottom:16px;">
                <p style="color:#666;margin-bottom:16px;font-size:15px;">Vous souhaitez arrêter cette offre de covoiturage ?</p>
                <a href="{base_url}/api/v2/offers/recurrent/{offer_id}/cancel" target="_blank" style="display:inline-block;background:#ef4444;color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:700;font-size:15px;box-shadow:0 2px 6px rgba(239,68,68,0.3);">
                    🛑 Désactiver cette offre
                </a>
                <p style="font-size:12px;color:#999;margin-top:12px;">Une fois désactivée, l'offre n'apparaîtra plus dans les recherches</p>
            </div>
            
            <!-- Info pratique -->
            <div style="text-align:center;padding:24px;background:white;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                <p style="color:#666;margin-bottom:16px;font-size:15px;">📧 Vous recevrez un email avec les détails à chaque nouvelle réservation.</p>
                <p style="font-size:13px;color:#999;margin-top:24px;">Cet email a été envoyé automatiquement par Carette Covoiturage</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Construire la liste des jours pour le texte
    days_list = []
    for day_en, day_abbr in days_data:
        if offer.get(day_en):
            days_list.append(day_abbr)
    days_text = ', '.join(days_list) if days_list else 'Aucun jour'
    
    text_body = f"""
Covoiturage récurrent publié !

Bonjour {driver_name},

Votre offre de covoiturage récurrent a bien été enregistrée.

📅 JOURS
{days_text}

➡️ ALLER
{departure} → {destination}
Départ: {time_departure_outbound}
Arrivée: {time_arrival_outbound}

⬅️ RETOUR
{destination} → {departure}
Départ: {time_departure_return}
Arrivée: {time_arrival_return}

👥 Places: {seats}
⏱️ Détour max: {max_detour} min

Vous recevrez un email dès qu'un collègue réservera.

L'équipe Carette
"""
    
    return (subject, html_body, text_body)
