"""Fichiers Word : conversion via LibreOffice puis recherche d'ancre / signature."""
import io
import shutil
import zipfile

import pytest

from tests.conftest import b64
from tests.helpers import locate_anchor, sig_widgets, verify_cms

pytestmark = pytest.mark.skipif(shutil.which("libreoffice") is None and shutil.which("soffice") is None,
                                reason="LibreOffice absent")

DOCX_CT = '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
DOCX_RELS = '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'


def make_docx(*paragraphs: str) -> bytes:
    corps = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    doc = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
           f'wordprocessingml/2006/main"><w:body>{corps}</w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", DOCX_CT)
        z.writestr("_rels/.rels", DOCX_RELS)
        z.writestr("word/document.xml", doc)
    return buf.getvalue()


@pytest.fixture
def dans_tmp(tmp_path, monkeypatch):
    """La conversion écrit des fichiers TEMP_* dans le répertoire courant."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_getinfo_docx(client, headers, dans_tmp):
    docx = make_docx("Titre du document", "Le Signataire")
    info = locate_anchor(client, headers, docx, recherche="Le Signataire", filename="exemple.docx")
    assert info["nombre_de_pages"] == 1
    assert info["signature_page"] == 1
    assert float(info["signature_coords"]["x1"]) > 0
    assert list(dans_tmp.glob("TEMP_*")) == [], "fichiers temporaires nettoyés"


def test_signature_docx(client, headers, sign_env, dans_tmp):
    docx = make_docx("Titre du document", "Le Signataire")
    r = client.post("/sign-basePDF64", headers=headers, json={
        "page": 1, "ocrlayer": False, "protect": False, "signature_box": "351, 121, 551, 221",
        "filedef1": {"filename": "exemple.docx", "content": b64(docx)}})
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"%PDF")
    assert len(sig_widgets(r.content, 0)) == 1
    verify_cms(r.content)


def test_signature_nominative_docx(client, headers, sign_env, dans_tmp):
    docx = make_docx("Texte")
    r = client.post("/sign-simple-name", headers=headers, json={
        "page": 1, "signername": "Jean Dupont", "signature_box": "351, 121, 551, 221",
        "filedef1": {"filename": "exemple.docx", "content": b64(docx)}})
    assert r.status_code == 200, r.text
    verify_cms(r.content)
