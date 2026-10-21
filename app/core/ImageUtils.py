from PIL import Image, ImageDraw, ImageFont

from app.core.logger import logger
from app.core.constants import SIGN_PATH, FONTS_DIR
import os

def creer_signature_png_transparente(texte=None, image_source=None,
                                     nom_fichier_sortie="signature_transparente.png",
                                     taille_image=(125, 85), taille_police=20,
                                     couleur_texte=(0, 0, 0, 255)) :
    """
    Crée une image PNG avec fond transparent pour une signature

    Args:
        texte (str): Texte à utiliser comme signature (optionnel)
        image_source (str): Chemin vers une image de signature existante (optionnel)
        nom_fichier_sortie (str): Nom du fichier de sortie
        taille_image (tuple): Dimensions de l'image (largeur, hauteur)
        taille_police (int): Taille de la police si texte utilisé
        couleur_texte (tuple): Couleur RGBA du texte
    """

    if not os.path.dirname(nom_fichier_sortie):
        nom_fichier_sortie = os.path.join(SIGN_PATH, nom_fichier_sortie)

    dossier = os.path.dirname(nom_fichier_sortie)
    if dossier:
        os.makedirs(dossier, exist_ok=True)

    if os.path.exists(nom_fichier_sortie):
        os.remove(nom_fichier_sortie)

    if image_source:
        # Utiliser une image existante
        try:
            # Ouvrir l'image source
            img_source = Image.open(image_source)

            # Convertir en RGBA si ce n'est pas déjà le cas
            if img_source.mode != 'RGBA':
                img_source = img_source.convert('RGBA')

            # Créer un masque à partir de l'image (supposant fond blanc)
            # Convertir en niveaux de gris
            img_gris = img_source.convert('L')

            # Créer un masque où le blanc devient transparent
            # Inverser les valeurs pour que le texte foncé reste opaque
            masque = Image.eval(img_gris, lambda x: 255 if x < 240 else 0)

            # Appliquer le masque
            img_source.putalpha(masque)

            # Redimensionner si nécessaire
            if img_source.size != taille_image:
                img_source = img_source.resize(taille_image, Image.LANCZOS)

            # Sauvegarder l'image
            img_source.save(nom_fichier_sortie, "PNG")
            return nom_fichier_sortie

        except Exception as e:
            print(f"Erreur lors du traitement de l'image source: {e}")
            # En cas d'erreur, on continue avec la méthode texte

    # Méthode par défaut: créer une image avec du texte
    # Créer une image avec fond transparent (mode RGBA)
    image = Image.new("RGBA", taille_image, (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)


    # Charger une police manuscrite (par défaut une police système)
    font = None
    try:
        # Essayer de charger une police manuscrite si disponible
        font = ImageFont.truetype(os.path.join(FONTS_DIR, "BonheurRoyale-Regular.ttf"), taille_police)
    except IOError:
        print("on ne trouve pas la font BonheurRoyale-Regular.ttf dans", FONTS_DIR)


    #family, style = font.getname()
    #"Bonheur Royale"
    #print("Nom de famille :", family)
    #print("Style :", style)
    # Charger une police manuscrite (par défaut une police système)
    if font is None :
        try:
            # Essayer de charger une police manuscrite si disponible
            font = ImageFont.truetype(os.path.join(FONTS_DIR, "BonheurRoyale-Regular.ttf"), taille_police)
        except IOError:
            print("on ne trouve pas la font BonheurRoyale-Regular.ttf dans", FONTS_DIR)
            font = ImageFont.load_default()

    family, style = font.getname()
    print("Nom de famille :", family)
    print("Style :", style)

    logger.info(f"on utilise police {family} {taille_police}")
    # Calculer la taille du texte pour le centrer
    bbox = draw.textbbox((0, 0), texte, font=font)
    largeur_texte = bbox[2] - bbox[0]
    hauteur_texte = bbox[3] - bbox[1]

    position = ((taille_image[0] - largeur_texte) // 2,
                (taille_image[1] - hauteur_texte) // 2)

    # Dessiner le texte sur l'image
    draw.text(position, texte, font=font, fill=couleur_texte)

    # Sauvegarder l'image PNG
    image.save(nom_fichier_sortie, "PNG")
    return nom_fichier_sortie


# Exemple d'utilisation avec l'image partagée
# fichier_cree = creer_signature_png_transparente(image_source="chemin/vers/votre/image.png")

# Ou avec du texte
#fichier_cree = creer_signature_png_transparente(texte="Jean-Guy Avelin")

# CLAUDE :


def creer_image_texte_manuscrit(texte, taille_image, nom_fichier="texte_manuscrit.png"):
    """
    Crée une image PNG avec du texte stylisé manuscrit.

    Args:
        texte (str): Le texte à afficher sur l'image
        taille_image (tuple): Tuple (largeur, hauteur) en pixels
        nom_fichier (str): Nom du fichier de sortie (optionnel)

    Returns:
        str: Chemin vers le fichier créé
    """
    if not os.path.dirname(nom_fichier):
        nom_fichier = os.path.join(SIGN_PATH, nom_fichier)

    dossier = os.path.dirname(nom_fichier)
    if dossier:
        os.makedirs(dossier, exist_ok=True)

    # Créer une nouvelle image avec fond blanc
    largeur, hauteur = taille_image
    image = Image.new('RGBA', (largeur, hauteur), color=(255,255,255,0))
    draw = ImageDraw.Draw(image)

    # Essayer de charger une police manuscrite
    try:
        # Tenter de charger une police système manuscrite
        # Sur Windows, essayer quelques polices manuscrites courantes
        polices_manuscrites = [
            "C:/Windows/Fonts/comic.ttf",  # Comic Sans MS
            "C:/Windows/Fonts/bradley.ttf",  # Bradley Hand
            "C:/Windows/Fonts/segoepr.ttf",  # Segoe Print
            "/System/Library/Fonts/Chalkduster.ttf",  # macOS
            "/System/Library/Fonts/Bradley Hand Bold.ttf",  # macOS
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",  # Linux
        ]

        police = None
        taille_police = min(largeur, hauteur) // 10  # Ajuster selon la taille de l'image

        for chemin_police in polices_manuscrites:
            if os.path.exists(chemin_police):
                try:
                    police = ImageFont.truetype(chemin_police, taille_police)
                    break
                except:
                    continue

        # Si aucune police manuscrite n'est trouvée, utiliser la police par défaut
        if police is None:
            police = ImageFont.load_default()

    except Exception as e:
        print(f"Erreur lors du chargement de la police: {e}")
        police = ImageFont.load_default()

    # Calculer la position pour centrer le texte
    bbox = draw.textbbox((0, 0), texte, font=police)
    text_largeur = bbox[2] - bbox[0]
    text_hauteur = bbox[3] - bbox[1]

    x = (largeur - text_largeur) // 2
    y = (hauteur - text_hauteur) // 2

    # Dessiner le texte avec une couleur sombre
    couleur_texte = (50, 50, 50)  # Gris foncé pour un effet plus naturel
    draw.text((x, y), texte, font=police, fill=couleur_texte)

    # Sauvegarder l'image
    image.save(nom_fichier, 'PNG')
    print(f"Image créée avec succès: {nom_fichier}")

    return nom_fichier


def creer_image_texte_manuscrit_avance(texte, taille_image, nom_fichier="texte_manuscrit.png",
                                        fond_transparent=True,
                                       couleur_fond=(255, 255, 255,0), couleur_texte=(50, 50, 50), taille_police=20,
                                       horodatage=""):
    """
    Version avancée avec plus d'options de personnalisation.

    Args:
        texte (str): Le texte à afficher
        taille_image (tuple): Tuple (largeur, hauteur) en pixels
        nom_fichier (str): Nom du fichier de sortie
        couleur_fond (tuple): Couleur RGB du fond
        couleur_texte (tuple): Couleur RGB du texte
        fond_transparent (bool): True pour fond transparent, False pour fond blanc

    Returns:
        str: Chemin vers le fichier créé
        :param taille_police:
    """

    if not os.path.dirname(nom_fichier):
        nom_fichier = os.path.join(SIGN_PATH, nom_fichier)

    dossier = os.path.dirname(nom_fichier)
    if dossier:
        os.makedirs(dossier, exist_ok=True)

    if os.path.exists(nom_fichier):
        os.remove(nom_fichier)

    largeur, hauteur = taille_image
    image = Image.new('RGBA', (largeur, hauteur), color=couleur_fond)
    if fond_transparent:
        # Fond transparent
        image = Image.new('RGBA', (largeur, hauteur), color=couleur_fond)
    else:
        # Fond blanc
        image = Image.new('RGB', (largeur, hauteur), color=(255, 255, 255))

    draw = ImageDraw.Draw(image)

    # Gestion des polices avec tailles adaptatives
    polices_manuscrites = [
        os.path.join(FONTS_DIR, "bradley-hand-itc-tt-bold.ttf"),
        os.path.join(FONTS_DIR, "BonheurRoyale-Regular.ttf"),
        os.path.join(FONTS_DIR, "Jennifer Lynne Bold.ttf"),
        "/System/Library/Fonts/Chalkduster.ttf",
        "/System/Library/Fonts/Bradley Hand Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]

    # Ajuster la taille de police selon le texte et l'image
    # original taille_police = max(12, min(largeur, hauteur) // max(8, len(texte) // 4))
    taille_police = min(26, min(largeur, hauteur) // max(4, len(texte) // 8))
    logger.info(f"******OLD police de {taille_police}, l {largeur}, h :{hauteur} calcul : {max(4, len(texte) // 8)}  calcul :{min(largeur, hauteur) // max(4, len(texte) // 8)}")
    print(f"******police de {taille_police}, l {largeur}, h :{hauteur} calcul : {max(4, len(texte) // 8)}  calcul :{min(largeur, hauteur) // max(4, len(texte) // 8)}")
    # MODIF 7/725, calcul taille_police
    # Try decreasing font sizes until the text fits
    max_font_size=36
    min_font_size=8

    # Fonction utilitaire pour obtenir la taille du texte via textbbox
    def get_text_size(txt, font):
        bbox = draw.textbbox((0, 0), txt, font=font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        return width, height

    for font_size in range(max_font_size, min_font_size - 1, -1):
        font = ImageFont.truetype(os.path.join(FONTS_DIR, "bradley-hand-itc-tt-bold.ttf"), font_size)
        text_width, text_height = get_text_size(texte, font)
        if text_width <= largeur and text_height <= hauteur:
            break
    else:
        logger.warning("Text is too large to fit even at the minimum font size.")

    print(f"ON CHOISIR LA TAILLE {font_size} pour {texte}")
    logger.info(f"ON CHOISIT LA TAILLE {font_size} pour {texte}")
    taille_police = font_size
    # fin de la bidouille

    police = None
    for chemin_police in polices_manuscrites:
        logger.debug(f"charge police {chemin_police}")
        if os.path.exists(chemin_police):
            try:
                police = ImageFont.truetype(chemin_police, taille_police)
                logger.debug(f"on utilise la police {police.getname()}")
                break
            except:
                logger.error(f"Erreur police {chemin_police}")
                continue

    if police is None:
        police = ImageFont.load_default()

    # Gestion du texte multiligne
    lignes = texte.split('\n')

    # Calculer la hauteur totale du texte
    hauteur_ligne = taille_police + 5
    hauteur_totale = len(lignes) * hauteur_ligne

    # Position de départ pour centrer verticalement
    y_start = (hauteur - hauteur_totale) // 2

    # Dessiner chaque ligne
    for i, ligne in enumerate(lignes):
        bbox = draw.textbbox((0, 0), ligne, font=police)
        text_largeur = bbox[2] - bbox[0]
        x = (largeur - text_largeur) // 2
        y = y_start + i * hauteur_ligne

        draw.text((x, y), ligne, font=police, fill=couleur_texte)

    # police pour horodatage
    police = None
    taille_police = 10
    logger.info("police deja vu")
    # Localiser la police DejaVuSans
    font_path = os.path.join(FONTS_DIR, "DejaVuSans.ttf")
    police = ImageFont.truetype(font_path, taille_police)
    logger.info("police deja vu OK taille :" + str(taille_police))
    if horodatage != '' :
        bbox = draw.textbbox((0, 0), horodatage, font=police)
        text_largeur = bbox[2] - bbox[0]
        x = 1
        y = y_start + len(texte.split('\n')) * hauteur_ligne
        draw.text((x, y), horodatage, font=police, fill=couleur_texte)


    # Sauvegarder l'image
    image.save(nom_fichier, 'PNG')
    print(f"Image créée avec succès: {nom_fichier}")

    return nom_fichier


# Exemple d'utilisation
if __name__ == "__main__":
    # Exemple simple
    texte1 = "Bonjour le monde!"
    taille1 = (800, 400)
    creer_image_texte_manuscrit(texte1, taille1, "exemple1.png")

    # Exemple avec texte multiligne
    texte2 = "Ceci est un exemple\nde texte manuscrit\nsur plusieurs lignes"
    taille2 = (600, 300)
    creer_image_texte_manuscrit_avance(texte2, taille2, "exemple2.png", couleur_fond=(248, 248, 240),
                                       couleur_texte=(70, 70, 70), taille_police=20)
