"""Fonctions d'aide pour inspecter un PDF signé."""
import hashlib
import io

import pymupdf
import pypdf
from asn1crypto import cms
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from tests.conftest import ANCHOR, PAGE_H, b64


def locate_anchor(client, headers, pdf: bytes, recherche: str = ANCHOR, filename: str = "doc.pdf"):
    """Appelle /getInfo-PDF et renvoie la réponse JSON."""
    r = client.post("/getInfo-PDF", headers=headers, json={
        "fichier": {"filename": filename, "content": b64(pdf)},
        "recherche": recherche,
    })
    assert r.status_code == 200, r.text
    return r.json()


def box_under_anchor(info: dict, largeur: int = 200, hauteur: int = 100, marge: int = 20):
    """Boîte de signature (repère PDF, origine en bas à gauche) juste sous l'ancre trouvée."""
    x1, y1 = float(info["signature_coords"]["x1"]), float(info["signature_coords"]["y1"])
    return (int(x1), int(PAGE_H - y1 - hauteur - marge), int(x1) + largeur, int(PAGE_H - y1 - marge))


def to_rect(box, page_h: int = PAGE_H) -> pymupdf.Rect:
    """Boîte PDF (bas-gauche) -> rectangle de rendu pymupdf (haut-gauche)."""
    return pymupdf.Rect(box[0], page_h - box[3], box[2], page_h - box[1])


def signature_fields(pdf: bytes):
    """Signatures du PDF : liste de (nom, dictionnaire /V), dans l'ordre des pages.

    On parcourt les annotations plutôt que get_fields(), qui fusionne les champs de même nom.
    """
    reader = pypdf.PdfReader(io.BytesIO(pdf))
    res = []
    for page in reader.pages:
        for a in page.get("/Annots") or []:
            a = a.get_object()
            if a.get("/FT") == "/Sig" and "/V" in a:
                res.append((a.get("/T"), a["/V"].get_object()))
    return res


def sig_widgets(pdf: bytes, page_index: int):
    reader = pypdf.PdfReader(io.BytesIO(pdf))
    annots = reader.pages[page_index].get("/Annots") or []
    return [a.get_object() for a in annots if a.get_object().get("/FT") == "/Sig"]


def render(data: bytes, page_index: int, clip: pymupdf.Rect | None = None):
    doc = pymupdf.open(stream=data, filetype="pdf")
    pix = doc[page_index].get_pixmap(clip=clip, dpi=72)
    return pix.samples, pix.n


def pixels_changed(before: bytes, after: bytes, page_index: int, rect: pymupdf.Rect) -> float:
    """Part de pixels qui diffèrent dans `rect` entre les deux rendus de la page."""
    a, n = render(before, page_index, rect)
    b, _ = render(after, page_index, rect)
    diff = sum(1 for i in range(0, len(a), n) if a[i:i + n] != b[i:i + n])
    return diff / (len(a) // n)


def page_identique(before: bytes, after: bytes, page_index: int) -> bool:
    return render(before, page_index) == render(after, page_index)


def cms_of(pdf: bytes, index: int = 0):
    """Renvoie (ContentInfo CMS, octets signés par la ByteRange) de la signature n° `index`."""
    value = signature_fields(pdf)[index][1]
    br = [int(v) for v in value["/ByteRange"]]
    contents = bytes(value["/Contents"])
    signed = pdf[br[0]:br[0] + br[1]] + pdf[br[2]:br[2] + br[3]]
    return cms.ContentInfo.load(contents), signed


def verify_cms(pdf: bytes, index: int = 0) -> x509.Certificate:
    """Vérifie réellement la signature CMS (empreinte du document + signature RSA).

    Renvoie le certificat du signataire. Lève AssertionError si la signature est invalide.
    """
    content_info, signed = cms_of(pdf, index)
    signed_data = content_info["content"]
    signer_info = signed_data["signer_infos"][0]
    cert = x509.load_der_x509_certificate(signed_data["certificates"][0].chosen.dump())

    attrs = {a["type"].native: a["values"][0].native for a in signer_info["signed_attrs"]}
    assert attrs["message_digest"] == hashlib.sha256(signed).digest(), "empreinte du PDF différente"

    # La signature porte sur les attributs signés, ré-encodés avec le tag SET (0x31)
    to_verify = b"\x31" + signer_info["signed_attrs"].dump()[1:]
    cert.public_key().verify(signer_info["signature"].native, to_verify,
                             padding.PKCS1v15(), hashes.SHA256())
    return cert
