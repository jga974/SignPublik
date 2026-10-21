"""Fixtures de test : tout est généré à la volée, aucun fichier réel n'est requis."""
import base64
import datetime
from pathlib import Path

import pymupdf
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from app.config import API_KEY

# Texte servant d'ancrage à la griffe (champ "recherche" de /getInfo-PDF)
ANCHOR = "Assistant"
ANCHOR_PAGE = 2  # numéro de page (base 1) où l'ancre est posée
PAGE_W, PAGE_H = 595, 842


def make_pdf(pages: int = 2, anchor: str = ANCHOR, anchor_page: int = ANCHOR_PAGE) -> bytes:
    """PDF A4 de `pages` pages, avec le texte d'ancrage sur `anchor_page`."""
    doc = pymupdf.open()
    for n in range(1, pages + 1):
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        page.insert_text((72, 72), f"Document de test - page {n}", fontsize=14)
        if n == anchor_page:
            page.insert_text((72, 700), anchor, fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def make_cert(common_name: str = "Test Signataire"):
    """Certificat auto-signé + clé privée, au format PEM."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def make_griffe_png(path) -> None:
    """Griffe de substitution : un aplat noir opaque, facile à détecter au rendu."""
    from PIL import Image
    Image.new("RGBA", (226, 170), (0, 0, 0, 255)).save(path)


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


@pytest.fixture
def sign_env(tmp_path, monkeypatch):
    """Isole la signature : répertoire de signatures, certificat et horodatage factices.

    - `cert.pem` / `private_key.pem` sont cherchés dans le répertoire courant ;
    - SIGN_PATH est lu au chargement des modules, on le redirige vers tmp_path ;
    - l'horodatage freetsa.org (réseau) est désactivé.
    """
    import app.hello_test as api
    import app.core.signature as sig

    cert_pem, key_pem = make_cert()
    (tmp_path / "cert.pem").write_bytes(cert_pem)
    (tmp_path / "private_key.pem").write_bytes(key_pem)
    make_griffe_png(tmp_path / "signature_signe_noBG.png")

    # Le code charge polices et certificats par chemin relatif ("app/core/fonts/...",
    # "cert.pem") : on travaille dans tmp_path en y exposant le dossier app/.
    (tmp_path / "app").symlink_to(Path(api.__file__).parent, target_is_directory=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(api, "SIGN_PATH", str(tmp_path))
    monkeypatch.setattr(sig, "SIGN_PATH", str(tmp_path))

    real_sign = sig.pdf.cms.sign

    def sign_sans_tsa(data, udct, *args, **kwargs):
        udct = {k: v for k, v in udct.items() if not k.startswith("timestamp")}
        return real_sign(data, udct, *args, **kwargs)

    monkeypatch.setattr(sig.pdf.cms, "sign", sign_sans_tsa)
    return tmp_path


@pytest.fixture
def client():
    from app.hello_test import app
    return TestClient(app)


@pytest.fixture
def headers():
    return {"api-key": API_KEY}
