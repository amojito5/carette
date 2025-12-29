"""
Gestionnaire de tokens sécurisés pour les magic links
Utilisé pour les actions par email (accepter, refuser, annuler)
"""
import hmac
import hashlib
import time
import json
from typing import Dict, Optional, Tuple

# Clé secrète pour signer les tokens (à mettre dans .env en production)
SECRET_KEY = "carette-secret-key-change-me-in-production-2025"

def generate_token(action: str, resource_id: int, user_email: str, expires_in: int = 86400 * 7) -> str:
    """
    Génère un token signé pour une action sécurisée
    
    Args:
        action: Type d'action (accept, refuse, cancel_passenger, cancel_offer, etc.)
        resource_id: ID de la ressource (reservation_id ou offer_id)
        user_email: Email de l'utilisateur autorisé à faire l'action
        expires_in: Durée de validité en secondes (défaut: 7 jours)
    
    Returns:
        Token signé au format: base64(payload).signature
    
    Exemple:
        token = generate_token('accept', 123, 'driver@example.com')
        # → "eyJhY3Rpb24iOiJhY2NlcHQi...}.a3f8b9c2d1e4..."
    """
    expiry = int(time.time()) + expires_in
    
    # Payload contenant les informations
    payload = {
        'action': action,
        'resource_id': resource_id,
        'email': user_email,
        'exp': expiry
    }
    
    # Encoder le payload en JSON puis base64
    import base64
    payload_json = json.dumps(payload, separators=(',', ':'))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip('=')
    
    # Créer la signature HMAC
    signature = hmac.new(
        SECRET_KEY.encode(),
        payload_b64.encode(),
        hashlib.sha256
    ).hexdigest()[:32]  # Tronquer à 32 caractères pour des URLs plus courtes
    
    # Retourner token = payload.signature
    return f"{payload_b64}.{signature}"


def verify_token(token: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    Vérifie et décode un token
    
    Args:
        token: Le token à vérifier
    
    Returns:
        Tuple (is_valid, payload, error_message)
        - is_valid: True si le token est valide
        - payload: Dict avec action, resource_id, email si valide, None sinon
        - error_message: Message d'erreur si invalide, None sinon
    
    Exemple:
        valid, data, error = verify_token(token)
        if valid:
            print(f"Action: {data['action']}, ID: {data['resource_id']}")
        else:
            print(f"Erreur: {error}")
    """
    try:
        # Séparer payload et signature
        if '.' not in token:
            return False, None, "Format de token invalide"
        
        payload_b64, signature = token.rsplit('.', 1)
        
        # Vérifier la signature
        expected_signature = hmac.new(
            SECRET_KEY.encode(),
            payload_b64.encode(),
            hashlib.sha256
        ).hexdigest()[:32]
        
        if not hmac.compare_digest(signature, expected_signature):
            return False, None, "Signature invalide"
        
        # Décoder le payload
        import base64
        # Ajouter le padding manquant
        padding = 4 - (len(payload_b64) % 4)
        if padding != 4:
            payload_b64 += '=' * padding
        
        payload_json = base64.urlsafe_b64decode(payload_b64).decode()
        payload = json.loads(payload_json)
        
        # Vérifier l'expiration
        if payload.get('exp', 0) < time.time():
            return False, None, "Token expiré"
        
        return True, payload, None
        
    except Exception as e:
        return False, None, f"Erreur de décodage: {str(e)}"


def generate_accept_link(reservation_id: int, driver_email: str, base_url: str = "http://localhost:5000") -> str:
    """
    Génère un lien pour accepter une réservation
    
    Args:
        reservation_id: ID de la réservation
        driver_email: Email du conducteur
        base_url: URL de base du site
    
    Returns:
        URL complète avec token
    
    Exemple:
        link = generate_accept_link(123, 'driver@example.com')
        # → "http://localhost:5000/api/reservation/accept?token=..."
    """
    token = generate_token('accept_reservation', reservation_id, driver_email)
    return f"{base_url}/api/reservation/accept?token={token}"


def generate_refuse_link(reservation_id: int, driver_email: str, base_url: str = "http://localhost:5000") -> str:
    """Génère un lien pour refuser une réservation"""
    token = generate_token('refuse_reservation', reservation_id, driver_email)
    return f"{base_url}/api/reservation/refuse?token={token}"


def generate_cancel_passenger_link(reservation_id: int, passenger_email: str, base_url: str = "http://localhost:5000") -> str:
    """Génère un lien pour qu'un passager annule sa réservation"""
    token = generate_token('cancel_passenger', reservation_id, passenger_email)
    return f"{base_url}/api/reservation/cancel?token={token}"


def generate_remove_passenger_link(reservation_id: int, driver_email: str, base_url: str = "http://localhost:5000") -> str:
    """Génère un lien pour que le conducteur retire un passager"""
    token = generate_token('remove_passenger', reservation_id, driver_email)
    return f"{base_url}/api/reservation/remove?token={token}"


def generate_cancel_offer_link(offer_id: int, driver_email: str, base_url: str = "http://localhost:5000") -> str:
    """Génère un lien pour annuler une offre complète"""
    token = generate_token('cancel_offer', offer_id, driver_email)
    return f"{base_url}/api/offer/cancel?token={token}"


def generate_view_reservations_link(offer_id: int, driver_email: str, base_url: str = "http://localhost:5000") -> str:
    """Génère un lien pour voir toutes les réservations d'une offre"""
    token = generate_token('view_reservations', offer_id, driver_email, expires_in=86400 * 30)  # 30 jours
    return f"{base_url}/api/offer/reservations?token={token}"


# ============================================================================
# TESTS (à exécuter avec: python3 token_manager.py)
# ============================================================================

if __name__ == "__main__":
    print("🔐 Test du système de tokens\n")
    
    # Test 1: Générer et vérifier un token
    print("Test 1: Génération et vérification")
    token = generate_token('accept_reservation', 123, 'driver@example.com', expires_in=3600)
    print(f"Token généré: {token[:50]}...")
    
    valid, payload, error = verify_token(token)
    if valid:
        print(f"✅ Token valide!")
        print(f"   Action: {payload['action']}")
        print(f"   Resource ID: {payload['resource_id']}")
        print(f"   Email: {payload['email']}")
    else:
        print(f"❌ Token invalide: {error}")
    
    # Test 2: Token invalide
    print("\nTest 2: Token invalide")
    fake_token = "fake.token.here"
    valid, payload, error = verify_token(fake_token)
    print(f"❌ Résultat attendu: {error}")
    
    # Test 3: Token expiré
    print("\nTest 3: Token expiré")
    expired_token = generate_token('test', 1, 'test@example.com', expires_in=-1)
    valid, payload, error = verify_token(expired_token)
    print(f"❌ Résultat attendu: {error}")
    
    # Test 4: Génération de liens
    print("\nTest 4: Génération de liens")
    accept_link = generate_accept_link(123, 'driver@example.com', 'https://example.com')
    print(f"Lien accepter: {accept_link[:80]}...")
    
    refuse_link = generate_refuse_link(123, 'driver@example.com', 'https://example.com')
    print(f"Lien refuser: {refuse_link[:80]}...")
    
    cancel_link = generate_cancel_passenger_link(123, 'passenger@example.com', 'https://example.com')
    print(f"Lien annuler: {cancel_link[:80]}...")
    
    print("\n✅ Tous les tests passés!")
