import io

import pymupdf
import pypdf

from tests.conftest import ANCHOR, ANCHOR_PAGE, PAGE_H, b64, make_pdf


def locate_anchor(client, headers, pdf: bytes):
    r = client.post("/getInfo-PDF", headers=headers, json={
        "fichier": {"filename": "doc.pdf", "content": b64(pdf)},
        "recherche": ANCHOR,
    })
    assert r.status_code == 200, r.text
    return r.json()


def signature_fields(pdf: bytes):
    """Champs de signature du PDF : (nom, dictionnaire /V)."""
    fields = pypdf.PdfReader(io.BytesIO(pdf)).get_fields() or {}
    return [(n, f["/V"]) for n, f in fields.items() if f.get("/FT") == "/Sig" and "/V" in f]


def pixels_changed(before: bytes, after: bytes, page_index: int, rect: pymupdf.Rect) -> float:
    """Part de pixels qui diffèrent dans `rect` entre les deux rendus de la page."""
    clip = pymupdf.Rect(rect)
    def render(data):
        doc = pymupdf.open(stream=data, filetype="pdf")
        pix = doc[page_index].get_pixmap(clip=clip, dpi=72)
        return pix.samples, pix.n
    a, n = render(before)
    b, _ = render(after)
    diff = sum(1 for i in range(0, len(a), n) if a[i:i + n] != b[i:i + n])
    return diff / (len(a) // n)


def test_ancre_trouvee(client, headers):
    info = locate_anchor(client, headers, make_pdf())
    assert info["nombre_de_pages"] == 2
    assert info["signature_page"] == ANCHOR_PAGE
    assert 70 <= float(info["signature_coords"]["x1"]) <= 74


def test_ancre_absente(client, headers):
    pdf = make_pdf(anchor="Autre texte")
    info = locate_anchor(client, headers, pdf)
    assert info["signature_page"] == -1


def test_signature_et_griffe_sur_ancre(client, headers, sign_env):
    """Pose la signature électronique + la griffe à l'emplacement de l'ancre."""
    pdf = make_pdf()
    info = locate_anchor(client, headers, pdf)
    x1, y1 = float(info["signature_coords"]["x1"]), float(info["signature_coords"]["y1"])

    # Boîte de signature (repère PDF, origine en bas à gauche) placée juste sous l'ancre
    box = (int(x1), int(PAGE_H - y1 - 120), int(x1) + 200, int(PAGE_H - y1 - 20))
    r = client.post("/sign-basePDF64", headers=headers, json={
        "page": info["signature_page"], "ocrlayer": False, "protect": False,
        "signature_box": ", ".join(map(str, box)),
        "filedef1": {"filename": "doc.pdf", "content": b64(pdf)},
    })
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    signed = r.content

    # 1. signature électronique présente (champ /Sig avec ByteRange et CMS)
    sigs = signature_fields(signed)
    assert len(sigs) == 1
    value = sigs[0][1]
    assert len(value["/ByteRange"]) == 4
    assert len(value["/Contents"]) > 0

    # 2. le document d'origine est conservé (mise à jour incrémentale)
    assert signed.startswith(pdf)

    # 3. le widget est sur la bonne page, dans la boîte demandée
    reader = pypdf.PdfReader(io.BytesIO(signed))
    widgets = [a.get_object() for a in reader.pages[ANCHOR_PAGE - 1].get("/Annots", [])
               if a.get_object().get("/FT") == "/Sig"]
    assert len(widgets) == 1
    assert [round(float(v)) for v in widgets[0]["/Rect"]] == list(box)

    # 4. la griffe est visible : la zone de la boîte change au rendu
    rect = pymupdf.Rect(box[0], PAGE_H - box[3], box[2], PAGE_H - box[1])
    assert pixels_changed(pdf, signed, ANCHOR_PAGE - 1, rect) > 0.2


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
    rect = pymupdf.Rect(box[0], PAGE_H - box[3], box[2], PAGE_H - box[1])
    assert pixels_changed(pdf, signed, 0, rect) > 0.01


def test_refus_sans_cle_api(client):
    r = client.post("/sign-basePDF64", headers={"api-key": "mauvaise"}, json={})
    assert r.status_code in (403, 422)
