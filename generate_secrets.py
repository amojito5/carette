#!/usr/bin/env python3
"""
Script de génération de secrets sécurisés pour Carette
Génère des clés aléatoires cryptographiquement sûres
"""
import secrets
import sys

def generate_secret(length=32):
    """Génère une clé secrète hexadécimale"""
    return secrets.token_hex(length)

def generate_password(length=24):
    """Génère un mot de passe sécurisé"""
    import string
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def main():
    print("🔐 Génération des secrets pour Carette")
    print("=" * 50)
    print()
    
    print("# Copiez ces valeurs dans votre fichier .env")
    print("# Ne JAMAIS commiter ces valeurs dans Git !")
    print()
    
    print("# Clés secrètes Flask/JWT")
    print(f"CARETTE_SECRET_KEY={generate_secret(32)}")
    print(f"JWT_SECRET_KEY={generate_secret(32)}")
    print()
    
    print("# Mots de passe base de données")
    print(f"CARETTE_DB_PASSWORD={generate_password(24)}")
    print(f"CARETTE_DB_ROOT_PASSWORD={generate_password(24)}")
    print()
    
    print("=" * 50)
    print("✅ Secrets générés avec succès !")
    print()
    print("📋 Prochaines étapes:")
    print("1. Copiez les valeurs ci-dessus dans votre fichier .env")
    print("2. Vérifiez que .env est dans .gitignore")
    print("3. Ne partagez JAMAIS ces secrets")
    print("4. Régénérez les secrets si compromis")

if __name__ == '__main__':
    main()
