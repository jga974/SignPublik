"""Endpoints annexes : /image-size/, /hello, /upload-and-download-pdf/ et griffe manuscrite."""
import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from tests.conftest import b64, make_pdf
from tests.test_utilities import png_b64


# ---------- /image-size/ ----------

def test_image_size(client):
    r = client.post("/image-size/", json={"image": {"filename": "g.png", "content": png_b64((113, 85))}})
    assert r.status_code == 200
    assert r.json() == {"width": 113, "height": 85, "save": False}


def test_image_size_avec_stockage(client, tmp_path, monkeypatch):
    import app.core.constants as constants
    monkeypatch.setattr(constants, "SIGN_PATH", str(tmp_path))
    r = client.post("/image-size/", json={
        "image": {"filename": "g.png", "content": png_b64()}, "store": True})
    assert r.status_code == 200
    assert r.json()["save"] == "g.png"
    assert (tmp_path / "g.png").exists()


def test_image_size_image_invalide(client):
    r = client.post("/image-size/", json={"image": {"filename": "g.png", "content": b64(b"non")}})
    assert r.status_code == 400


def test_image_size_corps_incomplet(client):
    assert client.post("/image-size/", json={}).status_code == 422


# ---------- hello ----------

def test_hello(client):
    r = client.get("/hello/monde")
    assert r.status_code == 200
    assert r.json() == {"message": "Hello, monde!"}


def test_hello_securise(client):
    from app.config import SHARED_SECRET
    assert client.get("/helloSP/x", headers={"x-api-key": SHARED_SECRET}).status_code == 200
    assert client.get("/helloSP/x", headers={"x-api-key": "faux"}).status_code == 403
    assert client.get("/helloSP/x").status_code == 422


# ---------- /upload-and-download-pdf/ ----------

def test_upload_and_download_renvoie_le_pdf(client):
    pdf = make_pdf()
    r = client.post("/upload-and-download-pdf/", files={"file": ("d.pdf", pdf, "application/pdf")})
    assert r.status_code == 200
    assert r.content == pdf
    assert r.headers["content-type"] == "application/pdf"


def test_upload_and_download_refuse_non_pdf(client):
    r = client.post("/upload-and-download-pdf/", files={"file": ("d.txt", b"abc", "text/plain")})
    assert r.status_code == 400


@pytest.mark.xfail(strict=True, reason="/upload-pdf/ appelle sign_pdf(), fonction qui n'existe plus : NameError")
def test_upload_pdf_signe(headers):
    from app.hello_test import app
    c = TestClient(app, raise_server_exceptions=False)
    r = c.post("/upload-pdf/", headers=headers, files={"file": ("d.pdf", make_pdf(), "application/pdf")})
    assert r.status_code == 200


def test_upload_pdf_refuse_non_pdf(client, headers):
    r = client.post("/upload-pdf/", headers=headers, files={"file": ("d.txt", b"abc", "text/plain")})
    assert r.status_code == 400


# ---------- griffe manuscrite ----------

def test_griffe_manuscrite(tmp_path):
    from app.core.ImageUtils import creer_image_texte_manuscrit_avance
    chemin = tmp_path / "griffe.png"
    res = creer_image_texte_manuscrit_avance("Jean Dupont", (226, 170), nom_fichier=str(chemin),
                                             horodatage="le 01/01/2026 à 10h00:00")
    assert res == str(chemin)
    img = Image.open(chemin)
    assert img.size == (226, 170)
    assert img.mode == "RGBA"
    alpha = img.getchannel("A")
    assert alpha.getextrema()[1] > 0, "du texte doit être dessiné"
    assert alpha.getpixel((0, 0)) == 0, "fond transparent"


def test_griffe_manuscrite_ecrase_le_fichier_existant(tmp_path):
    from app.core.ImageUtils import creer_image_texte_manuscrit_avance
    chemin = tmp_path / "g.png"
    creer_image_texte_manuscrit_avance("A", (100, 80), nom_fichier=str(chemin))
    creer_image_texte_manuscrit_avance("B", (120, 90), nom_fichier=str(chemin))
    assert Image.open(chemin).size == (120, 90)


def test_griffe_manuscrite_horodatage_ajoute_de_l_encre(tmp_path):
    from app.core.ImageUtils import creer_image_texte_manuscrit_avance
    sans = creer_image_texte_manuscrit_avance("Jean", (226, 170), nom_fichier=str(tmp_path / "a.png"))
    avec = creer_image_texte_manuscrit_avance("Jean", (226, 170), nom_fichier=str(tmp_path / "b.png"),
                                              horodatage="le 01/01/2026")
    def encre(p):
        return sum(1 for v in Image.open(p).getchannel("A").getdata() if v > 0)
    assert encre(avec) > encre(sans)


def test_griffe_manuscrite_nom_relatif_place_dans_sign_path(tmp_path, monkeypatch):
    import app.core.ImageUtils as iu
    monkeypatch.setattr(iu, "SIGN_PATH", str(tmp_path))
    res = iu.creer_image_texte_manuscrit_avance("Jean", (100, 80), nom_fichier="rel.png")
    assert res == str(tmp_path / "rel.png")
    assert (tmp_path / "rel.png").exists()


# ---------- /read-rib ----------

def rib_pdf(*lignes: str) -> bytes:
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    for i, ligne in enumerate(lignes):
        page.insert_text((72, 100 + 20 * i), ligne, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def lire_rib(client, headers, pdf: bytes):
    return client.post("/read-rib", headers=headers,
                       json={"fichier": {"filename": "rib.pdf", "content": b64(pdf)}})


def test_rib_complet(client, headers):
    r = lire_rib(client, headers, rib_pdf("IBAN FR76 3000 3004 1700 0560 7498 316", "BIC SOGEFRPP"))
    assert r.status_code == 200
    assert r.json() == {
        "iban": "FR7630003004170005607498316",
        "bic": "SOGEFRPP",
        "rib": {"code_banque": "30003", "code_guichet": "00417",
                "num_compte": "00056074983", "cle_rib": "16"},
    }


def test_rib_sans_bic(client, headers):
    """Un RIB sans BIC ne doit pas faire planter la route : bic vaut null."""
    r = lire_rib(client, headers, rib_pdf("IBAN FR76 3000 3004 1700 0560 7498 316"))
    assert r.status_code == 200
    assert r.json()["iban"] == "FR7630003004170005607498316"
    assert r.json()["bic"] is None


def test_rib_sans_iban(client, headers):
    r = lire_rib(client, headers, rib_pdf("Pas de coordonnées bancaires ici"))
    assert r.status_code == 200
    assert r.json() is None


def test_rib_sans_cle_api(client):
    r = client.post("/read-rib", json={"fichier": {"filename": "r.pdf", "content": ""}})
    assert r.status_code == 422
