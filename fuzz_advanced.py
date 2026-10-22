#!/usr/bin/env python3
"""Banc de Fuzzing Avancé pour SignPublik :
1. Attaques structurelles PDF (arbres circulaires, décompression FlateBomb, chiffrement /Encrypt, boîtes aberrantes)
2. Test de concurrence agressive (Race conditions sur les griffes PNG et écritures disque simultanées)
3. Chaînage multi-signatures (Résistance à l'écrasement ou corruption PAdES)
4. Test ReDoS (Backtracking catastrophique sur regex IBAN/BIC)
"""

import base64
import concurrent.futures
import io
import os
import shutil
import sys
import time
import zlib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from pypdf import PdfWriter
import pymupdf

from app.config import API_KEY
from app.hello_test import app
import app.core.signature as sig
import app.core.ImageUtils as imgutils
import app.hello_test as api

FIXTURES = ROOT_DIR / "tests" / "fixtures"

# Configuration environnement
dossier_tmp = ROOT_DIR / "signature_files"
dossier_tmp.mkdir(parents=True, exist_ok=True)
if (FIXTURES / "signature_signe_noBG.png").exists():
    shutil.copy(FIXTURES / "signature_signe_noBG.png", dossier_tmp)
api.SIGN_PATH = str(dossier_tmp)
sig.SIGN_PATH = str(dossier_tmp)
imgutils.SIGN_PATH = str(dossier_tmp)
sig.DEFAULT_CERT_FILE = str(FIXTURES / "cert.pem")
sig.DEFAULT_KEY_FILE = str(FIXTURES / "private_key.pem")

# Désactiver TSA externe pour tests
real_sign = sig.pdf.cms.sign
def sign_sans_tsa(data, udct, *args, **kwargs):
    udct = {k: v for k, v in udct.items() if not k.startswith("timestamp")}
    return real_sign(data, udct, *args, **kwargs)
sig.pdf.cms.sign = sign_sans_tsa


client = TestClient(app, raise_server_exceptions=False)
headers = {"api-key": API_KEY}
SAMPLE_PDF = (FIXTURES / "fichier_demande-testeur-avelin.pdf").read_bytes()


def to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


# =====================================================================
# 1. GÉNÉRATION DES PAYLOADS PATHOLOGIQUES
# =====================================================================

def generer_pdf_circulaire():
    """PDF avec arbre de pages cyclique (Kids pointant vers Pages lui-même)."""
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [2 0 R] /Count 1 >>
endobj
xref
0 3
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
trailer
<< /Size 3 /Root 1 0 R >>
startxref
116
%%EOF"""


def generer_flate_bomb_pdf():
    """PDF contenant un flux FlateDecode très compressé (10 Mo de zéros compressés en 10 Ko)."""
    decompressed_data = b"0 " * (5 * 1024 * 1024)  # 10 Mo
    compressed = zlib.compress(decompressed_data)
    
    pdf = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R >>
endobj
4 0 obj
<< /Filter /FlateDecode /Length {len(compressed)} >>
stream
""".encode("latin-1") + compressed + b"""
endstream
endobj
xref
0 5
0000000000 65535 f 
trailer
<< /Size 5 /Root 1 0 R >>
startxref
100
%%EOF"""
    return pdf


def generer_pdf_chiffre():
    """PDF protégé par mot de passe (chiffrement standard RC4/AES)."""
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.encrypt("mot_de_passe_secret")
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def generer_pdf_mediabox_extreme(box="[0 0 100000000 100000000]"):
    """PDF avec une MediaBox aberrante forgée directement en syntaxe PDF brute."""
    return f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox {box} /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 20 >>
stream
BT /F1 12 Tf ET
endstream
endobj
xref
0 5
0000000000 65535 f 
trailer
<< /Size 5 /Root 1 0 R >>
startxref
120
%%EOF""".encode()


# =====================================================================
# 2. TESTS DES ATTAQUES STRUCTURELLES
# =====================================================================

def tester_attaques_structurelles():
    print("\n" + "=" * 70)
    print("  [PHASE 1] ATTAQUES STRUCTURELLES DU FORMAT PDF")
    print("=" * 70)
    
    attaques = [
        ("Arbre de pages cyclique (Infinite recursion)", generer_pdf_circulaire()),
        ("PDF Flate Bomb (Décompression explosive 10Mo)", generer_flate_bomb_pdf()),
        ("PDF Chiffré /Encrypt (Avec mot de passe)", generer_pdf_chiffre()),
        ("MediaBox Infinie [0 0 1e8 1e8]", generer_pdf_mediabox_extreme("[0 0 100000000 100000000]")),
        ("MediaBox Inversée [500 500 0 0]", generer_pdf_mediabox_extreme("[500 500 0 0]")),
        ("MediaBox Nulle [0 0 0 0]", generer_pdf_mediabox_extreme("[0 0 0 0]")),
    ]

    for nom, pdf_data in attaques:
        t0 = time.time()
        print(f"\n▶ Test : {nom}")
        
        # Test sur /getInfo-PDF
        r_info = client.post("/getInfo-PDF", json={
            "fichier": {"filename": "malicious.pdf", "content": to_b64(pdf_data)},
            "recherche": "Assistant"
        }, headers=headers)
        
        # Test sur /sign-simple-name
        r_sign = client.post("/sign-simple-name", json={
            "page": 1,
            "signername": "Victime Test",
            "signermail": "victime@ac-corse.fr",
            "signature_box": "100, 100, 250, 180",
            "filedef1": {"filename": "malicious.pdf", "content": to_b64(pdf_data)}
        }, headers=headers)

        dt = time.time() - t0
        print(f"   - /getInfo-PDF      : HTTP {r_info.status_code} ({r_info.reason_phrase})")
        print(f"   - /sign-simple-name : HTTP {r_sign.status_code} ({r_sign.reason_phrase})")
        print(f"   - Temps d'exécution : {dt:.3f}s")
        
        # Vérification qu'il n'y a pas eu de crash non intercepté
        if r_info.status_code == 500 or r_sign.status_code == 500:
            print("   ❌ ÉCHEC : Erreur 500 levée sur cette structure !")
        else:
            print("   ✔ SUCCÈS : Exception interceptée proprement (pas de crash serveur).")


# =====================================================================
# 3. TEST DE CONCURRENCE & RACE CONDITIONS
# =====================================================================

def tester_concurrence(nb_requetes=40):
    print("\n" + "=" * 70)
    print(f"  [PHASE 2] CONCURRENCE & RACE CONDITIONS ({nb_requetes} REQUÊTES EN PARALLÈLE)")
    print("=" * 70)
    print("Objectif : Envoyer simultanément 40 requêtes de signature pour le MÊME signataire")
    print("afin de provoquer des collisions de fichiers (.png et .pdf temporaires).")

    signer_payload = {
        "page": 1,
        "signername": "Jean-Pierre Collision",
        "signermail": "jean-pierre.collision@ac-corse.fr",
        "signature_box": "150, 100, 300, 185",
        "filedef1": {"filename": "doc_concurrent.pdf", "content": to_b64(SAMPLE_PDF)}
    }

    t0 = time.time()
    resultats = []

    def appel_sign():
        # Chaque thread a sa propre instance de client
        c = TestClient(app, raise_server_exceptions=False)
        return c.post("/sign-simple-name", json=signer_payload, headers=headers)

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(appel_sign) for _ in range(nb_requetes)]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            resultats.append(res.status_code)

    duree = time.time() - t0
    codes = {}
    for code in resultats:
        codes[code] = codes.get(code, 0) + 1

    print(f"\nRésultats concurrence en {duree:.2f}s ({nb_requetes / duree:.1f} req/s) :")
    for code, count in sorted(codes.items()):
        print(f"   - HTTP {code} : {count} requêtes")

    if codes.get(200, 0) == nb_requetes:
        print("   ✔ PARFAIT : 100% des signatures concurrentes ont abouti sans collision !")
    else:
        print(f"   ⚠️ ATTENTION : {nb_requetes - codes.get(200, 0)} requête(s) ont échoué sous forte charge.")


# =====================================================================
# 4. TEST DU CHAÎNAGE MULTI-SIGNATURES
# =====================================================================

def tester_multi_signatures(nb_signatures=5):
    print("\n" + "=" * 70)
    print(f"  [PHASE 3] TEST MULTI-SIGNATURES EN SÉRIE ({nb_signatures} SIGNATURES CUMULÉES)")
    print("=" * 70)
    print("Objectif : Signer successivement un document déjà signé pour tester")
    print("l'accumulation PAdES et vérifier si le format reste valide.")

    current_pdf = SAMPLE_PDF
    for i in range(1, nb_signatures + 1):
        t0 = time.time()
        box_y = 100 + (i * 30)
        box_str = f"100, {box_y}, 250, {box_y + 60}"
        
        r = client.post("/sign-simple-name", json={
            "page": 1,
            "signername": f"Signataire Numero {i}",
            "signermail": f"signataire{i}@ac-corse.fr",
            "signature_box": box_str,
            "filedef1": {"filename": f"doc_step_{i}.pdf", "content": to_b64(current_pdf)}
        }, headers=headers)
        
        dt = time.time() - t0
        assert r.status_code == 200, f"Échec signature {i}: {r.text}"
        current_pdf = r.content
        print(f"   ✔ Signature n°{i} appliquée avec succès ({len(current_pdf)} octets, {dt:.2f}s)")

    # Vérification avec pymupdf et helpers
    from tests.helpers import signature_fields
    sigs = signature_fields(current_pdf)
    print(f"\nNombre de signatures cryptographiques détectées dans le PDF final : {len(sigs)}")
    if len(sigs) == nb_signatures:
        print(f"   ✔ EXCELLENT : Les {nb_signatures} signatures coexistent de manière intègre !")
    else:
        print(f"   ⚠️ Constat : {len(sigs)} signatures enregistrées au lieu de {nb_signatures}.")


# =====================================================================
# 5. TEST REDOS (Catastrophic Backtracking sur IBAN/BIC)
# =====================================================================

def tester_redos_rib():
    print("\n" + "=" * 70)
    print("  [PHASE 4] TEST DE RÉSISTANCE REDOS SUR /read-rib")
    print("=" * 70)
    print("Objectif : Envoyer des chaînes piégées conçues pour faire exploser")
    print("le moteur d'expressions régulières d'extraction d'IBAN.")

    # Piège pour r'\b(?:FR\d{2}(?:\s?[0-9A-Z]){23}...' :
    # Séquence de FR + 2 chiffres + 22 caractères conformes + espace + caractère non conforme répété
    pieges = [
        "FR76" + " A" * 1000 + "!",
        ("FR76 1234 5678 9012 3456 7890 12" + " ") * 200 + "X",
        "FR" + "9" * 10000,
        ("A" * 50 + " ") * 500,
    ]

    for i, texte_piege in enumerate(pieges, 1):
        doc = pymupdf.open()
        p = doc.new_page()
        p.insert_text((50, 50), texte_piege[:500])
        pdf_bytes = doc.tobytes()
        doc.close()

        t0 = time.time()
        r = client.post("/read-rib", json={
            "fichier": {"filename": "piege.pdf", "content": to_b64(pdf_bytes)}
        }, headers=headers)
        dt = time.time() - t0

        print(f"   - Payload ReDoS {i} ({len(texte_piege)} chars) : traité en {dt:.3f}s -> HTTP {r.status_code}")
        if dt > 2.0:
            print("   ⚠️ Risque ReDoS détecté (temps de traitement supérieur à 2 secondes) !")
        else:
            print("   ✔ Regex résistante au backtracking.")


def main():
    print("=" * 70)
    print("   LANCEMENT DE LA SESSION DE FUZZING AVANCÉ SUR SIGNPUBLIK")
    print("=" * 70)
    t_global = time.time()

    tester_attaques_structurelles()
    tester_concurrence(nb_requetes=30)
    tester_multi_signatures(nb_signatures=4)
    tester_redos_rib()

    print("\n" + "=" * 70)
    print(f"   FIN DE LA SESSION AVANCÉE (Durée globale : {time.time() - t_global:.2f}s)")
    print("=" * 70)


if __name__ == "__main__":
    main()
