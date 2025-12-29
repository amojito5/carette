"""
Module d'envoi d'emails avec SMTP
Gère l'envoi réel des emails en HTML + texte brut + pièces jointes
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.header import Header
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Configuration SMTP (à déplacer dans .env en production)
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER', 'noreply@carette.com')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'Carette Covoiturage <noreply@carette.com>')
FROM_NAME = os.getenv('FROM_NAME', 'Carette Covoiturage')


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    map_image_path: str = None,
    reply_to: str = None
) -> bool:
    """
    Envoie un email avec HTML + texte brut + image de carte optionnelle
    
    Args:
        to_email: Destinataire
        subject: Sujet de l'email
        html_body: Corps HTML (peut contenir <img src="cid:map_image">)
        text_body: Corps texte brut (fallback)
        map_image_path: Chemin vers l'image de carte (ex: "static/maps/abc123.png")
        reply_to: Email de réponse optionnel (ex: email du conducteur)
    
    Returns:
        True si envoyé avec succès, False sinon
    """
    try:
        # Créer le message multipart
        msg = MIMEMultipart('related')
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        msg['Subject'] = Header(subject, 'utf-8')
        
        if reply_to:
            msg['Reply-To'] = reply_to
        
        # Alternative: HTML ou texte
        msg_alternative = MIMEMultipart('alternative')
        msg.attach(msg_alternative)
        
        # Version texte brut
        part_text = MIMEText(text_body, 'plain', 'utf-8')
        msg_alternative.attach(part_text)
        
        # Version HTML
        part_html = MIMEText(html_body, 'html', 'utf-8')
        msg_alternative.attach(part_html)
        
        # Attacher l'image de carte si fournie
        if map_image_path and os.path.exists(map_image_path):
            with open(map_image_path, 'rb') as img_file:
                img_data = img_file.read()
                img = MIMEImage(img_data)
                img.add_header('Content-ID', '<map_image>')
                img.add_header('Content-Disposition', 'inline', filename='map.png')
                msg.attach(img)
                logger.debug(f"📎 Image attachée: {map_image_path}")
        
        # Connexion SMTP
        if not SMTP_PASSWORD:
            logger.warning("⚠️ SMTP_PASSWORD non configuré - email non envoyé (mode dev)")
            logger.info(f"📧 [DEV MODE] Email à {to_email}: {subject}")
            logger.debug(f"HTML body:\n{html_body[:200]}...")
            return True  # Simuler succès en dev
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"✅ Email envoyé à {to_email}: {subject}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur envoi email à {to_email}: {e}", exc_info=True)
        return False


def send_email_batch(emails: list) -> dict:
    """
    Envoie plusieurs emails en batch
    
    Args:
        emails: Liste de dicts avec keys: to_email, subject, html_body, text_body, map_image_path
    
    Returns:
        dict avec 'success': int, 'failed': int, 'errors': list
    """
    results = {
        'success': 0,
        'failed': 0,
        'errors': []
    }
    
    for email_data in emails:
        success = send_email(
            to_email=email_data['to_email'],
            subject=email_data['subject'],
            html_body=email_data['html_body'],
            text_body=email_data['text_body'],
            map_image_path=email_data.get('map_image_path'),
            reply_to=email_data.get('reply_to')
        )
        
        if success:
            results['success'] += 1
        else:
            results['failed'] += 1
            results['errors'].append(email_data['to_email'])
    
    logger.info(f"📊 Batch terminé: {results['success']} envoyés, {results['failed']} échecs")
    return results


# Pour les tests
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    
    # Test simple
    success = send_email(
        to_email="test@example.com",
        subject="🔔 Test email Carette",
        html_body="<h1>Test</h1><p>Ceci est un test</p>",
        text_body="Test\n\nCeci est un test"
    )
    
    print(f"Résultat: {'✅ Envoyé' if success else '❌ Échec'}")
