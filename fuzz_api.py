#!/usr/bin/env python3
"""Moteur de Fuzzing pour l'API SignPublik.

Teste la robustesse de l'API face à :
1. Fichiers PDF aléatoires et corrompus (bit flips, troncatures, en-têtes invalides)
2. Valeurs extrêmes / aberrantes de signature_box (NaN, débordements, négatifs, tuples mal formés)
3. Chaînes Base64 malformées (caractères invalides, null bytes, padding corrompu)
4. Signer names extrêmes (Unicode rare, RTL, injections, chaînes gigantesques)
5. Entrées textuelles ReDoS et chaînes corrompues sur l'extraction RIB
"""

import base64
import os
import random
import shutil
import string
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from app.config import API_KEY
from app.hello_test import app
import app.core.signature as sig
import app.core.ImageUtils as imgutils
import app.hello_test as api

FIXTURES = ROOT_DIR / "tests" / "fixtures"

# Initialisation environnement
dossier_tmp = ROOT_DIR / "signature_files"
dossier_tmp.mkdir(parents=True, exist_ok=True)
if (FIXTURES / "signature_signe_noBG.png").exists():
    shutil.copy(FIXTURES / "signature_signe_noBG.png", dossier_tmp)
api.SIGN_PATH = str(dossier_tmp)
sig.SIGN_PATH = str(dossier_tmp)
imgutils.SIGN_PATH = str(dossier_tmp)
sig.DEFAULT_CERT_FILE = str(FIXTURES / "cert.pem")
sig.DEFAULT_KEY_FILE = str(FIXTURES / "private_key.pem")

# Désactiver TSA externe
real_sign = sig.pdf.cms.sign
def sign_sans_tsa(data, udct, *args, **kwargs):
    udct = {k: v for k, v in udct.items() if not k.startswith("timestamp")}
    return real_sign(data, udct, *args, **kwargs)
sig.pdf.cms.sign = sign_sans_tsa


client = TestClient(app, raise_server_exceptions=False)
headers = {"api-key": API_KEY}

# Générateurs de données de fuzzing
SAMPLE_PDF = (FIXTURES / "fichier_demande-testeur-avelin.pdf").read_bytes()

def corrompre_octets(data: bytes, taux_mutation: float = 0.05) -> bytes:
    """Mute aléatoirement des octets dans un buffer binaire."""
    ba = bytearray(data)
    nb_mutations = max(1, int(len(ba) * taux_mutation))
    for _ in range(nb_mutations):
        idx = random.randint(0, len(ba) - 1)
        action = random.choice(["flip", "zero", "random", "delete"])
        if action == "flip":
            ba[idx] ^= random.randint(1, 255)
        elif action == "zero":
            ba[idx] = 0
        elif action == "random":
            ba[idx] = random.randint(0, 255)
        elif action == "delete" and len(ba) > 10:
            del ba[idx]
    return bytes(ba)

def generer_pdf_fuzz():
    """Génère un PDF corrompu ou aléatoire."""
    choix = random.choice([
        "corrupted_sample",
        "truncated_sample",
        "random_bytes",
        "empty",
        "fake_header_only",
        "header_with_garbage",
        "huge_header"
    ])
    if choix == "corrupted_sample":
        return corrompre_octets(SAMPLE_PDF, taux_mutation=random.uniform(0.01, 0.3))
    elif choix == "truncated_sample":
        cut = random.randint(1, len(SAMPLE_PDF) - 1)
        return SAMPLE_PDF[:cut]
    elif choix == "random_bytes":
        return os.urandom(random.randint(1, 4096))
    elif choix == "empty":
        return b""
    elif choix == "fake_header_only":
        return b"%PDF-1.4\n%%EOF"
    elif choix == "header_with_garbage":
        return b"%PDF-1.7\n" + os.urandom(500)
    elif choix == "huge_header":
        return b"%PDF-" + b"9" * 1000 + b"\n"

def generer_b64_fuzz():
    """Génère du base64 malformé ou valide-corrompu."""
    choix = random.choice(["valid_corrupted_pdf", "raw_garbage", "bad_padding", "null_bytes", "special_chars"])
    if choix == "valid_corrupted_pdf":
        return base64.b64encode(generer_pdf_fuzz()).decode("utf-8")
    elif choix == "raw_garbage":
        chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?/~`"
        return "".join(random.choices(chars, k=random.randint(0, 200)))
    elif choix == "bad_padding":
        return "SGVsbG8gV29ybGQ="[:-1]  # Padding invalide
    elif choix == "null_bytes":
        return "AAAA\x00BBBB\x00CCCC"
    elif choix == "special_chars":
        return "===///+++" + "\n\r\t" * 10

def generer_box_fuzz():
    """Génère des boîtes de signature atypiques."""
    choix = random.choice([
        "negative",
        "inverted",
        "non_numeric",
        "wrong_count",
        "huge_numbers",
        "zeros",
        "mixed_types",
        "sql_injection",
        "empty"
    ])
    if choix == "negative":
        return f"{random.randint(-1000, -1)}, {random.randint(-1000, -1)}, {random.randint(-500, -1)}, {random.randint(-500, -1)}"
    elif choix == "inverted":
        return "500, 500, 100, 100"
    elif choix == "non_numeric":
        return random.choice(["abc, def, ghi, jkl", "NaN, Infinity, -Infinity, None", "10, twenty, 30, forty"])
    elif choix == "wrong_count":
        return random.choice(["100", "100, 200", "100, 200, 300", "1, 2, 3, 4, 5, 6, 7"])
    elif choix == "huge_numbers":
        return f"{10**18}, {10**18}, {10**19}, {10**19}"
    elif choix == "zeros":
        return "0, 0, 0, 0"
    elif choix == "mixed_types":
        return "100.5, 200.7, 300.2, 400.9"
    elif choix == "sql_injection":
        return "100, 200, 300, 400; DROP TABLE users;--"
    elif choix == "empty":
        return ""

def generer_texte_fuzz():
    """Génère des chaînes de texte extrêmes (signataire, ancre, email)."""
    choix = random.choice([
        "very_long",
        "unicode_accents",
        "emoji_math",
        "rtl_arabic",
        "control_chars",
        "shell_chars",
        "empty",
        "spaces_only"
    ])
    if choix == "very_long":
        return "A" * random.randint(500, 5000)
    elif choix == "unicode_accents":
        return "Éléonore-François Müller-Côté ñçøåîü"
    elif choix == "emoji_math":
        return "Jean 🖋️ ✨ 👨‍💼 ∑(x) = ∫ y dt 🚀"
    elif choix == "rtl_arabic":
        return "مرحبا بالعالم - שלום עולם"
    elif choix == "control_chars":
        return "Jean\x00Dupont\r\n\t\x1b[31mRed\x1b[0m"
    elif choix == "shell_chars":
        return "Jean; $(rm -rf /) && echo 'test'"
    elif choix == "empty":
        return ""
    elif choix == "spaces_only":
        return "      "


def fuzzer_endpoint_getinfo(nb_iterations=100):
    print(f"\n[1/4] Fuzzing de /getInfo-PDF ({nb_iterations} requêtes)...")
    stats = defaultdict(int)
    anomalies = []

    for i in range(nb_iterations):
        payload = {
            "fichier": {
                "filename": f"fuzz_{i}.pdf",
                "content": generer_b64_fuzz()
            },
            "recherche": generer_texte_fuzz()
        }
        try:
            r = client.post("/getInfo-PDF", json=payload, headers=headers, timeout=5)
            stats[r.status_code] += 1
            if r.status_code == 500:
                anomalies.append(f"HTTP 500 sur /getInfo-PDF (itér {i}): {r.text[:200]}")
        except Exception as e:
            stats["CRASH"] += 1
            anomalies.append(f"Crash / Exception non gérée: {e}")

    return stats, anomalies


def fuzzer_endpoint_sign_name(nb_iterations=100):
    print(f"\n[2/4] Fuzzing de /sign-simple-name ({nb_iterations} requêtes)...")
    stats = defaultdict(int)
    anomalies = []

    for i in range(nb_iterations):
        payload = {
            "page": random.choice([-5, 0, 1, 2, 9999, "abc", None]),
            "signername": generer_texte_fuzz(),
            "signermail": random.choice([generer_texte_fuzz(), "jean@ac-corse.fr", "invalid-mail", ""]),
            "signature_box": generer_box_fuzz(),
            "filedef1": {
                "filename": f"fuzz_sign_{i}.pdf",
                "content": generer_b64_fuzz()
            }
        }
        try:
            r = client.post("/sign-simple-name", json=payload, headers=headers, timeout=5)
            stats[r.status_code] += 1
            if r.status_code == 500:
                anomalies.append(f"HTTP 500 sur /sign-simple-name (box='{payload['signature_box'][:30]}', nom='{payload['signername'][:20]}'): {r.text[:200]}")
        except Exception as e:
            stats["CRASH"] += 1
            anomalies.append(f"Crash / Exception non gérée: {e}")

    return stats, anomalies


def fuzzer_endpoint_read_rib(nb_iterations=100):
    print(f"\n[3/4] Fuzzing de /read-rib ({nb_iterations} requêtes)...")
    stats = defaultdict(int)
    anomalies = []

    for i in range(nb_iterations):
        payload = {
            "fichier": {
                "filename": f"rib_fuzz_{i}.pdf",
                "content": generer_b64_fuzz()
            }
        }
        try:
            r = client.post("/read-rib", json=payload, headers=headers, timeout=5)
            stats[r.status_code] += 1
            if r.status_code == 500:
                anomalies.append(f"HTTP 500 sur /read-rib: {r.text[:200]}")
        except Exception as e:
            stats["CRASH"] += 1
            anomalies.append(f"Crash / Exception: {e}")

    return stats, anomalies


def fuzzer_endpoint_image_size(nb_iterations=100):
    print(f"\n[4/4] Fuzzing de /image-size/ ({nb_iterations} requêtes)...")
    stats = defaultdict(int)
    anomalies = []

    for i in range(nb_iterations):
        payload = {
            "image": {
                "filename": f"img_fuzz_{i}.png",
                "content": generer_b64_fuzz()
            },
            "store": random.choice([True, False, None])
        }
        try:
            r = client.post("/image-size/", json=payload, headers=headers, timeout=5)
            stats[r.status_code] += 1
            if r.status_code == 500:
                anomalies.append(f"HTTP 500 sur /image-size/: {r.text[:200]}")
        except Exception as e:
            stats["CRASH"] += 1
            anomalies.append(f"Crash / Exception: {e}")

    return stats, anomalies


def main():
    print("=" * 70)
    print("        LANCEMENT DE LA SESSION DE FUZZING SUR L'API")
    print("=" * 70)
    t0 = time.time()

    all_anomalies = []
    
    # Exécution des campagnes de fuzzing
    for name, fuzzer in [
        ("/getInfo-PDF", fuzzer_endpoint_getinfo),
        ("/sign-simple-name", fuzzer_endpoint_sign_name),
        ("/read-rib", fuzzer_endpoint_read_rib),
        ("/image-size/", fuzzer_endpoint_image_size)
    ]:
        stats, anomalies = fuzzer(nb_iterations=75)
        print(f"  Résultats {name} :")
        for code, count in sorted(stats.items(), key=lambda x: str(x[0])):
            label = "OK" if code == 200 else ("Validation Error" if code == 422 else ("Bad Request" if code == 400 else "ANOMALIE (500/Crash)"))
            print(f"    - HTTP {code} ({label}) : {count}")
        all_anomalies.extend(anomalies)

    duree = time.time() - t0
    print("\n" + "=" * 70)
    print(f"                 BILAN DU FUZZING (Durée : {duree:.2f}s)")
    print("=" * 70)
    print(f"Total requêtes envoyées : 300 requêtes mutées")
    
    if all_anomalies:
        print(f"⚠️  {len(all_anomalies)} ANOMALIE(S) / ERREUR(S) 500 DÉTECTÉE(S) :")
        for i, a in enumerate(all_anomalies[:10], 1):
            print(f"  {i}. {a}")
        if len(all_anomalies) > 10:
            print(f"  ... et {len(all_anomalies) - 10} autre(s)")
    else:
        print("✅ AUCUN CRASH NI ERREUR 500 DÉTECTÉE !")
        print("   Toutes les entrées invalides ont été correctement gérées (400 ou 422).")
    print("=" * 70)

if __name__ == "__main__":
    main()
