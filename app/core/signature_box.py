"""Lecture et validation de l'emplacement de la signature (page + boîte)."""
import io
import re

from pypdf import PdfReader


class SignatureBoxError(ValueError):
    """Boîte ou page de signature invalide (message destiné au client de l'API)."""


def parse_signature_box(texte: str) -> tuple:
    """« gauche, bas, droite, haut » -> (x1, y1, x2, y2) en entiers, origine en bas à gauche.

    Les décimales sont acceptées (arrondies) : /getInfo-PDF renvoie des coordonnées décimales.
    """
    morceaux = [m.strip() for m in str(texte).split(",")]
    if len(morceaux) != 4 or not all(re.fullmatch(r"-?\d+(\.\d+)?", m) for m in morceaux):
        raise SignatureBoxError(
            f"signature_box invalide : « {texte} » (attendu : quatre nombres « gauche, bas, droite, haut »)")
    return tuple(int(round(float(m))) for m in morceaux)


def resolve_signature_location(pdf_content: bytes, signature_box: str, page: int):
    """Valide la boîte et la page demandées pour ce PDF.

    :param page: numéro de page, base 1. Une valeur < 1 désigne la première page.
    :return: (boîte (x1, y1, x2, y2), index de page base 0)
    :raises SignatureBoxError: boîte illisible, inversée, hors de la page, ou page inexistante
    """
    box = parse_signature_box(signature_box)
    x1, y1, x2, y2 = box
    if x1 >= x2 or y1 >= y2:
        raise SignatureBoxError(
            f"signature_box {box} : il faut gauche < droite et bas < haut "
            f"(origine en bas à gauche de la page)")

    reader = PdfReader(io.BytesIO(pdf_content))
    nb_pages = len(reader.pages)
    index = max(int(page) - 1, 0)
    if index >= nb_pages:
        raise SignatureBoxError(f"page {page} inexistante : le document a {nb_pages} page(s)")

    media = reader.pages[index].mediabox
    gauche, bas = float(media.left), float(media.bottom)
    droite, haut = float(media.right), float(media.top)
    if x1 < gauche or y1 < bas or x2 > droite or y2 > haut:
        raise SignatureBoxError(
            f"signature_box {box} sort de la page {index + 1} "
            f"({round(droite - gauche)} x {round(haut - bas)} points, origine en bas à gauche)")
    return box, index
