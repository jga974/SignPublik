
from app.core.logger import logger
from app.core.utilities import generate_unique_filename
from app.core.constants import *

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from endesive import pdf

# A VIRER apres refactoring du code
from fastapi import HTTPException

import os, sys, io
import datetime

def certificate_exists(mail : str) -> bool :
    logger.debug(f"on  cherche certif pour {mail}")
    # on cherche la cert file
    path = get_cert_name(mail)
    logger.debug(f"on  cherche {path}")
    if os.path.exists(path) is True:
        # et la clef
        path_key= get_key_name(mail)
        logger.info(f"on a trouve {path}, on cherche {path_key}")
        return os.path.exists(path_key)
    return False


def get_cert_name(mail : str) -> str:
    return os.path.join(SIGN_PATH, f"{mail.lower()}.pem")

def get_key_name(mail : str) -> str:
    return os.path.join(SIGN_PATH, f"{mail.lower()}_key.pem")


def sign_pdf_content(pdf_content, signature_box, page,
                     file_signature_img: str = None,
                     mail_signer : str="NOTFOUND"):
    try:
        if file_signature_img is None:
            file_signature_img = os.path.join(SIGN_PATH, "signature_signe_noBG.png")
        elif not os.path.isabs(file_signature_img) and not os.path.dirname(file_signature_img):
            file_signature_img = os.path.join(SIGN_PATH, file_signature_img)

        # Charger le certificat PEM (stocké dans un emplacement sécurisé)
        if certificate_exists(mail_signer) :
            cert_file = get_cert_name(mail_signer)
            key_file = get_key_name(mail_signer)
        else :
            cert_file = DEFAULT_CERT_FILE
            key_file = DEFAULT_KEY_FILE

        logo_path = "logo.png",
        logger.info(f"On demande {signature_box} et page {page} et taille {len(pdf_content)} et image {file_signature_img}")
        logger.info(f"Fichier sig  {file_signature_img} existe ? {os.path.isfile(file_signature_img)}")
        try:
            with open(cert_file, "rb") as f:
                cert_data = f.read()
        except FileNotFoundError:
            logger.error(f"Le fichier {cert_file} n'existe pas.")
            raise
        cert = x509.load_pem_x509_certificate(cert_data, default_backend())

        try:
            with open(key_file, "rb") as f:
                key = load_pem_private_key(f.read(), password=None, backend=default_backend())
        except FileNotFoundError:
            logger.error(f"Le fichier {key_file} n'existe pas.")
            raise

        othercerts = []  # Certificats intermédiaires si nécessaire

        # Signer le PDF
        metadata = {
            "aligned": 0,
            "sigflags": 3,
            "sigflagsft": 132,
            "sigpage": page,  # Page 0 = première page
            "sigbutton": True,
            "contact": "sg-rec@ac-corse.fr",
            "location": "Ajaccio, FR",
            "signingdate": datetime.datetime.utcnow().strftime("D:%Y%m%d%H%M%S+00'00'"),
            "reason": "Approval numérique",
            "signatureCCC": "signé électroniquement par Colibris Corse",
            "sigandcertify": True,
            "signature_img_centred" : False,
            "signature_img_distort": False,
            # "signaturebox": (100, 80, 250, 150),  # Position (gauche, bas, droite, haut),
            #"signaturebox": (350, 120, 550, 220),  # Position (gauche, bas, droite, haut),
            "signaturebox": signature_box,
            #"signature_img": "signature_signe_noBG.png",  # Logo optionnel
            #"signature_img_distort": False,
            'signature_appearance': {
                'icon':  file_signature_img,
                #'background': [0.75, 0.8, 0.95],
                #'outline': [0.2, 0.3, 0.5],
                'border': 0,
                'labels': True,
                #'display': ['date'],
                #'display': 'date,contact,reason'.split(',')
            },
            "timestamp_url": "http://freetsa.org/tsr",
            "timestampurl": "http://freetsa.org/tsr",
            "timestamp_alg": "sha256",
            "timestamp_retries": 3
        }
        logger.info("on va signer .")
        signed_pdf = pdf.cms.sign(
            pdf_content,
            metadata,
            key,
            cert,
            othercerts,
            "sha256"
        )
        logger.info("on a signe.")
        output_pdf = generate_unique_filename()
        logger.info(f"on va utiliser le nom {output_pdf}.")
        with open(output_pdf, "wb") as f:
            f.write(pdf_content)
            f.write(signed_pdf)
        logger.debug("on a ecrit le resultat")

        # Lire le contenu du fichier en streaming
        with open(output_pdf, "rb") as f:
            # key_data = f.read()
            file_like = io.BytesIO(f.read())
        logger.info(f"on a relu le fichier temporaire, on supprime {output_pdf}")
        os.remove(output_pdf)

        return file_like

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        logger.error(f"{exc_type.__name__} dans {fname} ligne {exc_tb.tb_lineno}")
        logger.error(f"Erreur lors de la signature du pdf_content .. : {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la signature: {str(e)}")
