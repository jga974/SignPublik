"""Endpoints de signature : /sign-basePDF64 (griffe fixe) et /sign-simple-name (griffe nominative)."""
import os

import pytest

from tests.conftest import PAGE_H, b64, make_cert, make_pdf
from tests.helpers import (box_under_anchor, locate_anchor, page_identique, pixels_changed,
                           render, sig_widgets, signature_fields, to_rect, verify_cms)

BOX = (350, 120, 550, 220)


def payload_base(pdf, box=BOX, page=1, filename="doc.pdf"):
    return {
        "page": page, "ocrlayer": False, "protect": False,
        "signature_box": ", ".join(map(str, box)),
        "filedef1": {"filename": filename, "content": b64(pdf)},
    }


def payload_nom(pdf, nom="Jean Dupont", mail=None, box=BOX, page=1, filename="doc.pdf"):
    p = {"page": page, "signername": nom, "signature_box": ", ".join(map(str, box)),
         "filedef1": {"filename": filename, "content": b64(pdf)}}
    if mail:
        p["signermail"] = mail
    return p


def sign_base(client, headers, pdf, **kw):
    return client.post("/sign-basePDF64", headers=headers, json=payload_base(pdf, **kw))


def sign_nom(client, headers, pdf, **kw):
    return client.post("/sign-simple-name", headers=headers, json=payload_nom(pdf, **kw))


# ---------- /sign-basePDF64 ----------

@pytest.mark.parametrize("page", [1, 2, 3])
def test_signature_sur_chaque_page(client, headers, sign_env, page):
    pdf = make_pdf(pages=3)
    r = sign_base(client, headers, pdf, page=page)
    assert r.status_code == 200, r.text
    signed = r.content
    for i in range(3):
        attendu = 1 if i == page - 1 else 0
        assert len(sig_widgets(signed, i)) == attendu, f"page {i + 1}"
    # les autres pages restent visuellement identiques
    for i in range(3):
        if i != page - 1:
            assert page_identique(pdf, signed, i)


@pytest.mark.parametrize("box", [(50, 50, 250, 150), (350, 120, 550, 220), (100, 700, 300, 800)])
def test_widget_dans_la_boite_demandee(client, headers, sign_env, box):
    pdf = make_pdf()
    signed = sign_base(client, headers, pdf, box=box).content
    rect = [round(float(v)) for v in sig_widgets(signed, 0)[0]["/Rect"]]
    assert rect == list(box)
    assert pixels_changed(pdf, signed, 0, to_rect(box)) > 0.2


def test_rien_ne_change_hors_de_la_boite(client, headers, sign_env):
    """Seule la zone de la boîte est modifiée au rendu de la page."""
    import pymupdf
    pdf = make_pdf()
    signed = sign_base(client, headers, pdf).content
    zone = to_rect(BOX)
    a, n = render(pdf, 0)
    b, _ = render(signed, 0)
    largeur = 595
    for y in range(0, 842, 7):
        for x in range(0, largeur, 7):
            if zone.x0 - 1 <= x <= zone.x1 + 1 and zone.y0 - 1 <= y <= zone.y1 + 1:
                continue
            i = (y * largeur + x) * n
            ecart = max(abs(p - q) for p, q in zip(a[i:i + n], b[i:i + n]))
            assert ecart <= 3, f"pixel modifié hors boîte en ({x},{y})"


def test_signature_valide_cryptographiquement(client, headers, sign_env):
    signed = sign_base(client, headers, make_pdf()).content
    cert = verify_cms(signed)
    assert cert.subject.rfc4514_string() == "CN=Test Signataire"


def test_modification_apres_signature_detectee(client, headers, sign_env):
    """Altérer un octet de la zone signée casse l'empreinte : verify_cms doit le voir."""
    signed = bytearray(sign_base(client, headers, make_pdf()).content)
    signed[100] ^= 0xFF
    with pytest.raises(AssertionError):
        verify_cms(bytes(signed))


def test_pdf_d_origine_conserve(client, headers, sign_env):
    pdf = make_pdf()
    assert sign_base(client, headers, pdf).content.startswith(pdf)


def test_en_tete_nom_du_fichier(client, headers, sign_env):
    r = sign_base(client, headers, make_pdf(), filename="contrat.pdf")
    assert r.headers["content-disposition"] == "attachment; filename=signed_contrat.pdf"


def test_signatures_successives(client, headers, sign_env):
    """Re-signer un PDF déjà signé ajoute une seconde signature et garde la première valide."""
    pdf = make_pdf()
    une = sign_base(client, headers, pdf, box=(50, 50, 250, 150)).content
    deux = client.post("/sign-basePDF64", headers=headers,
                       json=payload_base(une, box=(350, 50, 550, 150))).content
    assert len(signature_fields(deux)) == 2
    verify_cms(deux, 0)
    verify_cms(deux, 1)
    assert deux.startswith(une)


def test_signatures_successives_meme_nom_de_champ(client, headers, sign_env):
    """Comportement actuel (à surveiller) : chaque signature reçoit le nom de champ
    « Signature1 », donc deux signatures successives portent le même nom."""
    pdf = make_pdf()
    une = sign_base(client, headers, pdf, box=(50, 50, 250, 150)).content
    deux = client.post("/sign-basePDF64", headers=headers,
                       json=payload_base(une, box=(350, 50, 550, 150))).content
    assert [n for n, _ in signature_fields(deux)] == ["Signature1", "Signature1"]


def test_page_zero_ou_negative_signe_la_premiere(client, headers, sign_env):
    for page in (0, -3):
        signed = sign_base(client, headers, make_pdf(pages=2), page=page).content
        assert len(sig_widgets(signed, 0)) == 1
        assert len(sig_widgets(signed, 1)) == 0


def test_boite_par_defaut_du_modele(client, headers, sign_env):
    """Sans signature_box, le modèle fournit « 350, 120, 550, 220 »."""
    p = payload_base(make_pdf())
    del p["signature_box"]
    r = client.post("/sign-basePDF64", headers=headers, json=p)
    assert r.status_code == 200
    assert [round(float(v)) for v in sig_widgets(r.content, 0)[0]["/Rect"]] == list(BOX)


def test_boite_avec_espaces_et_decimaux(client, headers, sign_env):
    """Espaces tolérés ; les décimales (comme celles de /getInfo-PDF) sont arrondies."""
    p = payload_base(make_pdf())
    p["signature_box"] = "  100 , 100.4 ,300.5, 200 "
    r = client.post("/sign-basePDF64", headers=headers, json=p)
    assert r.status_code == 200
    assert [round(float(v)) for v in sig_widgets(r.content, 0)[0]["/Rect"]] == [100, 100, 300, 200]


# ---------- erreurs ----------

def test_pdf_invalide(client, headers, sign_env):
    r = sign_base(client, headers, b"ceci n'est pas un pdf")
    assert r.status_code == 400
    assert "Erreur lors de la signature" in r.json()["detail"]


def test_base64_invalide(client, headers, sign_env):
    p = payload_base(make_pdf())
    p["filedef1"]["content"] = "%%%"
    assert client.post("/sign-basePDF64", headers=headers, json=p).status_code == 400


def test_certificat_absent(client, headers, sign_env):
    os.remove(sign_env / "cert.pem")
    r = sign_base(client, headers, make_pdf())
    assert r.status_code == 400


def test_cle_privee_absente(client, headers, sign_env):
    os.remove(sign_env / "private_key.pem")
    assert sign_base(client, headers, make_pdf()).status_code == 400


def test_image_de_signature_absente(client, headers, sign_env):
    """/sign-basePDF64 utilise signature_signe_noBG.png dans SIGN_PATH."""
    os.remove(sign_env / "signature_signe_noBG.png")
    assert sign_base(client, headers, make_pdf()).status_code == 400


@pytest.mark.parametrize("route,payload", [
    ("/sign-basePDF64", lambda: payload_base(make_pdf())),
    ("/sign-simple-name", lambda: payload_nom(make_pdf())),
])
class TestAuthentification:
    def test_sans_cle(self, client, sign_env, route, payload):
        assert client.post(route, json=payload()).status_code == 422

    def test_mauvaise_cle(self, client, sign_env, route, payload):
        assert client.post(route, json=payload(), headers={"api-key": "x"}).status_code == 403

    def test_corps_vide(self, client, headers, sign_env, route, payload):
        assert client.post(route, json={}, headers=headers).status_code == 422


def test_champs_obligatoires_du_modele(client, headers, sign_env):
    """ocrlayer et protect sont requis par SignBasePDFRequest (même s'ils ne servent pas)."""
    p = payload_base(make_pdf())
    del p["ocrlayer"]
    assert client.post("/sign-basePDF64", headers=headers, json=p).status_code == 422


# ---------- /sign-simple-name ----------

def test_griffe_nominative_visible_et_valide(client, headers, sign_env):
    pdf = make_pdf()
    signed = sign_nom(client, headers, pdf).content
    assert pixels_changed(pdf, signed, 0, to_rect(BOX)) > 0.01
    verify_cms(signed)


def test_griffe_differente_selon_le_nom(client, headers, sign_env):
    pdf = make_pdf()
    a = sign_nom(client, headers, pdf, nom="Jean Dupont").content
    b = sign_nom(client, headers, pdf, nom="Marie Martin").content
    assert render(a, 0, to_rect(BOX)) != render(b, 0, to_rect(BOX))


def test_image_de_griffe_stockee_sous_un_nom_slugifie(client, headers, sign_env):
    sign_nom(client, headers, make_pdf(), nom="Éloïse Dupont-Martin")
    # accents retirés, minuscules, espaces -> « - » ; les tirets saisis sont supprimés
    assert (sign_env / "eloise-dupontmartin.png").exists()


def test_certificat_du_signataire_utilise_si_present(client, headers, sign_env):
    """Si <mail>.pem et <mail>_key.pem existent dans SIGN_PATH, c'est ce certificat qui signe."""
    cert_pem, key_pem = make_cert("Marie Martin")
    (sign_env / "marie.martin@ac-corse.fr.pem").write_bytes(cert_pem)
    (sign_env / "marie.martin@ac-corse.fr_key.pem").write_bytes(key_pem)
    signed = sign_nom(client, headers, make_pdf(), nom="Marie Martin",
                      mail="Marie.Martin@ac-corse.fr").content   # la casse est ignorée
    assert verify_cms(signed).subject.rfc4514_string() == "CN=Marie Martin"


def test_certificat_par_defaut_si_signataire_inconnu(client, headers, sign_env):
    signed = sign_nom(client, headers, make_pdf(), mail="inconnu@ac-corse.fr").content
    assert verify_cms(signed).subject.rfc4514_string() == "CN=Test Signataire"


def test_certificat_sans_cle_ignore(client, headers, sign_env):
    """Un .pem sans _key.pem n'est pas considéré comme un certificat de signataire."""
    cert_pem, _ = make_cert("Sans Cle")
    (sign_env / "orphelin@ac-corse.fr.pem").write_bytes(cert_pem)
    signed = sign_nom(client, headers, make_pdf(), mail="orphelin@ac-corse.fr").content
    assert verify_cms(signed).subject.rfc4514_string() == "CN=Test Signataire"


def test_nom_vide(client, headers, sign_env):
    """Nom vide : la griffe est quand même produite (fichier « .png »), pas d'erreur 500."""
    r = sign_nom(client, headers, make_pdf(), nom="")
    assert r.status_code in (200, 400)


def test_adresse_mail_par_defaut_du_modele():
    from app.models.files import SignBasePDFRequestName
    m = SignBasePDFRequestName(page=1, signername="A", filedef1={"filename": "d.pdf", "content": ""})
    assert m.signermail == "NOTNOW@ll.fr"
    assert m.signature_box == "350, 120, 550, 220"


# ---------- scénario complet ancre -> signature ----------

@pytest.mark.parametrize("anchor_page", [1, 2, 3])
def test_signature_sous_l_ancre(client, headers, sign_env, anchor_page):
    pdf = make_pdf(pages=3, anchor_page=anchor_page)
    info = locate_anchor(client, headers, pdf)
    box = box_under_anchor(info)
    signed = sign_base(client, headers, pdf, box=box, page=info["signature_page"]).content
    assert len(sig_widgets(signed, anchor_page - 1)) == 1
    assert pixels_changed(pdf, signed, anchor_page - 1, to_rect(box)) > 0.2
    # la griffe ne recouvre pas le texte de l'ancre
    c = {k: float(v) for k, v in info["signature_coords"].items()}
    import pymupdf
    zone_ancre = pymupdf.Rect(c["x1"], c["y1"], c["x2"], c["y2"])
    assert not to_rect(box).intersects(zone_ancre)
    verify_cms(signed)


def test_signature_nominative_sous_l_ancre(client, headers, sign_env):
    pdf = make_pdf()
    info = locate_anchor(client, headers, pdf)
    box = box_under_anchor(info, largeur=130, hauteur=100)
    signed = sign_nom(client, headers, pdf, box=box, page=info["signature_page"]).content
    assert len(sig_widgets(signed, 1)) == 1
    assert pixels_changed(pdf, signed, 1, to_rect(box)) > 0.01
