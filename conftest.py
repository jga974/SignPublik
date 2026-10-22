"""Option de ligne de commande pour conserver les PDF signés produits par les tests."""
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--save-signed", action="store", metavar="DOSSIER", default=None,
        help="enregistre dans DOSSIER les PDF signés produits par les tests (créé au besoin)",
    )


@pytest.fixture
def save_signed(request):
    """Renvoie une fonction save(nom, octets) ; sans --save-signed, elle ne fait rien."""
    dossier = request.config.getoption("--save-signed")

    def save(nom: str, contenu: bytes):
        if not dossier:
            return None
        chemin = Path(dossier).expanduser() / nom
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_bytes(contenu)
        print(f"PDF signé enregistré : {chemin.resolve()}")
        return chemin

    return save


@pytest.fixture(autouse=True)
def disable_rate_limiting_during_tests(monkeypatch):
    """Désactive le rate limiting par défaut pendant les tests unitaires pour éviter les faux positifs."""
    import app.core.rate_limiter as rl
    monkeypatch.setattr(rl, "RATE_LIMIT_ENABLED", False)

