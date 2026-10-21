# Décorateur pour gérer le cache avec expiration
import base64
import random
import string

import core.constants
from core.logger import logger
import datetime
import io, os
from PIL import Image


def cache_with_expiration(expiration_seconds):
    def decorator(func):
        import time
        cache = {}

        def wrapper(*args, **kwargs):
            # Vérifier si le résultat est dans le cache et s'il n'est pas expiré
            key = args + tuple(kwargs.items())
            if key in cache:
                result, timestamp = cache[key]
                if time.time() - timestamp < expiration_seconds:
                    return result

            # Appeler la fonction et mettre à jour le cache
            result = func(*args, **kwargs)
            cache[key] = (result, time.time())
            return result

        return wrapper

    return decorator


def trouver_nom_disponible(path, nom_base, extension):
    """
    Génère un nom de fichier unique en ajoutant "_bis" si le fichier existe déjà.
    """
    compteur = 0
    while True:
        # Premier essai sans suffixe
        if compteur == 0:
            nom_candidat = f"{nom_base}{extension}"
        # Essais suivants avec suffixe "_bis"
        else:
            nom_candidat = f"{nom_base}_bis{compteur}{extension}"

        if not os.path.exists(path+nom_candidat):
            logger.debug(f" on retourne le nom de fichier{nom_candidat}")
            return nom_candidat
        compteur += 1


def storeImage(b64img : str, filename : str) :
    nom_final = filename
    try:
        # Décoder les données Base64
        img_binaire = base64.b64decode(b64img)

        # on verifie l'existence ou pas
        nom, extension = os.path.splitext(filename)

        nom_final = filename
        # a utiliser si on ne veut pas ecraser
        # nom_final =trouver_nom_disponible(core.constants.SIGN_PATH, nom, extension))

        # Sauvegarder les données dans un fichier
        chemin_complet = os.path.join(core.constants.SIGN_PATH, nom_final)
        with open(chemin_complet, "wb") as fichier:
            fichier.write(img_binaire)

        logger.info(f"Le fichier image a été sauvegardé sous : {chemin_complet}")
        return nom_final
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde du fichier image {nom_final} : {e}")
        return False


@cache_with_expiration(600)
def get_image_size_in_points(b64img : str):
    image_data = base64.b64decode(b64img)

    # Charger l'image avec Pillow
    img = Image.open(io.BytesIO(image_data))
    width_px, height_px = img.size
    # Obtenir la résolution en DPI
    dpi = img.info.get('dpi', (72, 72))  # Par défaut, 72 DPI si non spécifié
    # Calculer la taille en points
    width = int(width_px * 72 / dpi[0])
    height = int(height_px * 72 / dpi[1])
    logger.info(f" image calc : {width} {height}")

    return  width, height


def generate_unique_filename(extension: str = "pdf") -> str:
    """
    Génère un nom de fichier unique basé sur l'heure, la date et une chaîne aléatoire.
    :param extension: Extension du fichier (par défaut "pdf").
    :return: Nom de fichier unique.
    """
    # Obtenir l'heure et la date actuelles
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")  # Format : AAAAMMJJ_HHMMSS

    # Générer une chaîne aléatoire de 4 caractères
    random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=4))

    # Combiner les éléments pour créer un nom de fichier unique
    filename = f"{timestamp}_{random_string}.{extension}"

    return filename


def file_chunk_generator(file_like, chunk_size: int = 8192):
    """
    Génère des morceaux (chunks) du fichier.
    :param file_like: Fichier en mémoire (io.BytesIO).
    :param chunk_size: Taille des morceaux (par défaut 8 Ko).
    :yield: Morceaux du fichier.
    """
    while chunk := file_like.read(chunk_size):
        yield chunk
