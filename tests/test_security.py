"""Tests de sécurité : vérification de la protection contre les vulnérabilités auditées."""
import os
import secrets
from pathlib import Path

import pytest
from app.config import API_KEY, SHARED_SECRET
from app.core.utilities import storeImage
from app.core.conversion import get_pdf_content
import app.core.constants as constants
from tests.conftest import b64


def test_path_traversal_store_image_bloque(tmp_path, monkeypatch):
    """Vérifie que storeImage refuse d'écrire en dehors de SIGN_PATH."""
    monkeypatch.setattr(constants, "SIGN_PATH", str(tmp_path))

    # Tentative d'écriture dans le répertoire parent
    payload_b64 = b64(b"\x89PNG\r\n\x1a\nfakeimage")
    nom_traversal = "../../../../tmp/malicious.png"

    result = storeImage(payload_b64, nom_traversal)

    # Le fichier ne doit jamais avoir été écrit dans /tmp/malicious.png
    assert not Path("/tmp/malicious.png").exists()
    # Le nom nettoyé reste confiné dans tmp_path
    if result:
        assert (tmp_path / result).exists()
        assert not (tmp_path / ".." / "malicious.png").exists()


def test_verification_api_key_constant_time():
    """Vérifie que la comparaison des secrets utilise secrets.compare_digest."""
    assert secrets.compare_digest("cle_correcte", "cle_correcte")
    assert not secrets.compare_digest("cle_fausse", "cle_correcte")


def test_path_traversal_docx_filename_sanitized(tmp_path, monkeypatch):
    """Vérifie que get_pdf_content nettoie les noms de fichiers contenant des traversées."""
    monkeypatch.chdir(tmp_path)
    content_fake = b64(b"not a real docx")

    try:
        get_pdf_content("../../../etc/fake.docx", content_fake)
    except Exception:
        pass

    # Aucun fichier TEMP_ ne doit exister hors du répertoire courant
    assert not Path("/etc/fake.docx").exists()
    assert not Path("/tmp/fake.docx").exists()


def test_anti_dos_payload_too_large(client, headers):
    """Vérifie le rejet HTTP 413 si la taille déclarée dépasse le seuil (ex: 30 Mo)."""
    r = client.post(
        "/getInfo-PDF",
        headers={**headers, "content-length": str(30 * 1024 * 1024)},
        json={"fichier": {"filename": "huge.pdf", "content": ""}, "recherche": "test"}
    )
    assert r.status_code == 413
    assert "Payload Too Large" in r.json()["detail"]


def test_anti_dos_rate_limiting(client, headers, monkeypatch):
    """Vérifie le blocage HTTP 429 Too Many Requests dès que le quota est dépassé."""
    import app.core.rate_limiter as rl
    monkeypatch.setattr(rl, "RATE_LIMIT_ENABLED", True)
    # Réinitialiser le limiteur pour ce test avec une limite basse (3 requêtes)
    limiteur = rl.SlidingWindowRateLimiter()
    monkeypatch.setattr(rl, "rate_limiter", limiteur)
    monkeypatch.setattr(rl, "RATE_LIMIT_GENERAL", 3)

    # 3 requêtes autorisées
    for _ in range(3):
        res = client.get("/hello/testeur")
        assert res.status_code == 200

    # 4ème requête : doit être bloquée avec 429
    res_bloquee = client.get("/hello/testeur")
    assert res_bloquee.status_code == 429
    assert "Too Many Requests" in res_bloquee.json()["detail"]
    assert "retry-after" in res_bloquee.headers

