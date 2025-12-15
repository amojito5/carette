"""
Serveur Flask simple pour servir le widget Carette (frontend + API)
Usage: gunicorn -w 2 -b 0.0.0.0:8080 serve:app
"""
from flask import Flask, send_from_directory
from flask_cors import CORS
import os

# Import de l'API backend
from backend.api import app as api_app

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Dossier racine du projet
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Servir les fichiers frontend
@app.route('/')
@app.route('/demo.html')
def demo():
    return send_from_directory(BASE_DIR, 'demo.html')

@app.route('/frontend/<path:filename>')
def frontend(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'frontend'), filename)

@app.route('/docs/<path:filename>')
def docs(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'docs'), filename)

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'static'), filename)

# Monter l'API backend sur /api
@app.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def api_proxy(path):
    """Proxy vers l'API backend"""
    from flask import request
    with api_app.test_client() as client:
        # Construire URL complète avec paramètres
        url = f'/api/{path}'
        if request.query_string:
            url += f'?{request.query_string.decode()}'
        
        if request.method == 'GET':
            resp = client.get(url)
        elif request.method == 'POST':
            resp = client.post(url, json=request.get_json())
        elif request.method == 'DELETE':
            resp = client.delete(url, json=request.get_json())
        else:
            resp = client.open(url, method=request.method)
        
        return resp.get_data(), resp.status_code, resp.headers.items()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
