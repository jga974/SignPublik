import requests
import json
from app.config import OMOGEN_SECRET_KEY
from app.core.logger import logger

SECRET_KEY = OMOGEN_SECRET_KEY


def envoi_pdf_ruda(pdf_stream, numen, libelle, nature="modalites_de_temps_de_travail/teletravail"):
    """
    Envoi sur RUDA du flux PDF
    :param pdf_stream: le flux du PDF
    :param numen: Numen unique de l'agent
    :param libelle: le texte de description du PDF qui apparait à l'agent
    :param nature: CF répertoire autorise (retrouver l'URL)
    :return: retour HTTP du WS
    """
    response = _envoyer_pdf_ruda(
        pdf_stream,
        numen,
        libelle_document=libelle,
        nature=nature,
        format_document="numerique",
        url="https://pr-api.omogen.in.phm.education.gouv.fr/mesirh/ged-ruda/documents/demandes"
    )
    return response

def envoi_pdf_ruda_arretes(pdf_stream, numen, libelle, nature="autre/n_autre"):
    """
    Envoi sur RUDA du flux PDF
    :param pdf_stream: le flux du PDF
    :param numen: Numen unique de l'agent
    :param libelle: le texte de description du PDF qui apparait à l'agent
    :param nature: CF répertoire autorise (retrouver l'URL)
    :return: retour HTTP du WS
    """
    response = _envoyer_pdf_ruda(
        pdf_stream,
        numen,
        libelle_document=libelle,
        nature=nature,
        format_document="numerique",
        url="https://pr-api.omogen.in.phm.education.gouv.fr/mesirh/ged-ruda/documents/arretes"
    )
    return response


def envoi_tt_pdf_ruda(flux, numen, libelle):
    """
       Envoi sur RUDA du flux PDF dans le classeur pour le télétravail
       :param pdf_stream: le flux du PDF
       :param numen: Numen unique de l'agent
       :param libelle: le texte de description du PDF qui apparait à l'agent
       :return: retour HTTP du WS
       """
    # resp = _envoyer_document(
    #    flux,
    #     numen,
    #     libelle_document= libelle,
    #     nature="modalites_de_temps_de_travail/teletravail",
    #     format_document="numerique"
    # )
    return envoi_pdf_ruda(flux, numen, libelle, "modalites_de_temps_de_travail/teletravail")


def envoi_pdf_ruda_AVIRER(flux, numen, nature, libelle):
    """
       Envoi sur RUDA d'un  PDF d
       :param pdf_stream: le flux du PDF
       :param numen: Numen unique de l'agent
       :param nature: sa nature (liste de valeurs a respecter)
       :param libelle: le texte de description du PDF qui apparait à l'agent
       :return: retour HTTP du WS
       """
    # resp = _envoyer_document(
    #    flux,
    #     numen,
    #     libelle_document= libelle,
    #     nature=nature",
    #     format_document="numerique"
    # )
    return envoi_pdf_ruda(flux, numen, libelle, nature)


def supp_doc_ruda(uid):
    headers = {
        "accept": "application/json",
        "X-Omogen-Api-Key": SECRET_KEY
    }

    url = f"https://pr-api.omogen.in.phm.education.gouv.fr/mesirh/ged-ruda/documents/{uid}/purge"
    response = requests.delete(url, headers=headers, timeout=30.0)
    logger.info("Statut suppression RUDA %s: %s", uid, response.status_code)
    return response


def  _envoyer_pdf_ruda(
        file_stream,

        numen,
        libelle_document,
        nature,
        format_document,
        origine="COLIBRIS",
        url="https://pr-api.omogen.in.phm.education.gouv.fr/mesirh/ged-ruda/documents/demandes"
    ):
    headers = {
        "accept": "application/json",
        "X-Omogen-Api-Key": SECRET_KEY
    }

    # Préparation du multipart/form-data
    files = {
        "fichier": file_stream,  # open(fichier_path, "rb"),
        # retourne : (
        #     None,                             # nom de fichier (None = pas de fichier joint)
        #     '{"origine": "COLIBRIS"}',       # contenu (sérialisé en JSON avec json.dumps)
        #     'application/json'               # type MIME (Content-Type)
        # )
        "si_source": (None, json.dumps({
            "origine": origine
        }), "application/json"),
        "metadonnees": (None, json.dumps({
            "numen": numen,
            "libelle_document": libelle_document,
            "nature": nature,
            "format": format_document
        }), "application/json")
    }

    try:
        response = requests.post(url, headers=headers, files=files, timeout=60.0)
        logger.info("Statut envoi RUDA numen %s: %s", numen, response.status_code)
        return response
    finally:
        files["fichier"].close()  # Toujours fermer le fichier ouvert
