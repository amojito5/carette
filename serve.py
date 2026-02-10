"""
Serveur Flask simple pour servir le widget Carette (frontend + API)
Usage: gunicorn -w 2 -b 0.0.0.0:9000 serve:app
"""
from flask import Flask, send_from_directory, request, abort
from werkzeug.security import safe_join
import os
from dotenv import load_dotenv

# Charger les variables d'environnement AVANT d'importer backend
load_dotenv(os.path.join(os.path.dirname(__file__), 'backend', '.env'))

# Import de l'app API backend
from backend.api import app as backend_app

# Dossier racine du projet
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Fichiers autorisés pour l'accès public
ALLOWED_FILES = {'demo.html', 'demo-recurrent.html', 'demo-rse.html', 'index.md'}
ALLOWED_EXTENSIONS = {'.html', '.js', '.css', '.md', '.json', '.png', '.jpg', '.jpeg', '.svg', '.ico'}

def is_safe_path(base, path, follow_symlinks=True):
    """Vérifie que le chemin demandé est sûr et dans le dossier autorisé"""
    if follow_symlinks:
        return os.path.realpath(path).startswith(os.path.realpath(base))
    return os.path.abspath(path).startswith(os.path.abspath(base))

# Ajouter les routes frontend au backend_app
@backend_app.route('/')
@backend_app.route('/demo.html')
def demo():
    """Page de démonstration"""
    file_path = os.path.join(BASE_DIR, 'demo.html')
    if not os.path.exists(file_path) or not is_safe_path(BASE_DIR, file_path):
        abort(404)
    return send_from_directory(BASE_DIR, 'demo.html')

@backend_app.route('/demo-recurrent.html')
def demo_recurrent():
    """Page de démonstration mode récurrent"""
    file_path = os.path.join(BASE_DIR, 'demo-recurrent.html')
    if not os.path.exists(file_path) or not is_safe_path(BASE_DIR, file_path):
        abort(404)
    return send_from_directory(BASE_DIR, 'demo-recurrent.html')

@backend_app.route('/demo-rse.html')
def demo_rse():
    """Page de démonstration mode RSE"""
    file_path = os.path.join(BASE_DIR, 'demo-rse.html')
    if not os.path.exists(file_path) or not is_safe_path(BASE_DIR, file_path):
        abort(404)
    return send_from_directory(BASE_DIR, 'demo-rse.html')

@backend_app.route('/rse-edit-week.html')
def rse_edit_week():
    """Page d'édition hebdomadaire RSE (magic link)"""
    file_path = os.path.join(BASE_DIR, 'rse-edit-week.html')
    if not os.path.exists(file_path) or not is_safe_path(BASE_DIR, file_path):
        abort(404)
    return send_from_directory(BASE_DIR, 'rse-edit-week.html')

@backend_app.route('/landing.html')
@backend_app.route('/index.html')
def landing():
    """Landing page commerciale"""
    file_path = os.path.join(BASE_DIR, 'landing.html')
    if not os.path.exists(file_path) or not is_safe_path(BASE_DIR, file_path):
        abort(404)
    return send_from_directory(BASE_DIR, 'landing.html')

@backend_app.route('/dashboard-company.html')
def dashboard_company():
    """Dashboard entreprise"""
    file_path = os.path.join(BASE_DIR, 'dashboard-company.html')
    if not os.path.exists(file_path) or not is_safe_path(BASE_DIR, file_path):
        abort(404)
    return send_from_directory(BASE_DIR, 'dashboard-company.html')

@backend_app.route('/signup.html')
@backend_app.route('/signup')
def signup():
    """Formulaire d'inscription entreprise"""
    file_path = os.path.join(BASE_DIR, 'signup.html')
    if not os.path.exists(file_path) or not is_safe_path(BASE_DIR, file_path):
        abort(404)
    return send_from_directory(BASE_DIR, 'signup.html')

@backend_app.route('/manage-employees-new.html')
@backend_app.route('/manage-employees.html')
def manage_employees():
    """Page de gestion des employés"""
    file_path = os.path.join(BASE_DIR, 'manage-employees-new.html')
    if not os.path.exists(file_path) or not is_safe_path(BASE_DIR, file_path):
        abort(404)
    return send_from_directory(BASE_DIR, 'manage-employees-new.html')

@backend_app.route('/legal/<path:filename>')
def legal_pages(filename):
    """Pages légales"""
    if filename.startswith('.') or '..' in filename:
        abort(404)
    file_path = safe_join(os.path.join(BASE_DIR, 'legal'), filename)
    if not file_path or not os.path.exists(file_path) or not is_safe_path(os.path.join(BASE_DIR, 'legal'), file_path):
        abort(404)
    return send_from_directory(os.path.join(BASE_DIR, 'legal'), filename)

@backend_app.route('/frontend/<path:filename>')
def frontend(filename):
    """Fichiers frontend (JS, CSS)"""
    # Bloquer les fichiers cachés et navigation parent
    if filename.startswith('.') or '..' in filename:
        abort(404)
    
    # Vérifier l'extension
    _, ext = os.path.splitext(filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        abort(403)
    
    file_path = safe_join(os.path.join(BASE_DIR, 'frontend'), filename)
    if not file_path or not os.path.exists(file_path) or not is_safe_path(os.path.join(BASE_DIR, 'frontend'), file_path):
        abort(404)
    
    return send_from_directory(os.path.join(BASE_DIR, 'frontend'), filename)

@backend_app.route('/docs/<path:filename>')
def docs(filename):
    """Documentation publique"""
    # Bloquer les fichiers cachés et navigation parent
    if filename.startswith('.') or '..' in filename:
        abort(404)
    
    # Vérifier l'extension
    _, ext = os.path.splitext(filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        abort(403)
    
    file_path = safe_join(os.path.join(BASE_DIR, 'docs'), filename)
    if not file_path or not os.path.exists(file_path) or not is_safe_path(os.path.join(BASE_DIR, 'docs'), file_path):
        abort(404)
    
    return send_from_directory(os.path.join(BASE_DIR, 'docs'), filename)

@backend_app.route('/static/<path:filename>')
def static_files(filename):
    """Fichiers statiques (images, etc.)"""
    # Bloquer les fichiers cachés et navigation parent
    if filename.startswith('.') or '..' in filename:
        abort(404)
    
    # Vérifier l'extension
    _, ext = os.path.splitext(filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        abort(403)
    
    file_path = safe_join(os.path.join(BASE_DIR, 'static'), filename)
    if not file_path or not os.path.exists(file_path) or not is_safe_path(os.path.join(BASE_DIR, 'static'), file_path):
        abort(404)
    
    return send_from_directory(os.path.join(BASE_DIR, 'static'), filename)

# Utiliser directement backend_app
app = backend_app

if __name__ == '__main__':
    port = int(os.getenv('CARETTE_API_PORT', 9000))
    app.run(host='0.0.0.0', port=port, debug=False)
