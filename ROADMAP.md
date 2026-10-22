# Roadmap SignPublik

Plan de modifications issu de la revue de code et d'architecture. Chaque phase est indépendante et livrable seule. Les cases sont à cocher au fil de l'avancement.

Légende : 🔴 critique · 🟠 important · 🟡 amélioration

---

## Phase 1 — Sécurité et bugs bloquants 🔴

### 1.1 Secrets et authentification
- [ ] Supprimer les valeurs par défaut de `API_KEY`, `SHARED_SECRET`, `OMOGEN_SECRET_KEY` (`app/config.py`) : échec au démarrage si absentes.
- [ ] Comparer la clé API avec `secrets.compare_digest` dans `verify_api_key`.
- [ ] Supprimer `logger.debug(f"header : {api_key}")` (la clé ne doit jamais être loguée).
- [ ] Ajouter `Depends(verify_api_key)` sur `/image-size/` (écrit sur disque avec `store=true`).
- [ ] Décider du sort de `/hello/{name}`, `/helloSP/{name}` et `/upload-and-download-pdf/` : supprimer ou protéger.
- [ ] Ne plus loguer les `numen` ni le contenu des réponses RUDA (données personnelles) ; remplacer les `print()` par `logger`.

### 1.2 Path traversal et fichiers temporaires
- [ ] `storeImage` : n'utiliser que `os.path.basename(filename)` (ou un UUID) avant `os.path.join(SIGN_PATH, ...)`.
- [ ] Même protection pour `TEMP_{filename}` et `slugify(request.signername)` utilisé comme nom de fichier.
- [ ] Remplacer les fichiers `TEMP_*` du répertoire courant par `tempfile.TemporaryDirectory()` (nettoyage garanti, pas de collision entre requêtes concurrentes).
- [ ] Supprimer l'écriture/relecture disque dans `sign_pdf_content` : travailler en `BytesIO`.

### 1.3 Bugs
- [ ] `delete_ruda_uuid`, `send_ruda_teletravail`, `send_ruda_pdf_arrete` : `response` est indéfini dans le `except` (`NameError`). Lever une `HTTPException(502)` avec le détail.
- [ ] Ces mêmes endpoints renvoient `json.dumps(...)` (chaîne) avec un HTTP 200 en cas d'erreur : renvoyer un vrai code d'erreur et un JSON.
- [ ] `sign_pdf_content` :
  - [ ] lever l'exception si le certificat ou la clé est introuvable (aujourd'hui `cert_data` reste indéfini) ;
  - [ ] corriger `logger.error(exc_type, fname, ...)` → `logger.exception(...)` ;
  - [ ] supprimer `logo_path = "logo.png",` (tuple accidentel, inutilisé) ;
  - [ ] remplacer `datetime.utcnow()` (déprécié) par `datetime.now(timezone.utc)`.
- [ ] `sign_pdf_base64_ok` ne transmet pas `mail_signer` : il signe toujours avec le certificat par défaut. Corriger ou documenter.
- [ ] Corriger l'en-tête `Content-Disposition$` (faute de frappe) dans `/upload-and-download-pdf/`.
- [ ] Distinguer 4xx (entrée invalide) et 5xx (échec de signature, LibreOffice) au lieu de tout convertir en 400.

### 1.4 Protection contre les abus
- [ ] Limiter la taille des contenus base64 / des fichiers acceptés.
- [ ] Ajouter `timeout=` à tous les appels `requests` (RUDA, TSA).
- [ ] Ajouter un timeout par défaut à `convert_to` et un profil LibreOffice isolé par appel (`-env:UserInstallation=...`) pour éviter les blocages en concurrence.

---

## Phase 2 — Nettoyage du dépôt 🟠

- [ ] Supprimer le `hello_test.py` de la racine (ancienne version, imports cassés) et vérifier que `conftest.py` / `test_client.py` de la racine ne sont pas des doublons de `tests/`.
- [ ] Supprimer le code mort de `app/hello_test.py` : `upload_pdf` (appelle `sign_pdf` avec des arguments inexistants), `sign_pdf` commentée, bloc `__main__` cassé (`hello_test.app` non importé).
- [ ] Supprimer `envoi_pdf_ruda_AVIRER`, les blocs commentés de `omogen.py` et de `signature.py`, et la mention `# A VIRER` dans `signature.py` (retirer la dépendance à `HTTPException` dans le code métier).
- [ ] Remettre les `import unicodedata, re` en tête de `utilities.py` ; supprimer `nettoyer_chaine_avancee` si inutilisée.
- [ ] Fusionner le fichier `README` (brouillon Apache/systemd) dans `README.md`, ou le supprimer.
- [ ] Choisir une langue (français ou anglais) pour les noms de fonctions, variables et logs.

---

## Phase 3 — Refactoring de l'architecture 🟠

### 3.1 Structure cible
```
app/
  main.py              # création de l'app, inclusion des routers (ex-hello_test.py)
  config.py            # pydantic-settings
  dependencies.py      # verify_api_key, etc.
  routers/
    signature.py       # /sign-simple-name, /sign-basePDF64
    pdf_info.py        # /getInfo-PDF
    ruda.py            # /send-ruda*, /delete-ruda
    rib.py             # /read-rib
    images.py          # /image-size/
  services/
    pdf.py             # décodage base64, DOCX→PDF, parsing box/page, recherche de texte
    signing.py         # signature (ex-core/signature.py)
    ruda.py            # client RUDA (ex-core/omogen.py)
  models/
```
- [ ] Renommer `hello_test.py` en `main.py` et adapter le README, le service systemd et les tests.
- [ ] Les routes se limitent à : valider → appeler un service → formater la réponse.

### 3.2 Déduplication
- [ ] Utiliser `get_pdf_content` partout : la conversion DOCX→PDF est copiée trois fois (`getInfo`, `sign_pdf_base64_ok`, `get_pdf_content`).
- [ ] Factoriser le parsing de `signature_box` et `page` (dupliqué dans les deux routes de signature).
- [ ] Factoriser la gestion de réponse/erreur RUDA (3 routes identiques).
- [ ] Supprimer les modèles/champs inutilisés (`ocrlayer`, `protect`, `protect_password` dans `SignBasePDFRequest`) ou les implémenter.

### 3.3 Concurrence
- [ ] Les handlers `async def` appellent du code bloquant (`requests`, `endesive`, PyMuPDF, LibreOffice). Passer en `def` ou utiliser `run_in_threadpool`.

---

## Phase 4 — Configuration et signature 🟠

- [ ] Remplacer le parseur `.env` maison de `config.py` par `pydantic-settings` (validation, types, erreurs claires).
- [ ] Sortir de la config : URLs RUDA/OMOGEN, `root_path` et `servers` de FastAPI, serveur TSA, `contact` / `location` / `reason` de la signature.
- [ ] Faire lire `SIGN_PATH` et `CERT_PATH` par `constants.py` (documentés dans `.env.example` mais ignorés) ; supprimer le `os.makedirs` à l'import.
- [ ] Repli sur le certificat par défaut : le rendre explicite (paramètre, log d'avertissement) ou le refuser selon la politique voulue.
- [ ] Prévoir des clés protégées par mot de passe et, à terme, un coffre/HSM pour les clés de signature.
- [ ] Gérer l'échec du TSA (retry déjà configuré, mais prévoir un comportement défini en cas d'indisponibilité).
- [ ] Remplacer `cache_with_expiration` (sans borne, clé = image base64 complète) par `cachetools.TTLCache` / `lru_cache`.

---

## Phase 5 — Qualité, tests et déploiement 🟡

- [ ] Ajouter des tests pour : accès non authentifié refusé, path traversal, erreurs RUDA (mock de `requests`), certificat manquant, limite de taille.
- [ ] Brancher une CI (GitHub Actions) : `pytest`, `ruff`, éventuellement `mypy`.
- [ ] Ajouter `ruff` (lint + format) et un `pre-commit`.
- [ ] Figer les dépendances (`pip-tools` / `uv` / lockfile) et vérifier les versions inhabituelles (`httpx2`, `starlette>=1.7`).
- [ ] Ajouter un `pyproject.toml` et un `Dockerfile` (Python + LibreOffice + polices) pour un déploiement reproductible.
- [ ] Logs structurés, niveau INFO sobre, sans donnée personnelle.
- [ ] Ajouter un endpoint `/health` pour la supervision.

---

## Ordre recommandé

1. Phase 1 (sécurité et bugs) : à faire en premier, par petites PR.
2. Phase 2 (nettoyage) : rapide, facilite les phases suivantes.
3. Phase 3 (architecture) : à faire une fois les tests de la phase 1 en place, pour refactorer sans régression.
4. Phases 4 et 5 : en parallèle ou ensuite.
