#!/usr/bin/env python3
"""Script autonome d'enchaînement :
1. Recherche de l'ancre textuelle dans le PDF (/getInfo-PDF)
2. Calcul de la boîte sous l'ancre
3. Signature électronique avec griffe manuscrite générée à partir du texte (/sign-simple-name)
"""

import argparse
import base64
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Ajouter la racine du projet au PYTHONPATH si nécessaire
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from app.config import API_KEY
from app.hello_test import app
import app.core.signature as sig
import app.core.ImageUtils as imgutils
import app.hello_test as api

FIXTURES = ROOT_DIR / "tests" / "fixtures"


def configurer_environnement():
    """Initialise le certificat et désactive l'appel TSA réseau pour un test local rapide."""
    dossier_sign = ROOT_DIR / "signature_files"
    dossier_sign.mkdir(parents=True, exist_ok=True)

    # Griffe par défaut si présente
    griffe_src = FIXTURES / "signature_signe_noBG.png"
    if griffe_src.exists():
        shutil.copy(griffe_src, dossier_sign)

    api.SIGN_PATH = str(dossier_sign)
    sig.SIGN_PATH = str(dossier_sign)
    imgutils.SIGN_PATH = str(dossier_sign)

    # Certificats par défaut
    if (FIXTURES / "cert.pem").exists():
        sig.DEFAULT_CERT_FILE = str(FIXTURES / "cert.pem")
    if (FIXTURES / "private_key.pem").exists():
        sig.DEFAULT_KEY_FILE = str(FIXTURES / "private_key.pem")

    # Désactiver l'horodatage freetsa.org pour exécution locale hors-ligne
    real_sign = sig.pdf.cms.sign
    def sign_sans_tsa(data, udct, *args, **kwargs):
        udct = {k: v for k, v in udct.items() if not k.startswith("timestamp")}
        return real_sign(data, udct, *args, **kwargs)
    sig.pdf.cms.sign = sign_sans_tsa


def executer_chaine(
    chemin_pdf: Path,
    ancre: str = "Assistant",
    nom_signataire: str = "Jean-Guy Avelin",
    email_signataire: str = "jean-guy.avelin@ac-corse.fr",
    chemin_sortie: Path = None,
    largeur_griffe: int = 150,
    hauteur_griffe: int = 85,
    marge: int = 15
):
    print("=" * 70)
    print("  ENCHAÎNEMENT : ANCRE TEXTE -> GRIFFE MANUSCRITE & SIGNATURE")
    print("=" * 70)
    print(f"📄 Fichier source     : {chemin_pdf}")
    print(f"🔍 Mot-clé d'ancrage  : « {ancre} »")
    print(f"✍️  Nom du signataire  : {nom_signataire}")
    print(f"📧 Email du signataire: {email_signataire}")
    print("-" * 70)

    if not chemin_pdf.exists():
        raise FileNotFoundError(f"Le fichier PDF n'existe pas : {chemin_pdf}")

    client = TestClient(app)
    headers = {"api-key": API_KEY}

    # Lecture et encodage du document PDF
    pdf_bytes = chemin_pdf.read_bytes()
    b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
    fichier_payload = {
        "filename": chemin_pdf.name,
        "content": b64_pdf
    }

    # -------------------------------------------------------------
    # 1er appel : /getInfo-PDF (Recherche de l'ancre et coordonnées)
    # -------------------------------------------------------------
    print("\n[Étape 1/2] Appel à /getInfo-PDF pour situer l'ancre...")
    req_info = {
        "fichier": fichier_payload,
        "recherche": ancre
    }
    res_info = client.post("/getInfo-PDF", json=req_info, headers=headers)
    if res_info.status_code != 200:
        raise RuntimeError(f"Erreur /getInfo-PDF ({res_info.status_code}): {res_info.text}")

    info = res_info.json()
    page_ancre = info.get("signature_page", -1)
    if page_ancre <= 0:
        raise ValueError(f"L'ancre « {ancre} » n'a pas été trouvée dans le document.")

    x1 = float(info["signature_coords"]["x1"])
    y1 = float(info["signature_coords"]["y1"])
    hauteur_page = int(info["pagesize"]["height"])

    # Calcul de la boîte de signature juste SOUS l'ancre
    # Attention au repère : y1 de PyMuPDF est compté depuis le haut,
    # alors que le repère PDF pour la signature compte depuis le bas.
    box = (
        int(x1),
        int(hauteur_page - y1 - hauteur_griffe - marge),
        int(x1 + largeur_griffe),
        int(hauteur_page - y1 - marge)
    )
    box_str = f"{box[0]}, {box[1]}, {box[2]}, {box[3]}"

    print(f"   ✔ Ancre localisée à la page {page_ancre} (x={x1:.1f}, y={y1:.1f})")
    print(f"   ✔ Boîte calculée sous l'ancre : {box_str}")

    # -------------------------------------------------------------
    # 2eme appel : /sign-simple-name (Griffe générée + signature X.509)
    # -------------------------------------------------------------
    print("\n[Étape 2/2] Appel à /sign-simple-name (génération griffe + signature)...")
    req_sign = {
        "page": page_ancre,
        "signername": nom_signataire,
        "signermail": email_signataire,
        "signature_box": box_str,
        "filedef1": fichier_payload
    }

    res_sign = client.post("/sign-simple-name", json=req_sign, headers=headers)
    if res_sign.status_code != 200:
        raise RuntimeError(f"Erreur /sign-simple-name ({res_sign.status_code}): {res_sign.text}")

    signed_bytes = res_sign.content
    print(f"   ✔ Document signé avec succès ({len(signed_bytes)} octets)")

    # Enregistrement du fichier signé
    if chemin_sortie is None:
        chemin_sortie = ROOT_DIR / "pdf_signes" / f"signe_{chemin_pdf.name}"

    chemin_sortie.parent.mkdir(parents=True, exist_ok=True)
    chemin_sortie.write_bytes(signed_bytes)

    print("-" * 70)
    print(f"🎉 SUCCÈS : PDF signé sauvegardé dans :\n   -> {chemin_sortie.resolve()}")
    print("=" * 70)
    return chemin_sortie


def main():
    parser = argparse.ArgumentParser(description="Signature d'un PDF sous ancre avec griffe générée à partir du texte")
    parser.add_argument(
        "--pdf",
        type=Path,
        default=FIXTURES / "fichier_demande-testeur-avelin.pdf",
        help="Chemin du fichier PDF à signer (défaut: fixture fichier_demande-testeur-avelin.pdf)"
    )
    parser.add_argument(
        "--ancre",
        type=str,
        default="Assistant",
        help="Texte de l'ancre à rechercher dans le PDF (défaut: 'Assistant')"
    )
    parser.add_argument(
        "--nom",
        type=str,
        default="Jean-Guy Avelin",
        help="Nom à faire apparaître sur la griffe manuscrite (défaut: 'Jean-Guy Avelin')"
    )
    parser.add_argument(
        "--email",
        type=str,
        default="jean-guy.avelin@ac-corse.fr",
        help="Email du signataire (défaut: 'jean-guy.avelin@ac-corse.fr')"
    )
    parser.add_argument(
        "--sortie",
        type=Path,
        default=ROOT_DIR / "pdf_signes" / "demande_avelin_signee.pdf",
        help="Chemin de sortie du PDF signé"
    )
    parser.add_argument(
        "--largeur",
        type=int,
        default=150,
        help="Largeur de la boîte de signature en points (défaut: 150, env. 5.3 cm)"
    )
    parser.add_argument(
        "--hauteur",
        type=int,
        default=85,
        help="Hauteur de la boîte de signature en points (défaut: 85, env. 3.0 cm)"
    )
    parser.add_argument(
        "--marge",
        type=int,
        default=15,
        help="Marge sous l'ancre en points (défaut: 15)"
    )

    args = parser.parse_args()

    configurer_environnement()
    executer_chaine(
        chemin_pdf=args.pdf,
        ancre=args.ancre,
        nom_signataire=args.nom,
        email_signataire=args.email,
        chemin_sortie=args.sortie,
        largeur_griffe=args.largeur,
        hauteur_griffe=args.hauteur,
        marge=args.marge
    )


if __name__ == "__main__":
    main()
