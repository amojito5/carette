"""
Carette - Utilitaires de validation et sécurité
"""
import re
import bleach
from datetime import datetime, timedelta


def validate_coordinates(lon, lat):
    """
    Valide des coordonnées GPS
    
    Args:
        lon: Longitude
        lat: Latitude
        
    Returns:
        Tuple (lon_float, lat_float)
        
    Raises:
        ValueError: Si coordonnées invalides
    """
    try:
        lon_f = float(lon)
        lat_f = float(lat)
        if not (-180 <= lon_f <= 180 and -90 <= lat_f <= 90):
            raise ValueError("Coordonnées hors limites géographiques")
        return lon_f, lat_f
    except (ValueError, TypeError) as e:
        raise ValueError(f"Coordonnées GPS invalides: {e}")


def sanitize_text(text, max_length=1000, allow_newlines=True):
    """
    Nettoie et sécurise du texte utilisateur
    
    Args:
        text: Texte à nettoyer
        max_length: Longueur maximale
        allow_newlines: Autoriser les retours à la ligne
        
    Returns:
        Texte nettoyé et tronqué
    """
    if not text:
        return ""
    
    # Enlever tout HTML/JavaScript dangereux
    clean = bleach.clean(str(text), tags=[], strip=True)
    
    # Optionnel: supprimer les retours à la ligne
    if not allow_newlines:
        clean = clean.replace('\n', ' ').replace('\r', '')
    
    # Tronquer à la longueur max
    return clean[:max_length].strip()


def validate_datetime(dt_str, allow_past=False, max_future_days=365):
    """
    Valide et parse une date/heure
    
    Args:
        dt_str: String datetime ISO format
        allow_past: Autoriser les dates passées
        max_future_days: Nombre max de jours dans le futur
        
    Returns:
        datetime object
        
    Raises:
        ValueError: Si date invalide
    """
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        
        if not allow_past and dt < now - timedelta(hours=1):
            raise ValueError("La date ne peut pas être dans le passé")
        
        if dt > now + timedelta(days=max_future_days):
            raise ValueError(f"La date ne peut pas être à plus de {max_future_days} jours dans le futur")
        
        return dt
    except (ValueError, TypeError, AttributeError) as e:
        raise ValueError(f"Format de date invalide (utilisez ISO 8601): {e}")


def validate_integer(value, min_val=None, max_val=None, field_name="valeur"):
    """
    Valide un entier avec bornes optionnelles
    
    Args:
        value: Valeur à valider
        min_val: Valeur minimale (optionnel)
        max_val: Valeur maximale (optionnel)
        field_name: Nom du champ pour les messages d'erreur
        
    Returns:
        int
        
    Raises:
        ValueError: Si valeur invalide
    """
    try:
        val = int(value)
        
        if min_val is not None and val < min_val:
            raise ValueError(f"{field_name} doit être >= {min_val}")
        
        if max_val is not None and val > max_val:
            raise ValueError(f"{field_name} doit être <= {max_val}")
        
        return val
    except (ValueError, TypeError) as e:
        raise ValueError(f"{field_name} invalide: {e}")


def validate_email(email):
    """
    Valide basiquement un email
    
    Args:
        email: Adresse email
        
    Returns:
        Email en minuscules
        
    Raises:
        ValueError: Si email invalide
    """
    if not email:
        raise ValueError("Email requis")
    
    # Regex basique (pas exhaustive mais raisonnable)
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    email_clean = email.strip().lower()
    
    if not re.match(pattern, email_clean):
        raise ValueError("Format d'email invalide")
    
    if len(email_clean) > 255:
        raise ValueError("Email trop long")
    
    return email_clean


def validate_user_id(user_id):
    """
    Valide un user_id
    
    Args:
        user_id: Identifiant utilisateur
        
    Returns:
        User ID nettoyé
        
    Raises:
        ValueError: Si user_id invalide
    """
    if not user_id:
        raise ValueError("user_id requis")
    
    uid = str(user_id).strip()
    
    if len(uid) < 1 or len(uid) > 255:
        raise ValueError("user_id doit avoir entre 1 et 255 caractères")
    
    # Enlever caractères dangereux
    uid = sanitize_text(uid, max_length=255, allow_newlines=False)
    
    if not uid:
        raise ValueError("user_id invalide après nettoyage")
    
    return uid
