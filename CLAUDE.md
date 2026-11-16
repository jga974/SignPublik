## Exploration du code : sous-agents Haiku

- Pour toute recherche qui oblige à parcourir plusieurs fichiers ou dossiers (où une fonction est définie ou utilisée, cartographie d'un module, recherche d'une convention, inventaire de fichiers), délègue à un sous-agent avec le modèle Haiku (`model: haiku`, par exemple l'agent `Explore`). Ne fais pas ces fouilles toi-même dans la session principale.
- Si plusieurs recherches sont indépendantes, lance plusieurs sous-agents Haiku en parallèle.
- Dans la consigne au sous-agent, demande : lecture seule, résultats sous forme de chemins + numéros de ligne + extraits courts (pas de fichiers entiers), et une conclusion en quelques lignes.
- Ne délègue pas : la lecture d'un fichier déjà identifié, un simple grep, les modifications de code, le débogage et les décisions d'architecture. Fais-les toi-même.
- Avant de modifier un fichier signalé par un sous-agent, relis-le toi-même. Ne te fie pas au seul résumé.
