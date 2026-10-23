"""Validation de l'emplacement de la signature (boîte + page)."""
import pymupdf
import pytest

from app.core.signature_box import SignatureBoxError, parse_signature_box, resolve_signature_location
from tests.conftest import PAGE_H, PAGE_W, b64, make_pdf
from tests.helpers import locate_anchor, sig_widgets, verify_cms


# ---------- parse_signature_box ----------

@pytest.mark.parametrize("texte,attendu", [
    ("350, 120, 550, 220", (350, 120, 550, 220)),
    ("350,120,550,220", (350, 120, 550, 220)),
    ("  1 , 2 ,3, 4 ", (1, 2, 3, 4)),
    ("72.4, 174.6, 272.5, 274.49", (72, 175, 272, 274)),   # décimales arrondies
    ("-10, 0, 10, 20", (-10, 0, 10, 20)),
])
def test_parse_valide(texte, attendu):
    assert parse_signature_box(texte) == attendu


@pytest.mark.parametrize("texte", [
    "", "pas, une, boite", "1, 2, 3", "1, 2, 3, 4, 5", "1;2;3;4", "1, 2, 3, x", "1, 2, , 4",
    "1e3, 2, 3, 4", "NaN, 0, 1, 1", "0x10, 0, 1, 1",
])
def test_parse_invalide(texte):
    with pytest.raises(SignatureBoxError):
        parse_signature_box(texte)


# ---------- resolve_signature_location ----------

PDF = make_pdf(pages=2)


def test_resolve_ok():
    assert resolve_signature_location(PDF, "100, 100, 300, 200", 2) == ((100, 100, 300, 200), 1)


@pytest.mark.parametrize("page,index", [(1, 0), (2, 1), (0, 0), (-5, 0)])
def test_resolve_numero_de_page(page, index):
    assert resolve_signature_location(PDF, "100, 100, 300, 200", page)[1] == index


def test_resolve_page_inexistante():
    with pytest.raises(SignatureBoxError, match="page 3 inexistante.*2 page"):
        resolve_signature_location(PDF, "100, 100, 300, 200", 3)


@pytest.mark.parametrize("box", ["300, 100, 100, 200", "100, 200, 300, 100", "100, 100, 100, 200", "100, 100, 300, 100"])
def test_resolve_boite_inversee_ou_nulle(box):
    with pytest.raises(SignatureBoxError, match="gauche < droite"):
        resolve_signature_location(PDF, box, 1)


@pytest.mark.parametrize("box", [
    "-1, 100, 300, 200",                       # à gauche de la page
    "100, -1, 300, 200",                       # sous la page
    f"100, 100, {PAGE_W + 1}, 200",            # à droite
    f"100, 100, 300, {PAGE_H + 1}",            # au-dessus
    "900, 900, 1100, 1000",
])
def test_resolve_hors_page(box):
    with pytest.raises(SignatureBoxError, match="sort de la page 1"):
        resolve_signature_location(PDF, box, 1)


def test_resolve_boite_egale_a_la_page():
    assert resolve_signature_location(PDF, f"0, 0, {PAGE_W}, {PAGE_H}", 1)[0] == (0, 0, PAGE_W, PAGE_H)


def test_resolve_utilise_la_taille_de_la_page_visee():
    doc = pymupdf.open()
    doc.new_page(width=600, height=800)
    doc.new_page(width=200, height=300)
    pdf = doc.tobytes()
    assert resolve_signature_location(pdf, "100, 100, 500, 700", 1)[1] == 0
    with pytest.raises(SignatureBoxError, match="sort de la page 2.*200 x 300"):
        resolve_signature_location(pdf, "100, 100, 500, 700", 2)


def test_resolve_pdf_invalide():
    with pytest.raises(Exception):
        resolve_signature_location(b"pas un pdf", "1, 1, 2, 2", 1)


# ---------- via l'API : 422 avec un message clair ----------

ROUTES = ["/sign-basePDF64", "/sign-simple-name"]


def payload(route, pdf, box, page=1):
    base = {"page": page, "signature_box": box, "filedef1": {"filename": "d.pdf", "content": b64(pdf)}}
    if route == "/sign-basePDF64":
        base.update(ocrlayer=False, protect=False)
    else:
        base.update(signername="Jean Dupont")
    return base


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("box,fragment", [
    ("pas, une, boite", "signature_box invalide"),
    ("300, 100, 100, 200", "gauche < droite"),
    ("900, 900, 1100, 1000", "sort de la page"),
    ("-50, -50, 100, 100", "sort de la page"),
    ("100, 100, 100, 100", "gauche < droite"),
])
def test_api_boite_invalide_422(client, headers, sign_env, route, box, fragment):
    r = client.post(route, headers=headers, json=payload(route, make_pdf(), box))
    assert r.status_code == 422, r.text
    assert fragment in r.json()["detail"]


@pytest.mark.parametrize("route", ROUTES)
def test_api_page_inexistante_422(client, headers, sign_env, route):
    r = client.post(route, headers=headers, json=payload(route, make_pdf(pages=2), "100, 100, 300, 200", page=9))
    assert r.status_code == 422
    assert "page 9 inexistante" in r.json()["detail"]
    assert "2 page" in r.json()["detail"]


@pytest.mark.parametrize("route", ROUTES)
def test_api_aucune_signature_si_boite_invalide(client, headers, sign_env, route):
    """Rien n'est signé : la réponse est une erreur JSON, pas un PDF."""
    r = client.post(route, headers=headers, json=payload(route, make_pdf(), "900, 900, 1100, 1000"))
    assert r.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize("route", ROUTES)
def test_api_decimales_de_getinfo_acceptees(client, headers, sign_env, route):
    """Les coordonnées décimales renvoyées par /getInfo-PDF peuvent être reprises telles quelles."""
    pdf = make_pdf()
    info = locate_anchor(client, headers, pdf)
    c = info["signature_coords"]
    h = float(info["pagesize"]["height"])
    box = f"{c['x1']}, {h - float(c['y1']) - 120}, {float(c['x1']) + 200}, {h - float(c['y1']) - 20}"
    r = client.post(route, headers=headers, json=payload(route, pdf, box, page=info["signature_page"]))
    assert r.status_code == 200, r.text
    assert len(sig_widgets(r.content, 1)) == 1
    verify_cms(r.content)


def test_api_boite_par_defaut_trop_grande_pour_une_petite_page(client, headers, sign_env):
    """La boîte par défaut (350, 120, 550, 220) ne tient pas sur une page A5 : erreur explicite."""
    doc = pymupdf.open()
    doc.new_page(width=420, height=595)   # A5
    r = client.post("/sign-basePDF64", headers=headers, json={
        "page": 1, "ocrlayer": False, "protect": False,
        "filedef1": {"filename": "d.pdf", "content": b64(doc.tobytes())}})
    assert r.status_code == 422
    assert "sort de la page" in r.json()["detail"]


# ---------- les erreurs de signature ne sont plus masquées ----------

def test_message_d_erreur_pdf_invalide_lisible(client, headers, sign_env):
    r = client.post("/sign-basePDF64", headers=headers, json=payload("/sign-basePDF64", b"pas un pdf", "1, 1, 2, 2"))
    assert r.status_code == 400
    assert "not all arguments converted" not in r.json()["detail"]


def test_message_d_erreur_certificat_absent_lisible(client, headers, sign_env):
    import os
    os.remove(sign_env / "cert.pem")
    r = client.post("/sign-basePDF64", headers=headers, json=payload("/sign-basePDF64", make_pdf(), "100, 100, 300, 200"))
    assert r.status_code == 400
    assert "not all arguments converted" not in r.json()["detail"]
    assert "cert.pem" in r.json()["detail"]
