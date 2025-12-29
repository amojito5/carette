#!/usr/bin/env python3
"""
Script pour prévisualiser les templates d'emails dans le navigateur
Usage: python preview_email_templates.py [port]
Accès: http://51.178.30.246:8888
"""

import sys
from flask import Flask, render_template_string, request
from email_templates import *

app = Flask(__name__)

# Données de test
TEST_DATA = {
    'passenger_name': 'Jean',
    'passenger_email': 'jean@test.com',
    'passenger_phone': '0617494314',
    'driver_name': 'Amo',
    'driver_email': 'amo@test.com',
    'driver_phone': '0612345678',
    'offer': {
        'departure': '7 Rue Lamartine (Hellemmes) 59260 Lille',
        'destination': 'Stade Bollaert-Dellelis',
        'datetime': 'Saturday 20 December 2025 à 19:00',
        'seats': 4
    },
    'meeting_address': 'Rue Montesquieu, Oignies',
    'trip_type': 'outbound',
    'base_url': 'http://localhost:5000'
}

TEMPLATES = {
    'request': ('Demande envoyée (passager)', lambda: email_request_sent_to_passenger(
        passenger_email=TEST_DATA['passenger_email'],
        passenger_name=TEST_DATA['passenger_name'],
        driver_name=TEST_DATA['driver_name'],
        offer=TEST_DATA['offer'],
        trip_type=TEST_DATA['trip_type'],
        meeting_address=TEST_DATA['meeting_address']
    )),
    
    'confirmed': ('Réservation acceptée (passager)', lambda: email_reservation_confirmed_to_passenger(
        passenger_email=TEST_DATA['passenger_email'],
        passenger_name=TEST_DATA['passenger_name'],
        driver_name=TEST_DATA['driver_name'],
        driver_phone=TEST_DATA['driver_phone'],
        driver_email_contact=TEST_DATA['driver_email'],
        offer=TEST_DATA['offer'],
        meeting_address=TEST_DATA['meeting_address'],
        price='Gratuit',
        cancel_url=f"{TEST_DATA['base_url']}/cancel?token=TEST"
    )),
    
    'driver_new': ('Nouvelle demande (conducteur)', lambda: email_new_reservation_request(
        driver_email=TEST_DATA['driver_email'],
        driver_name=TEST_DATA['driver_name'],
        passenger_name=TEST_DATA['passenger_name'],
        passenger_email=TEST_DATA['passenger_email'],
        passenger_phone=TEST_DATA['passenger_phone'],
        offer=TEST_DATA['offer'],
        meeting_address=TEST_DATA['meeting_address'],
        trip_type=TEST_DATA['trip_type'],
        detour_outbound=7,
        accept_url=f"{TEST_DATA['base_url']}/accept?token=TEST",
        refuse_url=f"{TEST_DATA['base_url']}/refuse?token=TEST",
        base_url=TEST_DATA['base_url']
    )),
    
    'driver_updated': ('Itinéraire mis à jour (conducteur)', lambda: email_driver_route_updated(
        driver_email=TEST_DATA['driver_email'],
        driver_name=TEST_DATA['driver_name'],
        offer=TEST_DATA['offer'],
        all_passengers=[{
            'name': 'Jean',
            'phone': '0617494314',
            'pickup_time': '18:50',
            'pickup_address': 'Rue Montesquieu, Oignies',
            'remove_url': f"{TEST_DATA['base_url']}/remove?token=TEST"
        }],
        seats_available=3,
        reason='Nouveau passager accepté',
        detour_outbound=7,
        detour_return=4,
        detour_remaining_outbound=8,
        detour_remaining_return=11,
        view_reservations_url=f"{TEST_DATA['base_url']}/reservations",
        cancel_offer_url=f"{TEST_DATA['base_url']}/cancel_offer?token=TEST",
        base_url=TEST_DATA['base_url']
    )),
    
    'refused': ('Demande refusée (passager)', lambda: email_reservation_refused(
        passenger_email=TEST_DATA['passenger_email'],
        passenger_name=TEST_DATA['passenger_name'],
        driver_name=TEST_DATA['driver_name'],
        offer=TEST_DATA['offer'],
        trip_type=TEST_DATA['trip_type']
    )),
    
    'cancelled': ('Annulation confirmée (passager)', lambda: email_cancellation_confirmed_passenger(
        passenger_email=TEST_DATA['passenger_email'],
        passenger_name=TEST_DATA['passenger_name'],
        offer=TEST_DATA['offer']
    )),
    
    'expired': ('Demande expirée', lambda: email_request_expired(
        passenger_email=TEST_DATA['passenger_email'],
        passenger_name=TEST_DATA['passenger_name'],
        driver_name=TEST_DATA['driver_name'],
        offer=TEST_DATA['offer']
    )),
    
    'reminder': ('Rappel J-1 (passager)', lambda: email_reminder_24h(
        recipient_email=TEST_DATA['passenger_email'],
        recipient_name=TEST_DATA['passenger_name'],
        role='passenger',
        offer=TEST_DATA['offer'],
        pickup_time='18:50',
        pickup_address=TEST_DATA['meeting_address'],
        driver_name=TEST_DATA['driver_name'],
        driver_phone=TEST_DATA['driver_phone'],
        cancel_url=f"{TEST_DATA['base_url']}/cancel?token=TEST"
    )),
    
    'offer_created': ('Offre créée (conducteur)', lambda: email_offer_published(
        driver_email=TEST_DATA['driver_email'],
        driver_name=TEST_DATA['driver_name'],
        offer=TEST_DATA['offer'],
        base_url=TEST_DATA['base_url']
    ))
}

@app.route('/')
def index():
    """Page d'accueil avec liste des templates"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>📧 Preview Templates Emails</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0;
                padding: 40px 20px;
                min-height: 100vh;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background: white;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                overflow: hidden;
            }
            .header {
                background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                padding: 40px;
                text-align: center;
                color: white;
            }
            .header h1 {
                margin: 0 0 10px 0;
                font-size: 36px;
            }
            .header p {
                margin: 0;
                opacity: 0.9;
                font-size: 16px;
            }
            .templates {
                padding: 30px 40px;
            }
            .template-item {
                display: block;
                padding: 20px;
                margin-bottom: 12px;
                background: #f8f9fa;
                border-radius: 12px;
                text-decoration: none;
                color: #2d3748;
                transition: all 0.2s;
                border-left: 4px solid #10b981;
            }
            .template-item:hover {
                background: #e5f7ef;
                transform: translateX(4px);
                box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2);
            }
            .template-name {
                font-weight: 600;
                font-size: 16px;
                margin-bottom: 4px;
            }
            .template-key {
                font-size: 13px;
                color: #666;
                font-family: monospace;
            }
            .footer {
                padding: 20px;
                text-align: center;
                color: #999;
                font-size: 14px;
                border-top: 1px solid #e5e7eb;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📧 Templates d'Emails</h1>
                <p>Prévisualisation en temps réel</p>
            </div>
            <div class="templates">
    """
    
    for key, (name, _) in TEMPLATES.items():
        html += f"""
                <a href="/preview/{key}" class="template-item">
                    <div class="template-name">{name}</div>
                    <div class="template-key">{key}</div>
                </a>
        """
    
    html += """
            </div>
            <div class="footer">
                Carette Covoiturage · Email System
            </div>
        </div>
    </body>
    </html>
    """
    return html

@app.route('/preview/<template_key>')
def preview(template_key):
    """Prévisualisation d'un template"""
    if template_key not in TEMPLATES:
        return f"Template '{template_key}' non trouvé", 404
    
    name, func = TEMPLATES[template_key]
    
    try:
        subject, html, text = func()
        
        preview_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{name}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: #f0f0f0;
            margin: 0;
            padding: 20px;
        }}
        .header {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .subject {{
            font-size: 20px;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
        }}
        .info {{
            color: #666;
            font-size: 14px;
        }}
        .back {{
            display: inline-block;
            margin-bottom: 10px;
            padding: 8px 16px;
            background: #10b981;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-size: 14px;
        }}
        .back:hover {{
            background: #059669;
        }}
        .email-container {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .tabs {{
            display: flex;
            background: #e5e7eb;
            border-bottom: 2px solid #d1d5db;
        }}
        .tab {{
            padding: 12px 24px;
            cursor: pointer;
            background: #e5e7eb;
            border: none;
            font-size: 14px;
            font-weight: 600;
        }}
        .tab.active {{
            background: white;
            border-bottom: 2px solid #3b82f6;
        }}
        .content {{
            display: none;
        }}
        .content.active {{
            display: block;
        }}
        .text-content {{
            white-space: pre-wrap;
            font-family: monospace;
            background: #f9fafb;
            padding: 20px;
            border-radius: 4px;
            margin: 20px;
        }}
    </style>
</head>
<body>
    <a href="/" class="back">← Retour à la liste</a>
    <div class="header">
        <div class="subject">📧 {subject}</div>
        <div class="info">Template: <strong>{name}</strong> ({template_key})</div>
    </div>
    
    <div class="email-container">
        <div class="tabs">
            <button class="tab active" onclick="showTab('html')">HTML</button>
            <button class="tab" onclick="showTab('text')">Texte brut</button>
        </div>
        
        <div id="html-content" class="content active">
            {html}
        </div>
        
        <div id="text-content" class="content">
            <div class="text-content">{text}</div>
        </div>
    </div>
    
    <script>
        function showTab(tab) {{
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.content').forEach(c => c.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById(tab + '-content').classList.add('active');
        }}
    </script>
</body>
</html>
        """
        
        return preview_html
        
    except Exception as e:
        import traceback
        return f"<pre>Erreur : {e}\n\n{traceback.format_exc()}</pre>", 500

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║       📧 SERVEUR DE PREVIEW DES TEMPLATES D'EMAILS  📧        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

🌐 Serveur démarré sur le port {port}

📍 Accès depuis ton navigateur :
   http://51.178.30.246:{port}

💡 Templates disponibles :
""")
    for key, (name, _) in TEMPLATES.items():
        print(f"   • {key}: {name}")
    
    print(f"\n⏸️  Arrêter le serveur : Ctrl+C\n")
    
    app.run(host='0.0.0.0', port=port, debug=True)

# Données de test
TEST_DATA = {
    'passenger_name': 'Jean',
    'passenger_email': 'jean@test.com',
    'passenger_phone': '0617494314',
    'driver_name': 'Amo',
    'driver_email': 'amo@test.com',
    'driver_phone': '0612345678',
    'offer': {
        'departure': '7 Rue Lamartine (Hellemmes) 59260 Lille',
        'destination': 'Stade Bollaert-Dellelis',
        'datetime': 'Saturday 20 December 2025 à 19:00',
        'seats': 4
    },
    'meeting_address': 'Rue Montesquieu, Oignies',
    'trip_type': 'outbound',
    'base_url': 'http://localhost:5000'
}

TEMPLATES = {
    'request': ('Demande envoyée (passager)', lambda: email_request_sent_to_passenger(
        passenger_email=TEST_DATA['passenger_email'],
        passenger_name=TEST_DATA['passenger_name'],
        driver_name=TEST_DATA['driver_name'],
        offer=TEST_DATA['offer'],
        trip_type=TEST_DATA['trip_type'],
        meeting_address=TEST_DATA['meeting_address']
    )),
    
    'confirmed': ('Réservation acceptée (passager)', lambda: email_reservation_confirmed_to_passenger(
        passenger_email=TEST_DATA['passenger_email'],
        passenger_name=TEST_DATA['passenger_name'],
        driver_name=TEST_DATA['driver_name'],
        driver_phone=TEST_DATA['driver_phone'],
        driver_email_contact=TEST_DATA['driver_email'],
        offer=TEST_DATA['offer'],
        meeting_address=TEST_DATA['meeting_address'],
        price='Gratuit',
        cancel_url=f"{TEST_DATA['base_url']}/cancel?token=TEST"
    )),
    
    'driver_new': ('Nouvelle demande (conducteur)', lambda: email_new_reservation_request(
        driver_email=TEST_DATA['driver_email'],
        driver_name=TEST_DATA['driver_name'],
        passenger_name=TEST_DATA['passenger_name'],
        passenger_email=TEST_DATA['passenger_email'],
        passenger_phone=TEST_DATA['passenger_phone'],
        offer=TEST_DATA['offer'],
        meeting_address=TEST_DATA['meeting_address'],
        trip_type=TEST_DATA['trip_type'],
        detour_outbound=7,
        accept_url=f"{TEST_DATA['base_url']}/accept?token=TEST",
        refuse_url=f"{TEST_DATA['base_url']}/refuse?token=TEST",
        base_url=TEST_DATA['base_url']
    )),
    
    'driver_updated': ('Itinéraire mis à jour (conducteur)', lambda: email_driver_route_updated(
        driver_email=TEST_DATA['driver_email'],
        driver_name=TEST_DATA['driver_name'],
        offer=TEST_DATA['offer'],
        all_passengers=[{
            'name': 'Jean',
            'phone': '0617494314',
            'pickup_time': '18:50',
            'pickup_address': 'Rue Montesquieu, Oignies',
            'remove_url': f"{TEST_DATA['base_url']}/remove?token=TEST"
        }],
        seats_available=3,
        reason='Nouveau passager accepté',
        view_reservations_url=f"{TEST_DATA['base_url']}/reservations",
        cancel_offer_url=f"{TEST_DATA['base_url']}/cancel_offer?token=TEST",
        base_url=TEST_DATA['base_url']
    )),
    
    'refused': ('Demande refusée (passager)', lambda: email_reservation_refused(
        passenger_email=TEST_DATA['passenger_email'],
        passenger_name=TEST_DATA['passenger_name'],
        driver_name=TEST_DATA['driver_name'],
        offer=TEST_DATA['offer'],
        trip_type=TEST_DATA['trip_type']
    )),
    
    'cancelled': ('Annulation confirmée (passager)', lambda: email_cancellation_confirmed_passenger(
        passenger_email=TEST_DATA['passenger_email'],
        passenger_name=TEST_DATA['passenger_name'],
        offer=TEST_DATA['offer']
    )),
    
    'expired': ('Demande expirée', lambda: email_request_expired(
        passenger_email=TEST_DATA['passenger_email'],
        passenger_name=TEST_DATA['passenger_name'],
        driver_name=TEST_DATA['driver_name'],
        offer=TEST_DATA['offer']
    )),
    
    'reminder': ('Rappel J-1 (passager)', lambda: email_reminder_24h(
        recipient_email=TEST_DATA['passenger_email'],
        recipient_name=TEST_DATA['passenger_name'],
        role='passenger',
        offer=TEST_DATA['offer'],
        pickup_time='18:50',
        pickup_address=TEST_DATA['meeting_address'],
        driver_name=TEST_DATA['driver_name'],
        driver_phone=TEST_DATA['driver_phone'],
        cancel_url=f"{TEST_DATA['base_url']}/cancel?token=TEST"
    ))
}

def show_menu():
    """Affiche le menu des templates disponibles"""
    print("\n" + "="*60)
    print("📧 PRÉVISUALISATION DES TEMPLATES D'EMAILS")
    print("="*60 + "\n")
    
    for i, (key, (name, _)) in enumerate(TEMPLATES.items(), 1):
        print(f"{i}. [{key}] {name}")
    
    print(f"\n0. Quitter\n")
    print("="*60)

def generate_html_preview(template_key):
    """Génère un fichier HTML de prévisualisation"""
    if template_key not in TEMPLATES:
        print(f"❌ Template '{template_key}' inconnu")
        return
    
    name, func = TEMPLATES[template_key]
    
    try:
        subject, html, text = func()
        
        # Créer le fichier HTML
        output_file = f"/tmp/email_preview_{template_key}.html"
        
        preview_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{name}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: #f0f0f0;
            margin: 0;
            padding: 20px;
        }}
        .header {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .subject {{
            font-size: 20px;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
        }}
        .info {{
            color: #666;
            font-size: 14px;
        }}
        .email-container {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .tabs {{
            display: flex;
            background: #e5e7eb;
            border-bottom: 2px solid #d1d5db;
        }}
        .tab {{
            padding: 12px 24px;
            cursor: pointer;
            background: #e5e7eb;
            border: none;
            font-size: 14px;
            font-weight: 600;
        }}
        .tab.active {{
            background: white;
            border-bottom: 2px solid #3b82f6;
        }}
        .content {{
            display: none;
            padding: 20px;
        }}
        .content.active {{
            display: block;
        }}
        .text-content {{
            white-space: pre-wrap;
            font-family: monospace;
            background: #f9fafb;
            padding: 20px;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="subject">📧 {subject}</div>
        <div class="info">Template: <strong>{name}</strong> ({template_key})</div>
    </div>
    
    <div class="email-container">
        <div class="tabs">
            <button class="tab active" onclick="showTab('html')">HTML</button>
            <button class="tab" onclick="showTab('text')">Texte brut</button>
        </div>
        
        <div id="html-content" class="content active">
            {html}
        </div>
        
        <div id="text-content" class="content">
            <div class="text-content">{text}</div>
        </div>
    </div>
    
    <script>
        function showTab(tab) {{
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.content').forEach(c => c.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById(tab + '-content').classList.add('active');
        }}
    </script>
</body>
</html>
        """
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(preview_html)
        
        print(f"\n✅ Template généré : {output_file}")
        print(f"📧 Sujet : {subject}")
        print(f"\n💡 Ouvre ce fichier dans ton navigateur pour voir le rendu :")
        print(f"   firefox {output_file}")
        print(f"   ou")
        print(f"   google-chrome {output_file}\n")
        
        return output_file
        
    except Exception as e:
        print(f"❌ Erreur : {e}")
        import traceback
        traceback.print_exc()

def interactive_mode():
    """Mode interactif"""
    while True:
        show_menu()
        choice = input("Choisis un template (numéro ou nom) : ").strip()
        
        if choice == '0':
            print("👋 Bye !")
            break
        
        # Par numéro
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(TEMPLATES):
                template_key = list(TEMPLATES.keys())[idx]
                generate_html_preview(template_key)
            else:
                print("❌ Numéro invalide")
        # Par nom
        elif choice in TEMPLATES:
            generate_html_preview(choice)
        else:
            print(f"❌ Template '{choice}' inconnu")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Mode ligne de commande
        template_key = sys.argv[1]
        generate_html_preview(template_key)
    else:
        # Mode interactif
        interactive_mode()
