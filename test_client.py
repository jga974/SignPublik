# a lancer avec pytest

import pytest

from fastapi.testclient import TestClient

import base64
from pathlib import Path

import shutil

from app.config import API_KEY as TEST_API_KEY
from app.hello_test import app
from tests.conftest import sans_horodatage

client = TestClient(app)

# Fichiers d'exemple versionnés (indépendant du répertoire de lancement)
FIXTURES = Path(__file__).parent / "tests" / "fixtures"


@pytest.fixture(autouse=True)
def signature_de_test(tmp_path, monkeypatch):
    """Signe avec le certificat et la griffe de tests/fixtures, sans réseau."""
    import app.hello_test as api
    import app.core.signature as sig
    shutil.copy(FIXTURES / "signature_signe_noBG.png", tmp_path)
    monkeypatch.setattr(api, "SIGN_PATH", str(tmp_path))
    monkeypatch.setattr(sig, "SIGN_PATH", str(tmp_path))
    monkeypatch.setattr(sig, "DEFAULT_CERT_FILE", str(FIXTURES / "cert.pem"))
    monkeypatch.setattr(sig, "DEFAULT_KEY_FILE", str(FIXTURES / "private_key.pem"))
    sans_horodatage(monkeypatch)


def test_PDFInfo():
    headers = {"api-key": TEST_API_KEY}

    with open(FIXTURES / "fichier_demande-testeur-avelin.pdf", "rb") as pdf_file:
        pdf_data = pdf_file.read()

    # Encoder le contenu en base64
    base64_encoded = base64.b64encode(pdf_data).decode("utf-8")
    data = {
        "fichier": {
            "filename": "fichier_demande-testeur-avelin.pdf",
            "content": base64_encoded
        },
        "recherche": "Assistant"
    }

    response = client.post("/getInfo-PDF/", json=data,  headers=headers)
    print("LLLLLLLL")
    print(response.json())
    print("End PDF info")
    assert response.status_code == 200
    assert response.json()['nombre_de_pages'] == 2;

@pytest.mark.skipif( 1 == 1 , reason="trop lourd a tester")
def test_DOCXInfo():
    headers = {"api-key": TEST_API_KEY}

    with open("Exemple_a_signer.docx", "rb") as docx_file:
        docx_data = docx_file.read()

    # Encoder le contenu en base64
    base64_encoded = base64.b64encode(docx_data).decode("utf-8")
    data = {
        "fichier": {
            "filename": "Exemple_a_signer.docx",
            "content": base64_encoded
        },
        "recherche": "Le Signataire"
    }

    response = client.post("/getInfo-PDF/", json=data, headers=headers)

    print(response.json())

    assert response.status_code == 200
    assert response.json()['nombre_de_pages'] == 1;
    assert int(float(response.json()['signature_coords']['x1'])) == 70;


def test_PDFSign(save_signed):
    headers = {"api-key": TEST_API_KEY}

    with open(FIXTURES / "fichier_demande-testeur-avelin.pdf", "rb") as pdf_file:
        pdf_data = pdf_file.read()
    print(f"taille du fichier : {len(pdf_data)}")
    # Encoder le contenu en base64
    base64_encoded = base64.b64encode(pdf_data).decode("utf-8")
    fichier = {
        "filename": "fichier_demande-testeur-avelin.pdf",
        "content": base64_encoded
    }

    # 1. on cherche l'ancre : page et position du texte « Assistant »
    info = client.post("/getInfo-PDF", headers=headers,
                       json={"fichier": fichier, "recherche": "Assistant"})
    assert info.status_code == 200
    info = info.json()
    assert info["signature_page"] == 2
    x1 = float(info["signature_coords"]["x1"])
    y1 = float(info["signature_coords"]["y1"])      # repère haut-gauche
    hauteur_page = int(info["pagesize"]["height"])

    # 2. la boîte de signature est en repère PDF (origine en bas à gauche) :
    #    200 x 100 points, 20 points sous l'ancre
    box = (int(x1), int(hauteur_page - y1 - 120), int(x1) + 200, int(hauteur_page - y1 - 20))
    print(f"ancre en ({x1:.0f}, {y1:.0f}) page {info['signature_page']}, boîte de signature {box}")

    # 3. on signe à cet endroit
    payload = {
        "page": info["signature_page"],
        "ocrlayer": False,
        "protect": False,
        "signature_box": ", ".join(map(str, box)),
        "filedef1": fichier
    }

    response = client.post(url = "/sign-basePDF64/", json=payload,  headers=headers)
    #print(response.json())
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/pdf'
    assert response.content.startswith(pdf_data), "le PDF d'origine doit être conservé"
    # pytest test_client.py::test_PDFSign -s --save-signed ./pdf_signes
    save_signed("signed_fichier_demande-testeur-avelin.pdf", response.content)

# Le signataire
@pytest.mark.skipif( 1 == 1 , reason="trop lourd a tester l  signature")
def test_DocSign():
    headers = {"api-key": TEST_API_KEY}

    with open("Exemple_a_signer.docx", "rb") as pdf_file:
        pdf_data = pdf_file.read()
    print(f"taille du fichier : {len(pdf_data)}")
    # Encoder le contenu en base64
    base64_encoded = base64.b64encode(pdf_data).decode("utf-8")
    payload = {
        "page": 1,
        "ocrlayer": False,
        "protect": False,
        "signature_box" : "351, 121, 551, 221",
        "filedef1": {
            "filename": "Exemple_a_signer.docx",
            "content": base64_encoded
        }
    }

    response = client.post(url = "/sign-basePDF64/", json=payload,  headers=headers)
    #print(response.json())
    assert response.status_code == 200
    print( response.headers['content-type'] == 'application/pdf');

def test_IMGInfo():
    headers = {"api-key": TEST_API_KEY}

    # Lire le fichier PNG en mode binaire
    with open(FIXTURES / "signature_signe_noBG.png", "rb") as png_file:
            png_data = png_file.read()

    # Encoder les données en base64
    base64_encoded = base64.b64encode(png_data).decode("utf-8")
    print("on est dans test img")
    data = {
        "image": {
            "filename": "signature_signe_noBG.png",
            "content": base64_encoded
        },
        "recherche": "Assistant"
    }
    response = client.post("/image-size/", json=data, headers=headers)
    print(response.json())
    assert response.status_code == 200
    assert response.json()['width'] == 113;
    assert response.json()['height'] == 85;


def test_RIBlecture():
    headers = {"api-key": TEST_API_KEY}

    # Lire le fichier PNG en mode binaire
    with open(FIXTURES / "rib.pdf", "rb") as pdf_file:
            pdf_data = pdf_file.read()

    # Encoder les données en base64
    base64_encoded = base64.b64encode(pdf_data).decode("utf-8")
    print("on est dans lecture du RIB")
    data = {
        "fichier": {
            "filename": "rib.pdf",
            "content": base64_encoded
        }
    }
    response = client.post("/read-rib/", json=data, headers=headers)
    print(response.json())
    assert response.status_code == 200
    assert response.json()['iban'] == 'FR7630003004170005607498316';
    assert response.json()['rib']['code_banque'] == '30003';

