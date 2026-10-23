# Service de Signature Électronique Colibris (signColibris)

API FastAPI pour la signature électronique de documents PDF, la détection de zone de signature, la conversion de documents DOCX et la passerelle GED avec OMOGEN / RUDA.

---

## Fonctionnalités

- **Signature électronique conforme PAdES** : signature cryptographique CMS / X.509 via `endesive` avec horodatage RFC 3161 (TSA).
- **Génération dynamique de signature visuelle** : création d'une image de signature manuscrite horodatée (avec PIL).
- **Conversion automatique DOCX -> PDF** : conversion via LibreOffice en mode *headless*.
- **Détection automatique de zone de signature** : recherche par mot-clé avec PyMuPDF pour situer la page et les coordonnées exactes.
- **Extraction bancaire (RIB / IBAN)** : extraction du texte PDF et décomposition des IBAN/BIC français.
- **Intégration OMOGEN / RUDA** : téléversement automatique des arrêtés et documents RH vers la GED ministérielle rattachée au NUMEN.

---

## Installation

### Prérequis

* Python 3.10+
* LibreOffice (pour la conversion DOCX en PDF) :
  * Linux : `sudo apt-get install libreoffice` ou `sudo dnf install libreoffice`
  * macOS : LibreOffice dans `/Applications/`
  * Windows : LibreOffice dans le `PATH`

### Installation des dépendances

```bash
python -m venv venv
source venv/bin/activate  # Sous Windows : venv\Scripts\activate
pip install -r requirements.txt
```

---

## Configuration

Copiez le fichier `.env.example` en `.env` et ajustez les paramètres :

```bash
cp .env.example .env
```

Variables disponibles :

| Variable | Description |
|---|---|
| `API_KEY` | Clé d'API passée dans l'en-tête HTTP `api-key` |
| `SHARED_SECRET` | Secret partagé optionnel |
| `OMOGEN_SECRET_KEY` | Clé d'authentification pour l'API GED OMOGEN |
| `SIGN_PATH` | Répertoire de stockage des signatures (défaut : `./signature_files/`) |
| `CERT_PATH` | Répertoire des certificats SSL / X.509 (défaut : `./ssl/`) |

> **Sécurité** : Les certificats `.pem`, clés privées, documents PDF et images de signatures personnelles sont ignorés par Git et ne doivent jamais être poussés sur un dépôt public.

---

## Démarrage

### En développement local

```bash
uvicorn app.hello_test:app --host 0.0.0.0 --port 8000 --reload
```

Accès à la documentation interactive Swagger : `http://localhost:8000/docs`.

### En production (Systemd + Apache Reverse Proxy)

Voir la configuration de service systemd :

```ini
[Unit]
Description=FastAPI signColibris
After=network.target

[Service]
User=apache
WorkingDirectory=/opt/flask
ExecStart=/opt/flask/env/bin/uvicorn app.hello_test:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Endpoints principaux

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/sign-simple-name` | Génère une signature manuscrite au nom du signataire et signe le PDF |
| `POST` | `/sign-basePDF64` | Signe un PDF (ou DOCX converti) encodé en base64 |
| `POST` | `/getInfo-PDF` | Renvoie le nombre de pages et les coordonnées de la signature par recherche textuelle |
| `POST` | `/read-rib` | Extrait et valide les IBAN / BIC d'un justificatif bancaire PDF |
| `POST` | `/send-ruda-pdf-arrete` | Transfère un arrêté signé vers la GED OMOGEN |
| `POST` | `/send-ruda` | Transfère une demande de télétravail vers OMOGEN |
| `DELETE`| `/delete-ruda/{uuid}` | Supprime/purge un document de la GED RUDA |

## Signer un PDF en ligne de commande

`scripts/signer_pdf.py` signe un PDF (ou DOCX) sous un texte d'ancrage, avec une griffe manuscrite
générée à partir d'un nom. Il utilise uniquement les API du service (`/getInfo-PDF` puis `/sign-simple-name`).

```bash
export API_KEY=...                      # clé API du service
python scripts/signer_pdf.py contrat.pdf --nom "Michel Dupont" --ancre "Assistant"
# -> signed_contrat.pdf
```

Options : `--url` (ou `$SIGNPUBLIK_URL`, défaut `http://localhost:8000`), `--sortie`, `--mail` (utilise le
certificat de ce signataire s'il existe sur le serveur), `--largeur`/`--hauteur`/`--marge` de la zone de
signature en points. Si la place manque sous l'ancre, la signature est posée au-dessus.
