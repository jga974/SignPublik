# Décorateur pour gérer le cache avec expiration
import base64
import random
import string

import app.core.constants
from app.core.logger import logger
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
        # Nettoyage strict anti Path Traversal
        nom_propre = os.path.basename(filename)
        # Supprimer caractères dangereux ou de contrôle
        nom_propre = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', nom_propre)
        if not nom_propre or nom_propre.startswith('.'):
            nom_propre = f"img_{generate_unique_filename(extension='png')}"

        nom, extension = os.path.splitext(nom_propre)
        if extension.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
            extension = '.png'
            nom_propre = f"{nom}{extension}"

        nom_final = nom_propre
        target_dir = os.path.abspath(app.core.constants.SIGN_PATH)
        chemin_complet = os.path.abspath(os.path.join(target_dir, nom_final))

        # Vérification formelle du confinement dans SIGN_PATH
        if not (chemin_complet == target_dir or chemin_complet.startswith(target_dir + os.sep)):
            logger.error(f"Tentative de Path Traversal bloquée pour le fichier : {filename}")
            return False

        # Décoder les données Base64
        img_binaire = base64.b64decode(b64img)

        # Sauvegarder les données dans un fichier
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

def nettoyer_chaine_avancee(texte, garder_chiffres=True, garder_espaces=False, remplacer_espaces_par='_'):
    """
    Version avancée avec options personnalisables

    Args:
        texte (str): La chaîne à nettoyer
        garder_chiffres (bool): Garder les chiffres
        garder_espaces (bool): Garder les espaces
        remplacer_espaces_par (str): Caractère de remplacement pour les espaces

    Returns:
        str: La chaîne nettoyée
    """
    # Supprimer les accents
    texte_normalise = unicodedata.normalize('NFD', texte)
    texte_sans_accents = ''.join(
        char for char in texte_normalise
        if unicodedata.category(char) != 'Mn'
    )

    # Construire le pattern selon les options (SANS inclure \s si on veut remplacer)
    if garder_chiffres:
        if garder_espaces or remplacer_espaces_par:  # Garder temporairement les espaces
            pattern = r'[^a-zA-Z0-9\s]'
        else:
            pattern = r'[^a-zA-Z0-9]'
    else:
        if garder_espaces or remplacer_espaces_par:  # Garder temporairement les espaces
            pattern = r'[^a-zA-Z\s]'
        else:
            pattern = r'[^a-zA-Z]'

    # Supprimer les caractères indésirables
    texte_nettoye = re.sub(pattern, '', texte_sans_accents)

    # Remplacer les espaces si nécessaire
    if not garder_espaces and remplacer_espaces_par:
        texte_nettoye = re.sub(r'\s+', remplacer_espaces_par, texte_nettoye)

    return texte_nettoye


import unicodedata
import re


def nettoyer_chaine_complete(texte, **options):
    """
    Version complète avec dictionnaire d'options

    Args:
        texte (str): La chaîne à nettoyer
        **options: Options de nettoyage
            - garder_chiffres (bool): Garder les chiffres (défaut: True)
            - garder_espaces (bool): Garder les espaces (défaut: False)
            - remplacer_espaces_par (str): Caractère de remplacement (défaut: '')
            - minuscules (bool): Convertir en minuscules (défaut: False)
            - garder_tirets (bool): Garder les tirets (défaut: False)

    Returns:
        str: La chaîne nettoyée
    """
    # Options par défaut
    config = {
        'garder_chiffres': True,
        'garder_espaces': False,
        'remplacer_espaces_par': '',
        'minuscules': False,
        'garder_tirets': False
    }
    config.update(options)

    if not isinstance(texte, str):
        return ''

    # Supprimer les accents
    texte_normalise = unicodedata.normalize('NFD', texte)
    texte_sans_accents = ''.join(
        char for char in texte_normalise
        if unicodedata.category(char) != 'Mn'
    )

    # Construire le pattern selon les options
    # TOUJOURS garder les espaces temporairement pour le traitement final
    pattern_parts = ['a-zA-Z', r'\s']  # Toujours inclure les espaces

    if config['garder_chiffres']:
        pattern_parts.append('0-9')

    if config['garder_tirets']:
        pattern_parts.append(r'\-')

    pattern = f"[^{''.join(pattern_parts)}]"

    # Supprimer les caractères indésirables
    texte_nettoye = re.sub(pattern, '', texte_sans_accents)

    # Traitement final des espaces selon la priorité
    if config['remplacer_espaces_par']:
        # Priorité 1 : Remplacer par un caractère spécifique
        texte_nettoye = re.sub(r'\s+', config['remplacer_espaces_par'], texte_nettoye)
    elif config['garder_espaces']:
        # Priorité 2 : Garder les espaces (normalisés)
        texte_nettoye = re.sub(r'\s+', ' ', texte_nettoye).strip()
    else:
        # Priorité 3 : Supprimer tous les espaces
        texte_nettoye = re.sub(r'\s+', '', texte_nettoye)

    # Conversion en minuscules si demandée
    if config['minuscules']:
        texte_nettoye = texte_nettoye.lower()

    return texte_nettoye

def slugify(texte) :
    return nettoyer_chaine_complete(texte, garder_espaces=True,
                                    remplacer_espaces_par='-',
                                    minuscules=True)

