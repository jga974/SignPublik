"""/getInfo-PDF : nombre de pages, taille, et position d'un texte (l'ancre de la griffe)."""
import json

import pymupdf
import pytest

from tests.conftest import ANCHOR, PAGE_H, PAGE_W, b64, make_pdf
from tests.helpers import locate_anchor


def pdf_with_texts(*pages_texts, fontsize=12):
    """PDF dont chaque page contient la liste de (texte, (x, y)) donnée (y depuis le haut)."""
    doc = pymupdf.open()
    for texts in pages_texts:
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        for text, pos in texts:
            page.insert_text(pos, text, fontsize=fontsize, fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data


# ---------- structure de la réponse ----------

def test_reponse_complete(client, headers):
    info = locate_anchor(client, headers, make_pdf(pages=3), filename="mon_doc.pdf")
    assert info["filename"] == "mon_doc.pdf"
    assert info["nombre_de_pages"] == 3
    assert info["pagesize"] == {"width": str(PAGE_W), "height": str(PAGE_H)}
    assert set(info["signature_coords"]) == {"x1", "y1", "x2", "y2"}
    assert "metadonnees" in info


@pytest.mark.parametrize("pages", [1, 2, 5])
def test_nombre_de_pages_et_liste_publik(client, headers, pages):
    """json_page est la liste {id, text} attendue par Publik, de 1 à n."""
    info = locate_anchor(client, headers, make_pdf(pages=pages, anchor_page=1))
    assert info["nombre_de_pages"] == pages
    assert json.loads(info["json_page"]) == [{"id": str(i), "text": str(i)} for i in range(1, pages + 1)]


def test_taille_de_page_non_a4(client, headers):
    doc = pymupdf.open()
    doc.new_page(width=300, height=400)
    info = locate_anchor(client, headers, doc.tobytes())
    assert info["pagesize"] == {"width": "300", "height": "400"}


# ---------- position de l'ancre ----------

@pytest.mark.parametrize("anchor_page", [1, 2, 3])
def test_page_de_l_ancre(client, headers, anchor_page):
    info = locate_anchor(client, headers, make_pdf(pages=3, anchor_page=anchor_page))
    assert info["signature_page"] == anchor_page


def test_coordonnees_de_l_ancre(client, headers):
    """Les coordonnées renvoyées encadrent le texte posé en (72, 700), repère haut-gauche."""
    info = locate_anchor(client, headers, make_pdf())
    c = {k: float(v) for k, v in info["signature_coords"].items()}
    assert 70 <= c["x1"] <= 74
    assert c["x2"] > c["x1"] and c["y2"] > c["y1"]
    # la ligne de base est à y=700 : le texte est juste au-dessus
    assert c["y1"] < 700 < c["y2"] + 3
    assert c["y2"] - c["y1"] < 20
    # largeur plausible pour 9 caractères en 12 pt
    assert 40 < c["x2"] - c["x1"] < 90


def test_ancre_deplacee(client, headers):
    """La position suit le texte : une ancre en haut à droite donne d'autres coordonnées."""
    pdf = pdf_with_texts([(ANCHOR, (400, 100))])
    c = locate_anchor(client, headers, pdf)["signature_coords"]
    assert 398 <= float(c["x1"]) <= 402
    assert 85 <= float(c["y1"]) <= 100


def test_ancre_absente(client, headers):
    info = locate_anchor(client, headers, make_pdf(anchor="Autre texte"))
    assert info["signature_page"] == -1
    assert {k: float(v) for k, v in info["signature_coords"].items()} == \
        {"x1": -1, "y1": -1, "x2": -1, "y2": -1}


def test_recherche_insensible_a_la_casse(client, headers):
    info = locate_anchor(client, headers, make_pdf(), recherche=ANCHOR.upper())
    assert info["signature_page"] == 2


def test_recherche_phrase_complete(client, headers):
    pdf = pdf_with_texts([("Le Signataire autorisé", (72, 300))])
    info = locate_anchor(client, headers, pdf, recherche="Le Signataire")
    assert info["signature_page"] == 1


def test_recherche_avec_accents(client, headers):
    pdf = pdf_with_texts([("Secrétaire général", (72, 300))])
    info = locate_anchor(client, headers, pdf, recherche="Secrétaire")
    assert info["signature_page"] == 1


def test_recherche_par_defaut_est_secretaire(client, headers):
    """Sans champ `recherche`, le modèle cherche « Secrétaire »."""
    pdf = pdf_with_texts([("Le Secrétaire", (72, 300))])
    r = client.post("/getInfo-PDF", headers=headers,
                    json={"fichier": {"filename": "d.pdf", "content": b64(pdf)}})
    assert r.status_code == 200
    assert r.json()["signature_page"] == 1


def test_premiere_occurrence_dans_une_page(client, headers):
    """Plusieurs occurrences sur la même page : seule la première renvoyée par pymupdf
    est retenue (ordre du flux du PDF, pas forcément la plus haute de la page)."""
    pdf = pdf_with_texts([(ANCHOR, (72, 600)), (ANCHOR, (72, 200))])
    attendu = pymupdf.open(stream=pdf, filetype="pdf")[0].search_for(ANCHOR)[0]
    c = locate_anchor(client, headers, pdf)["signature_coords"]
    assert float(c["y1"]) == pytest.approx(attendu.y0)
    assert float(c["x1"]) == pytest.approx(attendu.x0)


def test_occurrences_sur_plusieurs_pages_derniere_page_retenue(client, headers):
    """Comportement actuel : la boucle ne s'arrête pas à la première page trouvée,
    c'est donc la DERNIÈRE page contenant le texte qui est renvoyée."""
    pdf = pdf_with_texts([(ANCHOR, (72, 100))], [], [(ANCHOR, (72, 500))])
    info = locate_anchor(client, headers, pdf)
    assert info["nombre_de_pages"] == 3
    assert info["signature_page"] == 3
    assert 480 < float(info["signature_coords"]["y1"]) < 500


# ---------- entrées invalides / sécurité ----------

def test_sans_cle_api(client):
    r = client.post("/getInfo-PDF", json={"fichier": {"filename": "d.pdf", "content": ""}})
    assert r.status_code == 422


def test_mauvaise_cle_api(client):
    r = client.post("/getInfo-PDF", headers={"api-key": "mauvaise"},
                    json={"fichier": {"filename": "d.pdf", "content": b64(make_pdf())}})
    assert r.status_code == 403


def test_corps_incomplet(client, headers):
    r = client.post("/getInfo-PDF", headers=headers, json={"recherche": ANCHOR})
    assert r.status_code == 422


def test_contenu_non_pdf(client, headers):
    r = client.post("/getInfo-PDF", headers=headers,
                    json={"fichier": {"filename": "d.pdf", "content": b64(b"ceci n'est pas un pdf")}})
    assert r.status_code == 400
    assert "Erreur lors de la lecture des infos" in r.json()["detail"]


def test_base64_invalide(client, headers):
    r = client.post("/getInfo-PDF", headers=headers,
                    json={"fichier": {"filename": "d.pdf", "content": "%%%pas du base64%%%"}})
    assert r.status_code == 400


def test_route_avec_slash_final(client, headers):
    """Les anciens clients appellent /getInfo-PDF/ : la route doit répondre (redirection suivie)."""
    r = client.post("/getInfo-PDF/", headers=headers, json={
        "fichier": {"filename": "d.pdf", "content": b64(make_pdf())}, "recherche": ANCHOR})
    assert r.status_code == 200
    assert r.json()["signature_page"] == 2
