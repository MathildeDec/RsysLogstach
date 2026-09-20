# PATTERNS.md — Conventions et patterns

## Traçabilité systématique des fonctions

**Règle :** Toute fonction du code applicatif (`src/`, hors `tests/`) doit être tracée à l'entrée ET à la sortie (retour normal ou exception).

**Implémentation :** Décorateur `@traced` (`tracing.py`), plutôt que duplication manuelle. Le décorateur enveloppe l'appel entier — il ne peut structurellement pas rater un chemin de sortie, contrairement à une convention appliquée à la main.

**Contenu des logs :** Uniquement le `__qualname__` — jamais les arguments ni la valeur de retour (`credentials.py` manipule des secrets). Une fonction qui a besoin de journaliser un détail précis et non sensible le fait via son propre `logger.debug()` additionnel.

**Compatibilité :** `functools.wraps` préserve `__name__`/`__doc__`/`__wrapped__` — compatible avec `inspect.signature` et les méthodes GObject/GTK4.

## Absence de dépendances circulaires entre modules

**Règle :** Le graphe de dépendances entre modules de `src/` doit rester acyclique.

**Vérification :** `tests/test_no_cross_imports.py` analyse les imports via `ast` (pas de simple relecture) et vérifie mécaniquement l'absence de cycles.

**Exemples de décisions prises pour respecter cette règle :**
- `tracing` est intentionnellement sans AUCUNE dépendance interne — c'est le seul moyen pour que tous les autres modules puissent l'importer sans cycle.
- `util.add_failure_tags` a été déplacée depuis `interpreter.py` (session 24) vers `util.py` pour être partagée avec `filters.py::GeoipFilter` sans créer de dépendance `filters → interpreter` (interdite : `interpreter` dépend déjà de `filters`).
- `_build_geoip_record` (session 21) est dans `enrichment.py`, consommé par `filters.py` — pas l'inverse.
- `fingerprint.py` dépend de `templates` (résolution de chemins) mais `templates` ne dépend jamais de `fingerprint` — vérifié par test nommé `test_templates_has_no_dependency_on_fingerprint`.

## Secrets en environnement, jamais en argument CLI

**Règle :** Les identifiants OpenSearch sont lus via `os.environ` (`opensearch_auth_from_env`), jamais passés en argument CLI — visibles via `ps aux`.

## Tests sans pytest-asyncio

**Convention :** Les tests async utilisent `asyncio.run()` directement, sans dépendance à `pytest-asyncio` (absente de `requirements-dev.txt`). Voir `test_dlq.py`, `test_indexer.py`.

## Package à plat

**Convention :** `src/*.py` sans `__init__.py`, importé via `sys.path` (voir `conftest.py` et `PYTHONPATH=src` dans le déploiement rsyslog). `pyproject.toml` a `package = false` — `uv` gère uniquement l'environnement sans build PEP 517.

## Opérations disque hors boucle asyncio

**Convention :** Les écritures disque se font via `asyncio.to_thread` pour ne jamais bloquer la boucle asyncio d'`omprog` (motif introduit session 4, repris par `dlq.py` session 13).
