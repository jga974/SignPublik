"""scripts/signer_pdf.py : signer un PDF à une ancre avec une griffe créée à partir d'un nom."""
import pymupdf
import pytest

from scripts import signer_pdf
from scripts.signer_pdf import SignerError, boite_pres_de_l_ancre, main, signer
from tests.conftest import ANCHOR, ANCHOR_PAGE, PAGE_H, PAGE_W, make_cert, make_pdf
from tests.helpers import pixels_changed, sig_widgets, signature_fields, to_rect, verify_cms


def info_ancre(x1=72, y1=700, y2=715, w=PAGE_W, h=PAGE_H, page=2):
    return {"signature_page": page, "pagesize": {"width": str(w), "height": str(h)},
            "signature_coords": {"x1": str(x1), "y1": str(y1), "x2": str(x1 + 50), "y2": str(y2)}}


# ---------- calcul de la boîte ----------

def test_boite_sous_l_ancre():
    # ancre à 120 pt du haut, hauteur 15 pt -> bas du texte à 135 ; 20 pt de marge ; boîte 180 x 135
    x1, y1, x2, y2 = boite_pres_de_l_ancre(info_ancre(y1=120, y2=135), 180, 135, 20)
    assert (x1, x2 - x1, y2 - y1) == (72, 180, 135)
    assert y2 == PAGE_H - 135 - 20


def test_boite_au_dessus_si_pas_de_place_dessous():
    """Ancre en bas de page : la boîte passe au-dessus du texte."""
    x1, y1, x2, y2 = boite_pres_de_l_ancre(info_ancre(y1=780, y2=795), 180, 135, 20)
    assert y1 == PAGE_H - 780 + 20          # 20 pt au-dessus du haut du texte
    assert y2 - y1 == 135


def test_boite_decalee_pour_rester_dans_la_page():
    x1, _, x2, _ = boite_pres_de_l_ancre(info_ancre(x1=500, y1=120, y2=135), 180, 135, 20)
    assert x2 == PAGE_W and x2 - x1 == 180


def test_boite_trop_grande_pour_la_page():
    with pytest.raises(SignerError, match="plus grande que la page"):
        boite_pres_de_l_ancre(info_ancre(), PAGE_W + 1, 100, 20)


def test_boite_aucune_place():
    with pytest.raises(SignerError, match="pas assez de place"):
        boite_pres_de_l_ancre(info_ancre(y1=400, y2=415, h=800), 180, 700, 20)


# ---------- signature via les API réelles (TestClient) ----------

def test_signer_sous_l_ancre(client, headers, sign_env):
    pdf = make_pdf()
    # l'ancre de make_pdf est à 138 pt du bas de la page : une zone de 150 x 100 tient dessous
    signe = signer(client, "", headers["api-key"], pdf, "doc.pdf", "Michel Dupont", ANCHOR,
                   largeur=150, hauteur=100)

    assert signe.startswith(pdf)
    assert len(signature_fields(signe)) == 1
    verify_cms(signe)

    # le widget est sur la page de l'ancre, sous le texte
    widgets = sig_widgets(signe, ANCHOR_PAGE - 1)
    assert len(widgets) == 1
    x1, y1, x2, y2 = (float(v) for v in widgets[0]["/Rect"])
    ancre = pymupdf.open(stream=pdf, filetype="pdf")[ANCHOR_PAGE - 1].search_for(ANCHOR)[0]
    assert PAGE_H - y2 > ancre.y1, "la signature est sous l'ancre"
    assert x1 == pytest.approx(ancre.x0, abs=1)
    # la griffe « Michel Dupont » est visible
    assert pixels_changed(pdf, signe, ANCHOR_PAGE - 1, to_rect((x1, y1, x2, y2))) > 0.01


def test_signer_zone_par_defaut_passe_au_dessus_si_la_place_manque(client, headers, sign_env):
    """Zone par défaut (180 x 135) : trop haute pour tenir sous l'ancre de make_pdf -> au-dessus."""
    pdf = make_pdf()
    signe = signer(client, "", headers["api-key"], pdf, "doc.pdf", "Michel Dupont", ANCHOR)
    y1 = float(sig_widgets(signe, ANCHOR_PAGE - 1)[0]["/Rect"][1])
    ancre = pymupdf.open(stream=pdf, filetype="pdf")[ANCHOR_PAGE - 1].search_for(ANCHOR)[0]
    assert y1 > PAGE_H - ancre.y0
    verify_cms(signe)


def test_signer_griffe_depend_du_nom(client, headers, sign_env):
    pdf = make_pdf()
    a = signer(client, "", headers["api-key"], pdf, "d.pdf", "Michel Dupont", ANCHOR)
    b = signer(client, "", headers["api-key"], pdf, "d.pdf", "Marie Martin", ANCHOR)
    from tests.helpers import render
    zone = to_rect(tuple(float(v) for v in sig_widgets(a, 1)[0]["/Rect"]))
    assert render(a, 1, zone) != render(b, 1, zone)


def test_signer_certificat_du_signataire(client, headers, sign_env):
    cert_pem, key_pem = make_cert("Michel Dupont")
    (sign_env / "michel.dupont@ac-corse.fr.pem").write_bytes(cert_pem)
    (sign_env / "michel.dupont@ac-corse.fr_key.pem").write_bytes(key_pem)
    signe = signer(client, "", headers["api-key"], make_pdf(), "d.pdf", "Michel Dupont", ANCHOR,
                   mail="michel.dupont@ac-corse.fr")
    assert verify_cms(signe).subject.rfc4514_string() == "CN=Michel Dupont"


def test_signer_ancre_introuvable(client, headers, sign_env):
    with pytest.raises(SignerError, match="ancre « Inconnue » introuvable"):
        signer(client, "", headers["api-key"], make_pdf(), "d.pdf", "Michel Dupont", "Inconnue")


def test_signer_mauvaise_cle_api(client, sign_env):
    with pytest.raises(SignerError, match="HTTP 403"):
        signer(client, "", "mauvaise", make_pdf(), "d.pdf", "Michel Dupont", ANCHOR)


def test_signer_ancre_en_bas_de_page(client, headers, sign_env):
    """Ancre tout en bas : la signature est placée au-dessus, et reste valide."""
    doc = pymupdf.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    page.insert_text((72, 820), ANCHOR, fontsize=12)
    signe = signer(client, "", headers["api-key"], doc.tobytes(), "d.pdf", "Michel Dupont", ANCHOR)
    y1 = float(sig_widgets(signe, 0)[0]["/Rect"][1])
    ancre = pymupdf.open(stream=signe, filetype="pdf")[0].search_for(ANCHOR)[0]
    assert y1 > PAGE_H - ancre.y0, "la boîte est au-dessus de l'ancre"
    verify_cms(signe)


# ---------- ligne de commande ----------

def lancer(client, tmp_path, *args, pdf=None):
    entree = tmp_path / "contrat.pdf"
    entree.write_bytes(pdf or make_pdf())
    return main([str(entree), *args, "--url", ""], session=client), tmp_path


def test_cli_ok(client, headers, sign_env, tmp_path, capsys):
    code, _ = lancer(client, tmp_path, "--nom", "Michel Dupont", "--ancre", ANCHOR,
                     "--api-key", headers["api-key"])
    assert code == 0
    sortie = tmp_path / "signed_contrat.pdf"
    assert sortie.exists()
    verify_cms(sortie.read_bytes())
    assert str(sortie) in capsys.readouterr().out


def test_cli_sortie_personnalisee(client, headers, sign_env, tmp_path):
    cible = tmp_path / "dossier" / "final.pdf"
    cible.parent.mkdir()
    code, _ = lancer(client, tmp_path, "--nom", "Michel Dupont", "--ancre", ANCHOR,
                     "--api-key", headers["api-key"], "--sortie", str(cible))
    assert code == 0 and cible.exists()


def test_cli_ancre_introuvable(client, headers, sign_env, tmp_path, capsys):
    code, _ = lancer(client, tmp_path, "--nom", "M D", "--ancre", "Inconnue", "--api-key", headers["api-key"])
    assert code == 1
    assert "introuvable" in capsys.readouterr().err
    assert not (tmp_path / "signed_contrat.pdf").exists()


def test_cli_cle_api_manquante(client, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("API_KEY", raising=False)
    code, _ = lancer(client, tmp_path, "--nom", "M D", "--ancre", ANCHOR)
    assert code == 1
    assert "clé API manquante" in capsys.readouterr().err


def test_cli_fichier_introuvable(client, tmp_path, capsys):
    code = main([str(tmp_path / "absent.pdf"), "--nom", "M D", "--ancre", ANCHOR, "--api-key", "x",
                 "--url", ""], session=client)
    assert code == 1
    assert "fichier introuvable" in capsys.readouterr().err


def test_cli_arguments_obligatoires(tmp_path):
    with pytest.raises(SystemExit):
        main([str(tmp_path / "x.pdf")])


def test_cli_service_injoignable(tmp_path, capsys):
    entree = tmp_path / "c.pdf"
    entree.write_bytes(make_pdf())
    code = main([str(entree), "--nom", "M D", "--ancre", ANCHOR, "--api-key", "x",
                 "--url", "http://127.0.0.1:9"])
    assert code == 1
    assert "injoignable" in capsys.readouterr().err
