import os

# Répertoire racine du projet (un niveau au-dessus de core)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Répertoire de stockage des fichiers de signature et certificats
SIGN_PATH = os.path.join(BASE_DIR, "signature_files")
CERT_PATH = os.path.join(BASE_DIR, "ssl")

# S'assurer que le répertoire existe
os.makedirs(SIGN_PATH, exist_ok=True)
