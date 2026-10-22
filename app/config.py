import os
from pathlib import Path

# Tentative de chargement du fichier .env s'il existe
env_path = Path(__file__).resolve().parent.parent / '.env'
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=env_path)
    except ImportError:
        # Fallback si python-dotenv n'est pas installé : parsing basique
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ.setdefault(key.strip(), val.strip())

API_KEY = os.getenv("API_KEY", "DEV_DEFAULT_API_KEY")
SHARED_SECRET = os.getenv("SHARED_SECRET", "DEV_DEFAULT_SHARED_SECRET")
OMOGEN_SECRET_KEY = os.getenv("OMOGEN_SECRET_KEY", "DEV_DEFAULT_OMOGEN_KEY")

# Protection de sécurité : empêcher l'utilisation des clés par défaut en production (VULN-05)
if os.getenv("ENV", "").lower() in ("prod", "production") and API_KEY == "DEV_DEFAULT_API_KEY":
    raise RuntimeError("ERREUR CRITIQUE DE SÉCURITÉ : L'API_KEY par défaut ne peut pas être utilisée en production. Définissez API_KEY dans votre fichier .env.")

