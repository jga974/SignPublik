# Guide des Tests et Scripts d'Automatisation (SignPublik)

Ce document récapitule l'ensemble des scripts de test, des outils de fuzzing et des procédures de validation disponibles dans le projet.

---

## Sommaire

1. [Script Bash de Signature (`test_sign_simple_name.sh`)](#1-script-bash-de-signature-test_sign_simple_namesh)
2. [Script Python d'Enchaînement Ancre $\rightarrow$ Signature (`signer_demande.py`)](#2-script-python-denchaînement-ancre--signature-signer_demandepy)
3. [Banc de Fuzzing Standard (`fuzz_api.py`)](#3-banc-de-fuzzing-standard-fuzz_apipy)
4. [Banc de Fuzzing Avancé & Concurrence (`fuzz_advanced.py`)](#4-banc-de-fuzzing-avancé--concurrence-fuzz_advancedpy)
5. [Suite de Tests Unitaires et Sécurité (`pytest`)](#5-suite-de-tests-unitaires-et-sécurité-pytest)

---

## 1. Script Bash de Signature (`test_sign_simple_name.sh`)

Ce script permet de tester directement l'API HTTP en ligne de commande via `curl`. Il encode le document source en base64, envoie la requête à l'endpoint `/sign-simple-name` et enregistre le PDF signé sous un nom de fichier distinct.

### Emplacement
* Fichier : [`test_sign_simple_name.sh`](test_sign_simple_name.sh)

### Utilisation de base
```bash
./test_sign_simple_name.sh
```
*Par défaut, utilise `tests/fixtures/fichier_demande-testeur-avelin.pdf` et enregistre le résultat dans `pdf_signes/resultat_signe_bash.pdf`.*

### Utilisation avancée avec arguments
```bash
./test_sign_simple_name.sh [FICHIER_ENTREE] [FICHIER_SORTIE] [NOM_SIGNATAIRE] [EMAIL_SIGNATAIRE] [BOITE_SIGNATURE] [NUM_PAGE]
```

**Exemple :**
```bash
./test_sign_simple_name.sh \
  "mon_contrat.pdf" \
  "pdf_signes/contrat_signe_final.pdf" \
  "Jean-Guy Avelin" \
  "jean-guy.avelin@ac-corse.fr" \
  "150, 100, 300, 185" \
  1
```

### Variables d'environnement supportées
* `API_URL` : URL de base de l'API (défaut: `http://localhost:8000`).
* `API_KEY` : Clé d'API passée dans l'en-tête `api-key` (lue automatiquement depuis `.env` ou `DEV_DEFAULT_API_KEY`).

```bash
API_URL="https://projet.ac-corse.fr/api" API_KEY="votre_cle" ./test_sign_simple_name.sh
```

---

## 2. Script Python d'Enchaînement Ancre $\rightarrow$ Signature (`signer_demande.py`)

Ce script Python autonome enchaîne automatiquement les 2 étapes :
1. Recherche d'un mot-clé d'ancrage (ex: `"Assistant"`) via `/getInfo-PDF` et calcul de la zone de signature sous le texte.
2. Génération de la griffe manuscrite horodatée et signature cryptographique X.509 via `/sign-simple-name`.

### Emplacement
* Fichier : [`signer_demande.py`](signer_demande.py)

### Utilisation
```bash
python signer_demande.py
```

### Options en ligne de commande
```bash
python signer_demande.py \
  --pdf "tests/fixtures/fichier_demande-testeur-avelin.pdf" \
  --ancre "Assistant" \
  --nom "Jean-Guy Avelin" \
  --sortie "pdf_signes/demande_avelin_signee.pdf" \
  --largeur 150 \
  --hauteur 85 \
  --marge 15
```

---

## 3. Banc de Fuzzing Standard (`fuzz_api.py`)

Envoie des séries de requêtes mutées pour valider la robustesse de l'API face aux données inattendues ou malformées.

### Emplacement
* Fichier : [`fuzz_api.py`](fuzz_api.py)

### Scénarios testés (300 requêtes)
* **Fichiers binaires altérés** : PDF tronqués, inversions de bits (*bit flips*), octets nuls, en-têtes corrompus.
* **Base64 invalide** : corruption de padding, caractères non autorisés, chaînes nulles.
* **Boîtes de signature extrêmes** : coordonnées négatives, valeurs hors limites ($10^{19}$), non-numériques (`NaN`), tuples incomplets.
* **Signataires extrêmes** : textes Unicode rares, émojis, texte arabe/hébreu (RTL), chaînes $> 5\,000$ caractères.

### Exécution
```bash
python fuzz_api.py
```

---

## 4. Banc de Fuzzing Avancé & Concurrence (`fuzz_advanced.py`)

Simule des attaques de niveau structurel et des conditions de charge extrême.

### Emplacement
* Fichier : [`fuzz_advanced.py`](fuzz_advanced.py)

### Scénarios testés
1. **Attaques structurelles PDF** :
   * Arbre de pages cyclique (*Infinite loop*).
   * PDF Flate Bomb (décompression explosive de 10 Mo).
   * PDF protégés par mot de passe (`/Encrypt`).
   * MediaBox infinies, inversées ou nulles.
2. **Stress-test de concurrence** :
   * Envoi de 40 requêtes simultanées en parallèle pour le même signataire afin de vérifier l'absence de collisions de fichiers (`.png` / `.pdf`).
3. **Multi-signatures PAdES** :
   * Accumulation de 4 signatures successives sur un même document.
4. **Résistance ReDoS** :
   * Chaînes piégées de 2 000 à 25 500 caractères sur les regex d'extraction IBAN/BIC.

### Exécution
```bash
python fuzz_advanced.py
```

---

## 5. Suite de Tests Unitaires et Sécurité (`pytest`)

Le projet dispose d'une suite complète de 121 tests automatisés couvrant les cas nominaux, la conversion Word, l'extraction de RIB, le Rate Limiting et la sécurité anti-traversal.

### Exécution de tous les tests
```bash
pytest tests test_client.py -v
```

### Exécution ciblée des tests de sécurité
```bash
pytest tests/test_security.py -v
```
*Vérifie la protection contre le Path Traversal (`storeImage`, conversion DOCX), la comparaison en temps constant des clés (`secrets.compare_digest`), le rejet des requêtes trop lourdes (HTTP 413) et le Rate Limiting (HTTP 429).*

### Conserver les PDF produits lors des tests
```bash
pytest test_client.py -s --save-signed ./pdf_signes
```
