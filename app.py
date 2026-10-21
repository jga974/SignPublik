from flask import Flask, request, send_file, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded

import os
import time

# Dictionnaire pour stocker les échecs avec un timestamp
failed_attempts = {}

app = Flask(__name__)

# Secret partagé (à garder confidentiel)
SHARED_SECRET = os.getenv("SHARED_SECRET", "votre_secret_partage_ici")

# Configurer Flask-Limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,  # Utiliser l'adresse IP du client comme clé
    default_limits=["5 per minute"]  # Limite par défaut : 5 requêtes par minute
)

@app.route('/upload', methods=['POST'])
@limiter.limit("20 per minute")  # Limite spécifique pour cette route : 3 tentatives par minute
def upload_pdf():
    # Vérifier la présence du secret dans l'en-tête
    auth_header = request.headers.get('Authorization')

    client_ip = get_remote_address()

    # Supprimer les échecs expirés (plus de 5 minutes)
    current_time = time.time()
    failed_attempts[client_ip] = {
        timestamp: count for timestamp, count in failed_attempts.get(client_ip, {}).items()
        if current_time - timestamp < 300  # 5 minutes
    }


    if not auth_header or auth_header != f"Bearer {SHARED_SECRET}":
        # Incrémenter le compteur d'échecs pour cette IP
        failed_attempts[client_ip] = failed_attempts.get(client_ip, {})
        failed_attempts[client_ip][current_time] = failed_attempts[client_ip].get(current_time, 0) + 1

        # Appliquer une limite stricte après 3 échecs
        if sum(failed_attempts[client_ip].values()) > 3:
            return jsonify({"error": "Trop de tentatives échouées. Veuillez réessayer plus tard."}), 429

        return jsonify({"error": "Accès non autorisé"}), 401

    # Réinitialiser le compteur d'échecs en cas de succès
    failed_attempts[client_ip] = {}


    # Vérifier la présence du fichier
    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier fourni"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "Aucun fichier sélectionné"}), 400

    if file and file.filename.endswith('.pdf'):
        # Sauvegarder temporairement le fichier
        file_path = os.path.join('/tmp', file.filename)
        file.save(file_path)

        # Renvoyer le fichier PDF
        return send_file(file_path, as_attachment=True)

    return jsonify({"error": "Format de fichier non supporté"}), 400

@app.errorhandler(RateLimitExceeded)
def handle_rate_limit_exceeded(e):
    return jsonify({"error": "Trop de tentatives. Veuillez réessayer dans 1 minute."}), 429

if __name__ == '__main__':
    app.run(debug=True)

