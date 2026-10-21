"""Fonctions utilitaires : noms, images, flux, certificats."""
import base64
import io
import re
import time

import pytest
from PIL import Image

import app.core.constants as constants
from app.core import signature, utilities
from app.core.utilities import (cache_with_expiration, file_chunk_generator, generate_unique_filename,
                                get_image_size_in_points, nettoyer_chaine_complete, slugify, storeImage)


def png_b64(size=(113, 85), dpi=None) -> str:
    buf = io.BytesIO()
    kw = {"dpi": dpi} if dpi else {}
    Image.new("RGB", size, "white").save(buf, "PNG", **kw)
    return base64.b64encode(buf.getvalue()).decode()


# ---------- slugify / nettoyage ----------

@pytest.mark.parametrize("texte,attendu", [
    ("Jean Dupont", "jean-dupont"),
    ("  Jean   Dupont ", "-jean-dupont-"),
    ("Éloïse Çelik", "eloise-celik"),
    ("Jean-Pierre", "jeanpierre"),        # les tirets saisis sont supprimés
    ("O'Brien", "obrien"),
    ("Agent n°12", "agent-n12"),
    ("", ""),
])
def test_slugify(texte, attendu):
    assert slugify(texte) == attendu


def test_slugify_non_texte():
    assert slugify(None) == ""
    assert slugify(42) == ""


def test_nettoyer_options_par_defaut():
    assert nettoyer_chaine_complete("Été 2025 !") == "Ete2025"


def test_nettoyer_sans_chiffres():
    assert nettoyer_chaine_complete("abc123", garder_chiffres=False) == "abc"


def test_nettoyer_garder_tirets():
    assert nettoyer_chaine_complete("a-b c", garder_tirets=True, garder_espaces=True) == "a-b c"


def test_nettoyer_remplacement_prioritaire_sur_garder_espaces():
    assert nettoyer_chaine_complete("a b", garder_espaces=True, remplacer_espaces_par="_") == "a_b"


def test_nettoyer_minuscules():
    assert nettoyer_chaine_complete("ABC", minuscules=True) == "abc"


# ---------- noms de fichiers / flux ----------

def test_generate_unique_filename_format():
    nom = generate_unique_filename()
    assert re.fullmatch(r"\d{8}_\d{6}_[A-Za-z0-9]{4}\.pdf", nom)
    assert generate_unique_filename("png").endswith(".png")


def test_generate_unique_filename_differents():
    assert len({generate_unique_filename() for _ in range(50)}) > 1


def test_file_chunk_generator():
    data = b"x" * 20000
    morceaux = list(file_chunk_generator(io.BytesIO(data), chunk_size=8192))
    assert [len(m) for m in morceaux] == [8192, 8192, 3616]
    assert b"".join(morceaux) == data


def test_file_chunk_generator_vide():
    assert list(file_chunk_generator(io.BytesIO(b""))) == []


# ---------- taille des images ----------

def test_taille_image_72_dpi_par_defaut():
    assert get_image_size_in_points(png_b64((113, 85))) == (113, 85)


def test_taille_image_convertie_en_points():
    # 144 dpi : deux fois plus de pixels que de points
    assert get_image_size_in_points(png_b64((200, 100), dpi=(144, 144))) == (100, 50)


def test_taille_image_invalide():
    with pytest.raises(Exception):
        get_image_size_in_points(base64.b64encode(b"pas une image").decode())


def test_cache_avec_expiration(monkeypatch):
    appels = []

    @cache_with_expiration(10)
    def f(x):
        appels.append(x)
        return x * 2

    assert f(2) == 4 and f(2) == 4
    assert appels == [2]          # second appel servi par le cache
    assert f(3) == 6
    assert appels == [2, 3]

    t0 = time.time()
    monkeypatch.setattr(time, "time", lambda: t0 + 11)
    assert f(2) == 4
    assert appels == [2, 3, 2]    # cache expiré


# ---------- stockage d'image ----------

def test_store_image(tmp_path, monkeypatch):
    monkeypatch.setattr(constants, "SIGN_PATH", str(tmp_path))
    contenu = png_b64()
    assert storeImage(contenu, "ma_griffe.png") == "ma_griffe.png"
    assert (tmp_path / "ma_griffe.png").read_bytes() == base64.b64decode(contenu)


def test_store_image_ecrase(tmp_path, monkeypatch):
    monkeypatch.setattr(constants, "SIGN_PATH", str(tmp_path))
    storeImage(png_b64((10, 10)), "a.png")
    storeImage(png_b64((20, 20)), "a.png")
    assert Image.open(tmp_path / "a.png").size == (20, 20)


def test_store_image_erreur(tmp_path, monkeypatch):
    monkeypatch.setattr(constants, "SIGN_PATH", str(tmp_path / "inexistant"))
    assert storeImage(png_b64(), "a.png") is False


# ---------- chemins de certificats ----------

def test_chemins_certificat_en_minuscules():
    assert signature.get_cert_name("Jean.Dupont@AC-Corse.fr").endswith("jean.dupont@ac-corse.fr.pem")
    assert signature.get_key_name("Jean.Dupont@AC-Corse.fr").endswith("jean.dupont@ac-corse.fr_key.pem")


def test_certificate_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(signature, "SIGN_PATH", str(tmp_path))
    assert not signature.certificate_exists("a@b.fr")
    (tmp_path / "a@b.fr.pem").write_text("x")
    assert not signature.certificate_exists("a@b.fr")       # clé manquante
    (tmp_path / "a@b.fr_key.pem").write_text("x")
    assert signature.certificate_exists("A@B.fr")


def test_constantes_chemins():
    import os
    assert os.path.isdir(constants.SIGN_PATH)
    assert os.path.isfile(os.path.join(constants.FONTS_DIR, "DejaVuSans.ttf"))
    assert os.path.isabs(constants.DEFAULT_CERT_FILE)
