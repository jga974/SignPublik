"""Scénario de bout en bout : retrouver l'ancre, puis signer à cet endroit."""
from tests.conftest import ANCHOR_PAGE, b64, make_pdf
from tests.helpers import (box_under_anchor, locate_anchor, pixels_changed, sig_widgets,
                           signature_fields, to_rect, verify_cms)


def test_signature_et_griffe_sur_ancre(client, headers, sign_env):
    """Pose la signature électronique + la griffe à l'emplacement de l'ancre."""
    pdf = make_pdf()
    info = locate_anchor(client, headers, pdf)
    box = box_under_anchor(info)

    r = client.post("/sign-basePDF64", headers=headers, json={
        "page": info["signature_page"], "ocrlayer": False, "protect": False,
        "signature_box": ", ".join(map(str, box)),
        "filedef1": {"filename": "doc.pdf", "content": b64(pdf)},
    })
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    signed = r.content

    # signature électronique présente (champ /Sig avec ByteRange et CMS)
    sigs = signature_fields(signed)
    assert len(sigs) == 1
    assert len(sigs[0][1]["/ByteRange"]) == 4
    assert len(sigs[0][1]["/Contents"]) > 0

    # le document d'origine est conservé (mise à jour incrémentale)
    assert signed.startswith(pdf)

    # le widget est sur la bonne page, dans la boîte demandée
    widgets = sig_widgets(signed, ANCHOR_PAGE - 1)
    assert len(widgets) == 1
    assert [round(float(v)) for v in widgets[0]["/Rect"]] == list(box)

    # la griffe est visible : la zone de la boîte change au rendu
    assert pixels_changed(pdf, signed, ANCHOR_PAGE - 1, to_rect(box)) > 0.2

    # la signature est cryptographiquement valide
    verify_cms(signed)


def test_signature_nominative(client, headers, sign_env):
    """/sign-simple-name : la griffe est générée à partir du nom du signataire."""
    pdf = make_pdf()
    box = (350, 120, 550, 220)
    r = client.post("/sign-simple-name", headers=headers, json={
        "page": 1, "signername": "Jean Dupont",
        "signature_box": ", ".join(map(str, box)),
        "filedef1": {"filename": "doc.pdf", "content": b64(pdf)},
    })
    assert r.status_code == 200, r.text
    signed = r.content
    assert len(signature_fields(signed)) == 1
    assert pixels_changed(pdf, signed, 0, to_rect(box)) > 0.01
    verify_cms(signed)
