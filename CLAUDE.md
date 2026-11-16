## Exploration du code : sous-agent `recherche-fichiers`

- Pour toute recherche qui oblige à parcourir plusieurs fichiers ou dossiers (où une fonction est définie ou utilisée, cartographie d'un module, recherche d'une convention, inventaire de fichiers), utilise l'agent `recherche-fichiers` (Haiku, lecture seule). Ne fais pas ces fouilles toi-même dans la session principale.
- Si plusieurs recherches sont indépendantes, lance plusieurs instances de cet agent en parallèle.
- Ne délègue pas : la lecture d'un fichier déjà identifié, un simple grep, les modifications de code, le débogage et les décisions d'architecture. Fais-les toi-même.
- Avant de modifier un fichier signalé par l'agent, relis-le toi-même. Ne te fie pas au seul résumé.
