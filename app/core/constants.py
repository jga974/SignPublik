import os

# Répertoire racine du projet (deux niveaux au-dessus de app/core)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Répertoire de stockage des fichiers de signature et certificats
SIGN_PATH = os.path.join(BASE_DIR, "signature_files")
CERT_PATH = os.path.join(BASE_DIR, "ssl")

# Polices embarquées (indépendant du répertoire de lancement)
FONTS_DIR = os.path.join(BASE_DIR, "app", "core", "fonts")

# Certificat / clé de signature par défaut (si le signataire n'a pas les siens)
DEFAULT_CERT_FILE = os.path.join(BASE_DIR, "cert.pem")
DEFAULT_KEY_FILE = os.path.join(BASE_DIR, "private_key.pem")

# S'assurer que le répertoire existe
os.makedirs(SIGN_PATH, exist_ok=True)
