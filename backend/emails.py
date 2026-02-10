"""
Carette - Module Email (Workflow avec SendGrid/SMTP)
Gestion complète des emails automatisés pour le workflow covoiturage
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from typing import Dict, Optional, List
import secrets
from datetime import datetime, timedelta

# Configuration email
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'noreply@carette.app')
BASE_URL = os.getenv('BASE_URL', 'http://localhost:8080')

# Configuration WhatsApp
WHATSAPP_ENABLED = os.getenv('WHATSAPP_ENABLED', 'true').lower() == 'true'

# Mode debug : afficher le contenu des emails en console
EMAIL_DEBUG_MODE = os.getenv('EMAIL_DEBUG_MODE', 'true').lower() == 'true'


def send_email(to_email: str, subject: str, html_body: str, text_body: Optional[str] = None, attachments: Optional[List[Dict]] = None):
    """
    Envoyer un email via SMTP avec support des pièces jointes inline
    
    Args:
        to_email: Destinataire
        subject: Sujet
        html_body: Corps HTML
        text_body: Corps texte (optionnel)
        attachments: Liste de pièces jointes [{'path': '/chemin/image.png', 'cid': 'map_image'}]
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        print(f"\n{'='*80}")
        print(f"⚠️ EMAIL (SMTP non configuré)")
        print(f"📧 À: {to_email}")
        print(f"📝 Sujet: {subject}")
        print(f"{'='*80}")
        
        if EMAIL_DEBUG_MODE:
            # Afficher le contenu texte de l'email
            if text_body:
                print(f"\n{text_body}\n")
            else:
                # Extraire du texte du HTML (simplification)
                import re
                text_content = re.sub('<[^<]+?>', '', html_body)
                text_content = re.sub(r'\s+', ' ', text_content).strip()
                # Afficher seulement les 500 premiers caractères
                print(f"\n{text_content[:500]}...\n")
            print(f"{'='*80}\n")
        
        return False
    
    try:
        msg = MIMEMultipart('related')  # 'related' pour les images inline
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Conteneur pour texte/html
        msg_alternative = MIMEMultipart('alternative')
        msg.attach(msg_alternative)
        
        # Version texte
        if text_body:
            msg_alternative.attach(MIMEText(text_body, 'plain'))
        
        # Version HTML
        msg_alternative.attach(MIMEText(html_body, 'html'))
        
        # Ajouter les pièces jointes inline (images)
        if attachments:
            for attachment in attachments:
                try:
                    with open(attachment['path'], 'rb') as f:
                        img = MIMEImage(f.read())
                        img.add_header('Content-ID', f"<{attachment['cid']}>")
                        img.add_header('Content-Disposition', 'inline', filename=os.path.basename(attachment['path']))
                        msg.attach(img)
                except Exception as e:
                    print(f"⚠️ Erreur ajout pièce jointe {attachment['path']}: {e}")
        
        # Envoi
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        print(f"✅ Email envoyé: {to_email} - {subject}")
        return True
    except Exception as e:
        print(f"❌ Erreur envoi email: {e}")
        return False
        return True
        
    except Exception as e:
        print(f"❌ Erreur envoi email: {e}")
        return False


def generate_confirmation_token() -> str:
    """Générer un token sécurisé pour les liens de confirmation"""
    return secrets.token_urlsafe(32)


def whatsapp_button(phone: str, message: str) -> str:
    """Générer un bouton WhatsApp cliquable"""
    if not WHATSAPP_ENABLED:
        return ''
    
    # Nettoyer le numéro de téléphone
    clean_phone = ''.join(filter(str.isdigit, phone))
    if not clean_phone.startswith('33') and len(clean_phone) == 10:
        clean_phone = '33' + clean_phone[1:]  # 06... -> 336...
    
    # Encoder le message
    import urllib.parse
    encoded_msg = urllib.parse.quote(message)
    
    return f'''
    <table cellspacing="0" cellpadding="0" style="margin: 20px 0;">
        <tr>
            <td style="border-radius: 8px; background-color: #25D366;">
                <a href="https://wa.me/{clean_phone}?text={encoded_msg}" 
                   style="display: inline-block; padding: 12px 24px; font-family: Arial, sans-serif; 
                          font-size: 16px; color: #ffffff; text-decoration: none; border-radius: 8px; 
                          font-weight: bold;">
                    💬 Contacter sur WhatsApp
                </a>
            </td>
        </tr>
    </table>
    '''


# ============================================
# TEMPLATES D'EMAILS
# ============================================

def email_template_base(content: str) -> str:
    """Template HTML de base pour tous les emails"""
    return f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Carette - Covoiturage</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f5f5f5;">
        <table cellspacing="0" cellpadding="0" width="100%" style="background-color: #f5f5f5;">
            <tr>
                <td align="center" style="padding: 40px 20px;">
                    <table cellspacing="0" cellpadding="0" width="600" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                        <!-- Header -->
                        <tr>
                            <td align="center" style="padding: 30px; background-color: #4CAF50; border-radius: 12px 12px 0 0;">
                                <h1 style="margin: 0; color: #ffffff; font-size: 28px;">🚗 Carette</h1>
                                <p style="margin: 5px 0 0 0; color: #ffffff; font-size: 14px;">Covoiturage simple et rapide</p>
                            </td>
                        </tr>
                        
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px;">
                                {content}
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td align="center" style="padding: 20px; background-color: #f9f9f9; border-radius: 0 0 12px 12px;">
                                <p style="margin: 0; color: #666666; font-size: 12px;">
                                    Carette - Covoiturage facile<br>
                                    Questions ? Répondez à cet email
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """


def email_new_reservation_to_driver(driver_email: str, driver_name: str,
                                     passenger_name: str, passenger_phone: str,
                                     offer_details: Dict, accept_link: str, reject_link: str) -> bool:
    """Email au conducteur : nouvelle demande de réservation"""
    
    whatsapp = whatsapp_button(passenger_phone,
        f"Bonjour ! Je suis {passenger_name}, j'ai demandé une place pour votre trajet {offer_details['departure']} → {offer_details['destination']} 🚗")
    
    # Récupérer les infos de détour
    detour_time = offer_details.get('detour_time', 0)
    meeting_address = offer_details.get('meeting_address', '')
    trip_type_label = {
        'outbound': 'Aller',
        'return': 'Retour',
        'both': 'Aller-Retour'
    }.get(offer_details.get('trip_type', 'outbound'), 'Trajet')
    
    # Bloc d'info détour si applicable
    detour_info_html = ''
    if detour_time > 0:
        detour_info_html = f"""
        <div style="background-color: #fff3e0; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ff9800;">
            <p style="margin: 0; color: #e65100; font-size: 14px; line-height: 1.6;">
                ⚠️ <strong>Détour nécessaire</strong><br>
                Point de rencontre : <strong>{meeting_address}</strong><br>
                Temps de détour : <strong>+{detour_time} minutes</strong>
            </p>
        </div>
        """
    
    content = f"""
    <h2 style="color: #333333; margin-bottom: 20px;">Nouvelle demande de réservation ! 🎉</h2>
    
    <p style="color: #666666; line-height: 1.6;">
        Bonjour {driver_name},<br><br>
        <strong>{passenger_name}</strong> souhaite réserver une place dans votre trajet :
    </p>
    
    <div style="background-color: #f9f9f9; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p style="margin: 5px 0; color: #333333;"><strong>🚗 Type :</strong> {trip_type_label}</p>
        <p style="margin: 5px 0; color: #333333;"><strong>📍 Départ :</strong> {offer_details['departure']}</p>
        <p style="margin: 5px 0; color: #333333;"><strong>🎯 Destination :</strong> {offer_details['destination']}</p>
        <p style="margin: 5px 0; color: #333333;"><strong>📅 Date :</strong> {offer_details['datetime']}</p>
        <p style="margin: 5px 0; color: #333333;"><strong>👤 Passager :</strong> {passenger_name}</p>
    </div>
    
    {detour_info_html}
    
    <h3 style="color: #333333; margin-top: 30px;">Coordonnées du passager :</h3>
    <p style="color: #666666;">
        📱 {passenger_phone}
    </p>
    
    {whatsapp}
    
    <h3 style="color: #333333; margin-top: 30px;">Que voulez-vous faire ?</h3>
    
    <table cellspacing="0" cellpadding="0" style="margin: 20px 0;">
        <tr>
            <td style="padding-right: 10px;">
                <table cellspacing="0" cellpadding="0">
                    <tr>
                        <td style="border-radius: 8px; background-color: #4CAF50;">
                            <a href="{accept_link}"
                               style="display: inline-block; padding: 14px 28px; font-family: Arial, sans-serif;
                                      font-size: 16px; color: #ffffff; text-decoration: none; border-radius: 8px;
                                      font-weight: bold;">
                                ✅ Accepter la réservation
                            </a>
                        </td>
                    </tr>
                </table>
            </td>
            <td>
                <table cellspacing="0" cellpadding="0">
                    <tr>
                        <td style="border-radius: 8px; background-color: #f44336;">
                            <a href="{reject_link}"
                               style="display: inline-block; padding: 14px 28px; font-family: Arial, sans-serif;
                                      font-size: 16px; color: #ffffff; text-decoration: none; border-radius: 8px;
                                      font-weight: bold;">
                                ❌ Refuser
                            </a>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
    
    <p style="color: #999999; font-size: 12px; margin-top: 30px;">
        💡 <strong>Note :</strong> Le passager a versé une caution de 1€ pour garantir son engagement. Si vous acceptez, il réglera le reste du prix directement avec vous (cash, Lydia, Paylib).
    </p>
    """
    
    html = email_template_base(content)
    subject = f"Nouvelle demande : {passenger_name} → {offer_details['departure']}"
    
    return send_email(driver_email, subject, html)


def email_reservation_confirmed_to_passenger(passenger_email: str, passenger_name: str,
                                              driver_name: str, driver_email: str, driver_phone: str,
                                              offer_details: Dict) -> bool:
    """Email au passager : réservation confirmée"""
    
    whatsapp = whatsapp_button(driver_phone,
        f"Bonjour ! C'est {passenger_name}, ma réservation vient d'être confirmée pour le trajet {offer_details['departure']} → {offer_details['destination']} 🚗")
    
    content = f"""
    <h2 style="color: #4CAF50; margin-bottom: 20px;">✅ Réservation confirmée !</h2>
    
    <p style="color: #666666; line-height: 1.6;">
        Bonjour {passenger_name},<br><br>
        Bonne nouvelle ! <strong>{driver_name}</strong> a accepté votre demande de covoiturage.
    </p>
    
    <div style="background-color: #e8f5e9; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #4CAF50;">
        <p style="margin: 5px 0; color: #333333;"><strong>📍 Départ :</strong> {offer_details['departure']}</p>
        <p style="margin: 5px 0; color: #333333;"><strong>🎯 Destination :</strong> {offer_details['destination']}</p>
        <p style="margin: 5px 0; color: #333333;"><strong>📅 Date :</strong> {offer_details['datetime']}</p>
        <p style="margin: 5px 0; color: #333333;"><strong>🚗 Conducteur :</strong> {driver_name}</p>
    </div>
    
    <h3 style="color: #333333; margin-top: 30px;">Coordonnées du conducteur :</h3>
    <p style="color: #666666;">
        📧 <a href="mailto:{driver_email}" style="color: #4CAF50;">{driver_email}</a><br>
        📱 {driver_phone}
    </p>
    
    {whatsapp}
    
    <div style="background-color: #fff3e0; padding: 15px; border-radius: 8px; margin: 30px 0;">
        <p style="margin: 0; color: #e65100; font-size: 14px;">
            💰 <strong>Rappel paiement :</strong> Vous avez payé 1€ de frais de réservation. 
            Le prix du trajet se règle directement avec le conducteur (espèces, Lydia, etc.).
        </p>
    </div>
    
    <p style="color: #666666; line-height: 1.6; margin-top: 30px;">
        Bon voyage ! 🚗💨
    </p>
    """
    
    html = email_template_base(content)
    subject = f"Confirmé : Trajet {offer_details['departure']} → {offer_details['destination']}"
    
    return send_email(passenger_email, subject, html)


def email_reservation_rejected_to_passenger(passenger_email: str, passenger_name: str,
                                             driver_name: str, offer_details: Dict) -> bool:
    """Email au passager : réservation refusée"""
    
    content = f"""
    <h2 style="color: #f44336; margin-bottom: 20px;">Réservation non acceptée</h2>
    
    <p style="color: #666666; line-height: 1.6;">
        Bonjour {passenger_name},<br><br>
        Malheureusement, <strong>{driver_name}</strong> n'a pas pu accepter votre demande pour ce trajet :
    </p>
    
    <div style="background-color: #ffebee; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f44336;">
        <p style="margin: 5px 0; color: #333333;"><strong>📍 Départ :</strong> {offer_details['departure']}</p>
        <p style="margin: 5px 0; color: #333333;"><strong>🎯 Destination :</strong> {offer_details['destination']}</p>
        <p style="margin: 5px 0; color: #333333;"><strong>📅 Date :</strong> {offer_details['datetime']}</p>
    </div>
    
    <p style="color: #666666; line-height: 1.6;">
        Ne vous inquiétez pas ! Vous pouvez rechercher d'autres trajets disponibles.
    </p>
    
    <div style="background-color: #e8f5e9; padding: 15px; border-radius: 8px; margin: 30px 0;">
        <p style="margin: 0; color: #2e7d32; font-size: 14px;">
            💰 Les frais de réservation (1€) vous seront remboursés automatiquement sous 3-5 jours.
        </p>
    </div>
    """
    
    html = email_template_base(content)
    subject = "Réservation non acceptée"
    
    return send_email(passenger_email, subject, html)


def email_payment_simulation(passenger_email: str, passenger_name: str, offer_details: Dict) -> bool:
    """Email après simulation de paiement (provisoire avant Stripe)"""
    
    content = f"""
    <h2 style="color: #4CAF50; margin-bottom: 20px;">🎉 Paiement simulé - Demande envoyée !</h2>
    
    <p style="color: #666666; line-height: 1.6;">
        Bonjour {passenger_name},<br><br>
        Votre demande de réservation a bien été envoyée au conducteur.
    </p>
    
    <div style="background-color: #e3f2fd; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #2196F3;">
        <p style="margin: 5px 0; color: #333333;"><strong>📍 Départ :</strong> {offer_details['departure']}</p>
        <p style="margin: 5px 0; color: #333333;"><strong>🎯 Destination :</strong> {offer_details['destination']}</p>
        <p style="margin: 5px 0; color: #333333;"><strong>📅 Date :</strong> {offer_details['datetime']}</p>
        <p style="margin: 5px 0; color: #333333;"><strong>💳 Frais :</strong> 1,00€ (simulé)</p>
    </div>
    
    <h3 style="color: #333333; margin-top: 30px;">Prochaines étapes :</h3>
    <ol style="color: #666666; line-height: 1.8;">
        <li>Le conducteur reçoit votre demande par email</li>
        <li>Il peut accepter ou refuser</li>
        <li>Vous recevrez une confirmation par email</li>
        <li>Vous pourrez ensuite contacter le conducteur sur WhatsApp</li>
    </ol>
    
    <div style="background-color: #fff3e0; padding: 15px; border-radius: 8px; margin: 30px 0;">
        <p style="margin: 0; color: #e65100; font-size: 14px;">
            ⚠️ <strong>Mode test :</strong> Le paiement de 1€ est actuellement simulé. 
            En production, ceci sera un vrai paiement Stripe.
        </p>
    </div>
    """
    
    html = email_template_base(content)
    subject = "Demande envoyée - En attente de confirmation"
    
    return send_email(passenger_email, subject, html)
