import logging

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),  # Enregistrer les logs dans un fichier
        logging.StreamHandler()  # Afficher les logs dans la console
    ]
)
logger = logging.getLogger(__name__)
