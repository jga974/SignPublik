#!/usr/bin/env python3
"""Signe un PDF (ou DOCX) à l'emplacement d'une ancre, avec une griffe créée à partir d'un nom.

Utilise uniquement les API existantes du service :
  1. POST /getInfo-PDF       -> page et position du texte d'ancrage
  2. POST /sign-simple-name  -> signature électronique + griffe manuscrite générée depuis le nom

Exemple :
    python scripts/signer_pdf.py contrat.pdf --nom "Michel Dupont" --ancre "Assistant"

La clé API est lue dans --api-key ou la variable d'environnement API_KEY ; l'URL du service dans
--url ou SIGNPUBLIK_URL (par défaut http://localhost:8000).
"""
import argparse
import base64
import os
import sys
from pathlib import Path

import requests


class SignerError(Exception):
    """Erreur affichable telle quelle à l'utilisateur."""


def _detail(reponse) -> str:
    try:
        return str(reponse.json().get("detail", reponse.text))
    except Exception:
        return reponse.text[:300]


def _appeler(session, url: str, headers: dict, payload: dict):
    try:
        reponse = session.post(url, json=payload, headers=headers)
    except requests.RequestException as e:
        raise SignerError(f"service injoignable ({url}) : {e}") from e
    if reponse.status_code != 200:
        raise SignerError(f"{url} -> HTTP {reponse.status_code} : {_detail(reponse)}")
    return reponse


def boite_pres_de_l_ancre(info: dict, largeur: int, hauteur: int, marge: int) -> tuple:
    """Boîte de signature (x1, y1, x2, y2), origine en bas à gauche, juste sous l'ancre.

    /getInfo-PDF donne la position de l'ancre depuis le haut de la page. S'il n'y a pas assez de
    place sous l'ancre, la boîte est placée au-dessus ; elle est aussi décalée pour rester dans la page.
    """
    coords = info["signature_coords"]
    ancre_gauche = float(coords["x1"])
    ancre_haut = float(coords["y1"])      # distance entre le haut de la page et le haut du texte
    ancre_bas = float(coords["y2"])
    page_l = int(info["pagesize"]["width"])
    page_h = int(info["pagesize"]["height"])
    if largeur > page_l or hauteur > page_h:
        raise SignerError(f"la zone de signature ({largeur} x {hauteur}) est plus grande que la page "
                          f"({page_l} x {page_h})")

    x1 = int(min(max(ancre_gauche, 0), page_l - largeur))

    sous_y2 = int(page_h - ancre_bas - marge)          # bord haut de la boîte, sous l'ancre
    if sous_y2 - hauteur >= 0:
        y2 = sous_y2
    else:
        dessus_y1 = int(page_h - ancre_haut + marge)    # bord bas de la boîte, au-dessus de l'ancre
        if dessus_y1 + hauteur > page_h:
            raise SignerError("pas assez de place autour de l'ancre pour la signature "
                              "(réduisez --largeur/--hauteur/--marge)")
        y2 = dessus_y1 + hauteur
    return (x1, y2 - hauteur, x1 + largeur, y2)


def signer(session, url: str, api_key: str, contenu: bytes, nom_fichier: str, nom: str, ancre: str,
           mail: str | None = None, largeur: int = 180, hauteur: int = 135, marge: int = 20) -> bytes:
    """Signe `contenu` à l'ancre et renvoie le PDF signé.

    :param session: objet avec .post(url, json=, headers=) (requests.Session ou TestClient)
    :param url: adresse du service, sans « / » final
    """
    headers = {"api-key": api_key}
    fichier = {"filename": nom_fichier, "content": base64.b64encode(contenu).decode()}

    info = _appeler(session, f"{url}/getInfo-PDF", headers,
                    {"fichier": fichier, "recherche": ancre}).json()
    page = info["signature_page"]
    if page == -1:
        raise SignerError(f"ancre « {ancre} » introuvable dans {nom_fichier}")

    boite = boite_pres_de_l_ancre(info, largeur, hauteur, marge)
    print(f"ancre « {ancre} » trouvée page {page}, signature en {boite}", file=sys.stderr)

    payload = {"page": page, "signername": nom, "signature_box": ", ".join(map(str, boite)),
               "filedef1": fichier}
    if mail:
        payload["signermail"] = mail
    return _appeler(session, f"{url}/sign-simple-name", headers, payload).content


def lire_arguments(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("fichier", type=Path, help="PDF (ou DOCX) à signer")
    p.add_argument("--nom", required=True, help="nom du signataire, affiché dans la griffe")
    p.add_argument("--ancre", required=True, help="texte du document sous lequel signer")
    p.add_argument("--sortie", type=Path, help="fichier de sortie (défaut : signed_<fichier>.pdf)")
    p.add_argument("--mail", help="mail du signataire : utilise son certificat s'il existe sur le serveur")
    p.add_argument("--url", default=os.getenv("SIGNPUBLIK_URL", "http://localhost:8000"),
                   help="adresse du service (défaut : $SIGNPUBLIK_URL ou http://localhost:8000)")
    p.add_argument("--api-key", default=os.getenv("API_KEY"), help="clé API (défaut : $API_KEY)")
    p.add_argument("--largeur", type=int, default=180, help="largeur de la zone de signature, en points")
    p.add_argument("--hauteur", type=int, default=135, help="hauteur de la zone de signature, en points")
    p.add_argument("--marge", type=int, default=20, help="espace entre l'ancre et la signature, en points")
    return p.parse_args(argv)


def main(argv=None, session=None) -> int:
    args = lire_arguments(argv)
    try:
        if not args.api_key:
            raise SignerError("clé API manquante : utilisez --api-key ou la variable API_KEY")
        if not args.fichier.is_file():
            raise SignerError(f"fichier introuvable : {args.fichier}")
        sortie = args.sortie or args.fichier.with_name(f"signed_{args.fichier.stem}.pdf")
        pdf_signe = signer(session or requests.Session(), args.url.rstrip("/"), args.api_key,
                           args.fichier.read_bytes(), args.fichier.name, args.nom, args.ancre,
                           mail=args.mail, largeur=args.largeur, hauteur=args.hauteur, marge=args.marge)
        sortie.write_bytes(pdf_signe)
    except SignerError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1
    print(f"PDF signé : {sortie.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
