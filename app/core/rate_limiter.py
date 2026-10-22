"""Module de limitation de débit (Rate Limiter) et de protection anti-DoS.

Implémente un algorithme de fenêtre glissante en mémoire (Thread-Safe, zéro dépendance externe)
avec expiration automatique des compteurs.
"""

import os
import threading
import time
from collections import defaultdict
from typing import Tuple

# Configurations globales via variables d'environnement
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("true", "1", "yes")
RATE_LIMIT_GENERAL = int(os.getenv("RATE_LIMIT_GENERAL", "120"))  # req/minute
RATE_LIMIT_HEAVY = int(os.getenv("RATE_LIMIT_HEAVY", "60"))        # req/minute pour signatures/docx
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25")) * 1024 * 1024  # 25 Mo


class SlidingWindowRateLimiter:
    """Limiteur de débit basé sur une fenêtre glissante en mémoire."""

    def __init__(self):
        self._lock = threading.Lock()
        self._requests = defaultdict(list)
        self._last_cleanup = time.time()

    def _cleanup_old_records(self, now: float, window_seconds: float = 60.0):
        """Nettoie périodiquement les anciennes entrées pour éviter les fuites mémoire."""
        if now - self._last_cleanup > 300.0:  # Nettoyage toutes les 5 minutes
            keys_to_delete = []
            for client_id, timestamps in self._requests.items():
                self._requests[client_id] = [t for t in timestamps if now - t < window_seconds]
                if not self._requests[client_id]:
                    keys_to_delete.append(client_id)
            for k in keys_to_delete:
                del self._requests[k]
            self._last_cleanup = now

    def is_allowed(self, client_id: str, limit: int = 60, window_seconds: float = 60.0) -> Tuple[bool, int]:
        """Vérifie si le client est autorisé à faire une requête.

        Returns:
            Tuple[bool, int]: (autorisé ou non, temps d'attente en secondes si bloqué)
        """
        if not RATE_LIMIT_ENABLED:
            return True, 0

        now = time.time()
        with self._lock:
            self._cleanup_old_records(now, window_seconds)
            timestamps = self._requests[client_id]
            # Filtrer les timestamps de la fenêtre actuelle
            recent = [t for t in timestamps if now - t < window_seconds]
            self._requests[client_id] = recent

            if len(recent) >= limit:
                # Calculer le temps restant avant que la plus ancienne requête expire
                oldest = recent[0]
                retry_after = max(1, int(window_seconds - (now - oldest)))
                return False, retry_after

            # Enregistrer la requête courante
            self._requests[client_id].append(now)
            return True, 0


# Instance globale partagée
rate_limiter = SlidingWindowRateLimiter()
