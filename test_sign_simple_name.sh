#!/usr/bin/env bash
# ==============================================================================
# Script de test bash pour /sign-simple-name
# Envoie un PDF encodé en base64 à l'API et récupère le PDF signé sous un autre nom.
# ==============================================================================

set -euo pipefail

# Paramètres configurables (avec valeurs par défaut)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT_PDF="${1:-"${SCRIPT_DIR}/tests/fixtures/fichier_demande-testeur-avelin.pdf"}"
OUTPUT_PDF="${2:-"${SCRIPT_DIR}/pdf_signes/resultat_signe_bash.pdf"}"
SIGNER_NAME="${3:-"Jean-Guy Avelin"}"
SIGNER_MAIL="${4:-"jean-guy.avelin@ac-corse.fr"}"
SIGNATURE_BOX="${5:-"150, 100, 300, 185"}"
PAGE_NUM="${6:-1}"
API_URL="${API_URL:-"http://localhost:8000"}"

# Lecture de la clé d'API depuis le .env si présent, sinon valeur par défaut de dev
if [ -f "${SCRIPT_DIR}/.env" ]; then
    API_KEY="${API_KEY:-$(grep -E '^API_KEY=' "${SCRIPT_DIR}/.env" | cut -d '=' -f2- | tr -d '"\r\n')}"
fi
API_KEY="${API_KEY:-"DEV_DEFAULT_API_KEY"}"

echo "======================================================================"
echo "          TEST BASH : SIGNATURE PDF VIA /sign-simple-name"
echo "======================================================================"
echo "📄 Fichier d'entrée  : ${INPUT_PDF}"
echo "💾 Fichier de sortie : ${OUTPUT_PDF}"
echo "✍️  Signataire        : ${SIGNER_NAME} (${SIGNER_MAIL})"
echo "📍 Emplacement boîte : ${SIGNATURE_BOX} (page ${PAGE_NUM})"
echo "🌐 URL de l'API      : ${API_URL}/sign-simple-name"
echo "----------------------------------------------------------------------"

# 1. Vérification de l'existence du fichier d'entrée
if [ ! -f "${INPUT_PDF}" ]; then
    echo "❌ Erreur : le fichier d'entrée '${INPUT_PDF}' n'existe pas." >&2
    exit 1
fi

# 2. Création du dossier de destination si nécessaire
mkdir -p "$(dirname "${OUTPUT_PDF}")"

# 3. Encodage du PDF en Base64 (compatible Linux et macOS)
echo "[1/3] Encodage du document en base64..."
FILENAME="$(basename "${INPUT_PDF}")"
if command -v python3 &>/dev/null; then
    BASE64_CONTENT=$(python3 -c "import base64; print(base64.b64encode(open('${INPUT_PDF}', 'rb').read()).decode('utf-8'))")
else
    BASE64_CONTENT=$(base64 < "${INPUT_PDF}" | tr -d '\r\n')
fi

# 4. Construction de la charge utile JSON temporaire
TMP_JSON=$(mktemp)
trap 'rm -f "${TMP_JSON}"' EXIT

python3 -c "
import json
payload = {
    'page': int('${PAGE_NUM}'),
    'signername': '''${SIGNER_NAME}''',
    'signermail': '''${SIGNER_MAIL}''',
    'signature_box': '''${SIGNATURE_BOX}''',
    'filedef1': {
        'filename': '''${FILENAME}''',
        'content': '''${BASE64_CONTENT}'''
    }
}
with open('${TMP_JSON}', 'w', encoding='utf-8') as f:
    json.dump(payload, f)
"

# 5. Envoi de la requête via curl
echo "[2/3] Appel POST à l'API /sign-simple-name..."
HTTP_STATUS=$(curl -s -w "%{http_code}" -X POST "${API_URL}/sign-simple-name" \
    -H "Content-Type: application/json" \
    -H "api-key: ${API_KEY}" \
    --data-binary @"${TMP_JSON}" \
    -o "${OUTPUT_PDF}")

echo "[3/3] Réponse HTTP : ${HTTP_STATUS}"

# 6. Vérification du résultat
if [ "${HTTP_STATUS}" -eq 200 ]; then
    TAILLE=$(wc -c < "${OUTPUT_PDF}" | tr -d ' ')
    echo "----------------------------------------------------------------------"
    echo "🎉 SUCCÈS : Le document a été signé et enregistré sous un autre nom !"
    echo "   -> Chemin : ${OUTPUT_PDF}"
    echo "   -> Taille : ${TAILLE} octets"
    echo "======================================================================"
    exit 0
else
    echo "----------------------------------------------------------------------"
    echo "❌ ÉCHEC DE LA SIGNATURE (Code HTTP: ${HTTP_STATUS})" >&2
    echo "Détails de l'erreur renvoyés par l'API :" >&2
    if [ -f "${OUTPUT_PDF}" ]; then
        cat "${OUTPUT_PDF}" >&2
        echo "" >&2
        rm -f "${OUTPUT_PDF}"
    fi
    echo "======================================================================"
    exit 1
fi
