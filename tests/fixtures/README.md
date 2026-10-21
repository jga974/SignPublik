# Fichiers d'exemple pour les tests

| Fichier | Usage |
|---|---|
| `fichier_demande-testeur-avelin.pdf` | PDF de 2 pages, texte « Assistant » en page 2 (ancre de la griffe) |
| `rib.pdf` | RIB fictif (IBAN `FR76 3000 3004 1700 0560 7498 316`, BIC `SOGEFRPP`) |
| `signature_signe_noBG.png` | Griffe de 113×85 px, fond transparent |
| `cert.pem`, `private_key.pem` | Certificat auto-signé et clé **de test uniquement** |

Tout est fictif. **La clé privée est publique** : elle ne doit jamais servir à signer un vrai document
ni être copiée à la racine du projet ou sur un serveur. Les vrais `cert.pem` / `private_key.pem`
restent ignorés par git (voir `.gitignore`).
