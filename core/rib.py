import re
import pypdf
from core.logger import logger
from pypdf import PdfReader
from pypdf import errors

def extract_text_from_pdf_stream(pdf_stream):
    """Extrait le texte d'un fichier PDF"""
    # Lire le PDF avec PyPDF2
    text = ""
    try:
        lecteur_pdf = PdfReader(pdf_stream)
        for page in lecteur_pdf.pages:
            text += page.extract_text()
    except FileNotFoundError:
        logger.warning(f"Erreur : fichier non trouvé.")
    except errors.PdfReadError:
        logger.warning(f"Erreur : le fichier n'est pas un PDF valide ou est corrompu.")
    except OSError as e:
        logger.warning(f"Erreur d'accès au fichier : {e}")
    except Exception as e:
        logger.warning(f"Erreur inattendue : {e}")
    return text


def extract_ibans(text):
    """Trouve les IBAN dans le texte avec regex"""
    # ancienne version trop permissive pattern = r'\b[A-Z]{2}(?:\s?[0-9A-Z]){13,30}\b'
    # frenche only !
    pattern =r'\b(?:FR\d{2}(?:\s?[0-9A-Z]){23}|IT\d{2}[A-Z](?:\s?\d){10}(?:\s?[0-9A-Z]){12})\b'
    ibans = re.findall(pattern, text, re.IGNORECASE)
    logger.debug(ibans)
    # BIC (8 ou 11 caractères, lettres/chiffres, commence par 4 lettres banque, 2 lettres pays, 2 lettres lieu, 3 optionnels)
    # OLD : bic_regex = r'\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?\b'
    # banques francaises only
    bic_regex = r'\b[A-Z]{4}FR[A-Z0-9]{2}([A-Z0-9]{3})?\b'
    bics = re.findall(bic_regex, text, re.IGNORECASE)
    bics = [m.group(0) for m in re.finditer(bic_regex, text, re.IGNORECASE)]
    logger.debug(f"BICS LUS : {bics}")
    # Nettoyage éventuel (enlève espaces, majuscules)
    #ibans = [iban.replace(" ", "").upper() for iban in ibans]
    #bics = [bic.upper() for bic in bics]

    return [re.sub(r'\s+', '', iban).upper() for iban in ibans],[bic.upper() for bic in bics]


def parse_french_rib(iban):
    """Extrait les composants RIB d'un IBAN français"""
    if len(iban) != 27 or not iban.startswith('FR'):
        return None

    bban = iban[4:]  # Supprime 'FR' et les 2 chiffres de contrôle
    return {
        'code_banque': bban[0:5],
        'code_guichet': bban[5:10],
        'num_compte': bban[10:21],
        'cle_rib': bban[21:23]
    }

