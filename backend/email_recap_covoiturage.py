"""
Template d'email simple pour récapituler un covoiturage avec passagers
"""
import urllib.parse

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
    Encarts Aller/Retour avec Google Maps et Waze, style encart.
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

def create_passengers_contact_card(reservations: list, color: str = "#10b981", base_url: str = None) -> str:
    """
    Crée un encart avec les coordonnées de tous les passagers
    """
    if not reservations:
        return ""
    
    passengers_html = ""
    for res in reservations:
        remove_url = f"{base_url}/api/v2/reservations/recurrent/{res['id']}/remove?token={res.get('confirmation_token', '')}" if base_url else ""
        remove_button = f'<a href="{remove_url}" style="color:#dc2626;text-decoration:none;font-size:18px;padding:6px 12px;border-radius:6px;background:#fee2e2;border:1px solid #fca5a5;display:inline-block;margin-left:12px;font-weight:600;" title="Retirer ce passager">❌ Retirer</a>' if remove_url else ''
        
        passengers_html += f"""
        <div style="padding:16px;background:#fff;border-radius:8px;margin-bottom:12px;border:1px solid #e5e7eb;display:flex;justify-content:space-between;align-items:center;">
            <div style="flex:1;">
                <div style="font-size:16px;font-weight:700;color:#111;margin-bottom:8px;">👤 {res['passenger_name']}</div>
                <div style="font-size:14px;color:#666;margin-bottom:4px;">✉️ {res['passenger_email']}</div>
                {f'<div style="font-size:14px;color:#666;">📱 {res["passenger_phone"]}</div>' if res.get('passenger_phone') else ''}
            </div>
            {remove_button}
        </div>
        """
    
    return f"""
    <div style="background:#fff;border-radius:16px;box-shadow:0 4px 16px rgba(0,0,0,0.1);padding:24px;margin-bottom:24px;border-top:4px solid {color};">
        <div style="font-size:18px;font-weight:700;color:#111;margin-bottom:16px;">👥 Vos passagers</div>
        {passengers_html}
    </div>
    """

def generate_covoiturage_recap_email(
    offer_data: dict,
    reservations: list,
    email_type: str = 'accepted',  # 'accepted', 'rejected' ou 'updated'
    base_url: str = 'http://localhost:9000'
):
    """
    Génère un email de récapitulatif du covoiturage avec les passagers intégrés
    Affiche un itinéraire par jour avec les passagers actifs ce jour-là
    """
    from datetime import datetime, timedelta
    import urllib.parse
    
    driver_name = offer_data['driver_name']
    
    # Titre et intro selon le type
    if email_type == 'updated':
        if len(reservations) == 0:
            subject = f"🔄 Itinéraire actualisé - Plus aucun passager"
            intro_text = "Tous vos passagers ont été retirés. Votre trajet est maintenant direct."
            header_title = "🔄 Itinéraire actualisé"
            header_color = "#f59e0b"
        elif len(reservations) == 1:
            subject = f"🔄 Itinéraire actualisé avec {reservations[0]['passenger_name']}"
            intro_text = f"Un passager a été retiré. Il vous reste : <strong>{reservations[0]['passenger_name']}</strong>"
            header_title = "🔄 Itinéraire actualisé"
            header_color = "#f59e0b"
        else:
            passenger_names = ', '.join([r['passenger_name'] for r in reservations])
            subject = f"🔄 Itinéraire actualisé avec {len(reservations)} passagers"
            intro_text = f"Un passager a été retiré. Il vous reste : <strong>{passenger_names}</strong>"
            header_title = "🔄 Itinéraire actualisé"
            header_color = "#f59e0b"
    elif email_type == 'accepted':
        if len(reservations) == 1:
            subject = f"✅ Réservation confirmée avec {reservations[0]['passenger_name']}"
            intro_text = f"Vous avez accepté <strong>{reservations[0]['passenger_name']}</strong>. Voici votre covoiturage actualisé."
            header_title = "✅ Covoiturage confirmé"
            header_color = "#10b981"
        else:
            # Générer les coches visuelles selon le nombre de passagers
            checkmarks = "✅ " * len(reservations)
            passenger_names = ', '.join([r['passenger_name'] for r in reservations])
            subject = f"{checkmarks}Vos nouveaux itinéraires avec {len(reservations)} passagers"
            intro_text = f"Récapitulatif de votre covoiturage avec : <strong>{passenger_names}</strong>"
            header_title = f"{checkmarks}Vos nouveaux itinéraires"
            header_color = offer_data.get('color_outbound', '#7c3aed')
    else:
        subject = f"❌ Demande refusée - {reservations[0]['passenger_name']}"
        intro_text = f"Vous avez refusé <strong>{reservations[0]['passenger_name']}</strong>. Voici le récapitulatif."
        header_title = "❌ Demande refusée"
        header_color = "#ef4444"
    
    # Couleurs
    color_outbound = offer_data.get('color_outbound', '#7c3aed')
    color_return = offer_data.get('color_return', '#f97316')
    
    if color_outbound and len(color_outbound) == 9:
        color_outbound = color_outbound[:7]
    if color_return and len(color_return) == 9:
        color_return = color_return[:7]
    
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
    
    # Générer les sections par jour
    days_sections = ""
    
    for day_en, (day_full, day_abbr) in day_names.items():
        # Vérifier si l'offre est active ce jour (support 2 formats)
        if 'days' in offer_data:
            is_offer_active = offer_data['days'].get(day_en, False)
        else:
            is_offer_active = offer_data.get(day_en, False)
        
        if not is_offer_active:
            continue
        
        # Filtrer les passagers actifs ce jour (les jours sont maintenant directement dans r, pas dans r['days'])
        passengers_today = [r for r in reservations if r.get(day_en, False)]
        
        # Si aucun passager ce jour, afficher itinéraire solo
        if not passengers_today:
            days_sections += f'''
            <div style="background:#fff;border-radius:16px;box-shadow:0 4px 16px rgba(0,0,0,0.1);padding:24px;margin-bottom:24px;border:2px solid #f0f0f0;">
                <div style="display:inline-block;background:#fff;color:#111;padding:10px 24px;border-radius:20px;font-size:15px;font-weight:700;margin-bottom:20px;border:2px solid #e5e7eb;">
                    📅 {day_full.upper()}
                </div>
                <div style="text-align:center;padding:32px;background:#f8f9fa;border-radius:12px;border:2px dashed #d1d5db;">
                    <div style="font-size:48px;margin-bottom:12px;opacity:0.5;">🚗</div>
                    <div style="color:#6b7280;font-size:15px;font-weight:600;">Aucun passager ce jour-là</div>
                    <div style="color:#9ca3af;font-size:13px;margin-top:4px;">Trajet solo</div>
                </div>
            </div>
            '''
            continue
        
        # Déterminer heure de départ la plus tôt basée sur pickups (chronologie)
        dep_time_val = offer_data['departure_time']
        computed_dep_times = [r.get('computed_departure_time') for r in passengers_today if r.get('computed_departure_time')]
        if computed_dep_times:
            try:
                dep_time_val = min(computed_dep_times)
            except Exception:
                pass
        dep_time_str = dep_time_val.strftime('%H:%M')
        
        # Grouper les passagers qui montent au départ (UNIQUEMENT par adresse)
        departure_address = offer_data['departure'].lower().strip()
        passengers_at_departure = []
        passengers_other_pickups = []
        
        for r in passengers_today:
            if r.get('pickup_time_outbound'):
                meeting_addr = r.get('meeting_point_address', '').lower().strip()
                # Grouper UNIQUEMENT par adresse, pas par détour
                if meeting_addr == departure_address:
                    passengers_at_departure.append(r)
                else:
                    passengers_other_pickups.append(r)

        # Timeline ALLER avec passagers du jour
        # Étape départ
        timeline_aller = f'''
            <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                <div style="display:flex;flex-direction:column;align-items:center;">
                    <div style="width:32px;height:32px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏠</div>
                    <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                </div>
                <div style="flex:1;margin-left:20px;">
                    <div style="font-weight:600;font-size:13px;margin-bottom:2px;"><font color="#444444">Départ de chez vous</font></div>
                    <div style="font-weight:700;font-size:16px;margin-bottom:2px;"><font color="#111111">{dep_time_str}</font></div>
                    <div style="font-size:12px;line-height:1.4;"><font color="#666666">{offer_data['departure']}</font></div>'''
        
        # Ajouter les passagers qui montent au départ
        if passengers_at_departure:
            for res in passengers_at_departure:
                timeline_aller += f'''
                    <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                        <div style="width:20px;height:20px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                        <span style="font-size:13px;margin-left:8px;"><font color="#111111"><strong>{res['passenger_name']}</strong></font></span>
                    </div>'''
        
        timeline_aller += '''
                </div>
            </div>
        '''
        
        # Grouper les autres pickups par adresse (pour éviter les doublons)
        pickups_by_address = {}
        for res in passengers_other_pickups:
            addr_normalized = res.get('meeting_point_address', '').lower().strip()
            if addr_normalized not in pickups_by_address:
                pickups_by_address[addr_normalized] = []
            pickups_by_address[addr_normalized].append(res)
        
        # Trier les pickups par heure chronologique (pickup_time_outbound)
        def get_time_value(time_obj):
            if isinstance(time_obj, timedelta):
                return time_obj.total_seconds()
            elif hasattr(time_obj, 'hour'):
                return time_obj.hour * 3600 + time_obj.minute * 60
            return 0
        
        sorted_pickups = sorted(
            pickups_by_address.items(),
            key=lambda item: get_time_value(item[1][0].get('pickup_time_outbound')) if item[1] else 0
        )
        
        # Créer une étape par adresse unique (dans l'ordre chronologique)
        for addr, passengers_at_addr in sorted_pickups:
            # Utiliser le premier passager pour les infos d'adresse et horaire
            first = passengers_at_addr[0]
            
            # Construire la liste des passagers à cette adresse
            passengers_list_html = ""
            for res in passengers_at_addr:
                passengers_list_html += f'''
                        <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                            <div style="width:20px;height:20px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                            <span style="font-size:13px;margin-left:8px;"><font color="#111111"><strong>{res['passenger_name']}</strong></font></span>
                        </div>'''
            
            timeline_aller += f'''
                <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                    <div style="display:flex;flex-direction:column;align-items:center;">
                        <div style="width:32px;height:32px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">📍</div>
                        <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                    </div>
                    <div style="flex:1;margin-left:20px;">
                        <div style="font-weight:600;font-size:13px;margin-bottom:2px;"><font color="#444444">Pickup</font></div>
                        <div style="font-weight:700;font-size:16px;margin-bottom:2px;"><font color="{color_outbound}">{first['pickup_time_outbound'].strftime('%H:%M')}</font></div>
                        <div style="font-size:12px;line-height:1.4;"><font color="#666666">{first['meeting_point_address']}</font></div>{passengers_list_html}
                    </div>
                </div>
            '''
        
        timeline_aller += f'''
            <div style="display:flex;align-items:flex-start;">
                <div style="display:flex;flex-direction:column;align-items:center;">
                    <div style="width:32px;height:32px;border-radius:50%;background:#10b981;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏢</div>
                </div>
                <div style="flex:1;margin-left:20px;">
                    <div style="font-weight:600;font-size:13px;margin-bottom:2px;"><font color="#444444">Arrivée au bureau</font></div>
                    <div style="font-weight:700;font-size:16px;margin-bottom:2px;"><font color="#111111">{offer_data['arrival_time'].strftime('%H:%M')}</font></div>
                    <div style="font-size:12px;line-height:1.4;"><font color="#666666">{offer_data['destination']}</font></div>
                </div>
            </div>
        '''
        
        # Grouper les passagers qui descendent à l'arrivée (UNIQUEMENT par adresse)
        arrival_address = offer_data['departure'].lower().strip()  # Arrivée = domicile du conducteur
        passengers_at_arrival = []
        passengers_other_dropoffs = []
        
        for r in passengers_today:
            if r.get('dropoff_time_return'):
                meeting_addr = r.get('meeting_point_address', '').lower().strip()
                # Grouper UNIQUEMENT par adresse, pas par détour
                if meeting_addr == arrival_address:
                    passengers_at_arrival.append(r)
                else:
                    passengers_other_dropoffs.append(r)
        
        # Timeline RETOUR avec passagers du jour
        timeline_retour = f'''
            <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                <div style="display:flex;flex-direction:column;align-items:center;">
                    <div style="width:32px;height:32px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏢</div>
                    <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                </div>
                <div style="flex:1;margin-left:20px;">
                    <div style="font-weight:600;font-size:13px;margin-bottom:2px;"><font color="#444444">Départ du bureau</font></div>
                    <div style="font-weight:700;font-size:16px;margin-bottom:2px;"><font color="#111111">{offer_data['return_departure_time'].strftime('%H:%M')}</font></div>
                    <div style="font-size:12px;line-height:1.4;"><font color="#666666">{offer_data['destination']}</font></div>
                </div>
            </div>
        '''
        
        # Grouper les autres dropoffs par adresse (pour éviter les doublons)
        dropoffs_by_address = {}
        for res in passengers_other_dropoffs:
            addr_normalized = res.get('meeting_point_address', '').lower().strip()
            if addr_normalized not in dropoffs_by_address:
                dropoffs_by_address[addr_normalized] = []
            dropoffs_by_address[addr_normalized].append(res)
        
        # Trier les dropoffs par heure chronologique (dropoff_time_return)
        sorted_dropoffs = sorted(
            dropoffs_by_address.items(),
            key=lambda item: get_time_value(item[1][0].get('dropoff_time_return')) if item[1] else 0
        )
        
        # Créer une étape par adresse unique (dans l'ordre chronologique)
        for addr, passengers_at_addr in sorted_dropoffs:
            # Utiliser le premier passager pour les infos d'adresse et horaire
            first = passengers_at_addr[0]
            
            # Construire la liste des passagers à cette adresse
            passengers_list_html = ""
            for res in passengers_at_addr:
                passengers_list_html += f'''
                        <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                            <div style="width:20px;height:20px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                            <span style="font-size:13px;margin-left:8px;"><font color="#111111"><strong>{res['passenger_name']}</strong></font></span>
                        </div>'''
            
            timeline_retour += f'''
                <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                    <div style="display:flex;flex-direction:column;align-items:center;">
                        <div style="width:32px;height:32px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">📍</div>
                        <div style="width:2px;height:40px;background:#e5e7eb;margin-top:4px;"></div>
                    </div>
                    <div style="flex:1;margin-left:20px;">
                        <div style="font-weight:600;font-size:13px;margin-bottom:2px;"><font color="#444444">Dropoff</font></div>
                        <div style="font-weight:700;font-size:16px;margin-bottom:2px;"><font color="{color_return}">{first['dropoff_time_return'].strftime('%H:%M')}</font></div>
                        <div style="font-size:12px;line-height:1.4;"><font color="#666666">{first['meeting_point_address']}</font></div>{passengers_list_html}
                    </div>
                </div>
            '''
        
        # Déterminer heure d'arrivée domicile la plus tardive basée sur déposes
        arr_home_val = offer_data['return_arrival_time']
        computed_arr_times = [r.get('computed_arrival_home_time') for r in passengers_today if r.get('computed_arrival_home_time')]
        if computed_arr_times:
            try:
                arr_home_val = max(computed_arr_times)
            except Exception:
                pass
        arr_home_str = arr_home_val.strftime('%H:%M')

        # Étape arrivée
        timeline_retour += f'''
            <div style="display:flex;align-items:flex-start;">
                <div style="display:flex;flex-direction:column;align-items:center;">
                    <div style="width:32px;height:32px;border-radius:50%;background:#10b981;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏠</div>
                </div>
                <div style="flex:1;margin-left:20px;">
                    <div style="font-weight:600;font-size:13px;margin-bottom:2px;"><font color="#444444">Arrivée chez vous</font></div>
                    <div style="font-weight:700;font-size:16px;margin-bottom:2px;"><font color="#111111">{arr_home_str}</font></div>
                    <div style="font-size:12px;line-height:1.4;"><font color="#666666">{offer_data['departure']}</font></div>'''
        
        # Ajouter les passagers qui descendent à l'arrivée
        if passengers_at_arrival:
            for res in passengers_at_arrival:
                timeline_retour += f'''
                    <div style="margin-top:8px;padding-left:4px;display:flex;align-items:center;">
                        <div style="width:20px;height:20px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:11px;">👤</div>
                        <span style="font-size:13px;margin-left:8px;"><font color="#111111"><strong>{res['passenger_name']}</strong></font></span>
                    </div>'''
        
        timeline_retour += '''
                </div>
            </div>
        '''
        
        # Construire waypoints pour navigation ALLER (adresses des pickups intermédiaires)
        waypoints_aller = [{'address': addr} for addr, _ in sorted_pickups]
        
        # Construire waypoints pour navigation RETOUR (adresses des dropoffs intermédiaires)
        waypoints_retour = [{'address': addr} for addr, _ in sorted_dropoffs]
        
        # Ajouter la section pour ce jour
        days_sections += f'''
        <div style="background:#fff;border-radius:16px;box-shadow:0 4px 16px rgba(0,0,0,0.1);padding:24px;margin-bottom:24px;border:2px solid #f0f0f0;">
            <!-- Badge jour -->
            <div style="display:inline-block;background:linear-gradient(135deg, #10b981, #059669);color:#111;padding:10px 24px;border-radius:20px;font-size:15px;font-weight:700;margin-bottom:20px;box-shadow:0 4px 12px rgba(0,0,0,0.15);">
                📅 {day_full.upper()}
                <span style="margin-left:8px;background:#eaeaea;color:#111;padding:4px 10px;border-radius:12px;font-size:13px;">
                    {len(passengers_today)} passager{'s' if len(passengers_today) > 1 else ''}
                </span>
            </div>
            
            <div style="display:flex;gap:20px;flex-wrap:wrap;">
                <!-- ALLER -->
                <div style="flex:1;min-width:280px;background-color:#fafafa;background:linear-gradient(to bottom, #ffffff, #fafafa);border-radius:12px;padding:20px;border:1px solid #e5e7eb;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                    <div style="font-size:15px;font-weight:700;color:{color_outbound};margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid {color_outbound};">➡️ ALLER</div>
                    {timeline_aller}
                    {create_compact_nav_buttons(offer_data['departure'], offer_data['destination'], waypoints_aller)}
                </div>
                
                <!-- RETOUR -->
                <div style="flex:1;min-width:280px;background-color:#fafafa;background:linear-gradient(to bottom, #ffffff, #fafafa);border-radius:12px;padding:20px;border:1px solid #e5e7eb;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                    <div style="font-size:15px;font-weight:700;color:{color_return};margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid {color_return};">⬅️ RETOUR</div>
                    {timeline_retour}
                    {create_compact_nav_buttons(offer_data['destination'], offer_data['departure'], waypoints_retour)}
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
        <div style="max-width:800px;margin:40px auto;padding:20px;">
            <!-- En-tête -->
            <div style="text-align:center;margin-bottom:32px;">
                <h1 style="color:{header_color};font-size:28px;margin:0 0 12px 0;font-weight:800;">{header_title}</h1>
                <div style="color:#666;font-size:16px;margin:0;line-height:1.5;">{intro_text}</div>
            </div>
            
            <!-- Bandeau trajet simple -->
            <div style="background:{color_outbound};border-radius:16px;padding:20px;text-align:center;box-shadow:0 4px 12px rgba(0,0,0,0.15);margin-bottom:24px;">
                <div style="font-size:16px;font-weight:700;color:#fff;line-height:1.5;">{offer_data['departure']} ➡️ {offer_data['destination']}</div>
            </div>
            
            <!-- Encart passagers -->
            {create_passengers_contact_card(reservations, color_outbound, base_url)}
            
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
    
    # Email texte
    text_body = f"""
{header_title}

{intro_text}

Trajet : {offer_data['departure']} ↔ {offer_data['destination']}

---
Carette - Plateforme de covoiturage RSE
    """
    
    return (subject, html_body, text_body)
