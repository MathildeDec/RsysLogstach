"""Dead letter queue locale pour les échecs d'indexation OpenSearch permanents.

Nouveau module (session 13), réponse à l'item "Proposé" #2 de FEATURES.md :
`OpenSearchIndexer` traitait jusqu'ici tout échec (connexion refusée *ou*
erreur 4xx de mapping définitive) de la même façon — nouvelle tentative,
puis message rendu à rsyslog. Un document qui provoque une erreur de
mapping permanente (ex. un champ qui ne correspond pas au type attendu par
l'index template) ne devient jamais valide en le rejouant : le retenir
indéfiniment côté rsyslog (retenté toutes les 30 s, cf. rsyslog.conf) ne
fait que boucler pour toujours, sans jamais progresser.

Ce module fournit la voie de sortie : `LocalDeadLetterQueue.write()`
consigne le document dans un fichier JSONL local (une ligne par document,
append-only) — voir `indexer.py::OpenSearchIndexer.send`, qui l'appelle
uniquement pour les erreurs identifiées comme permanentes (`RequestError`/
`NotFoundError` d'opensearchpy, 400/404), jamais pour une erreur de
connexion ou un timeout (transitoires, comportement de retenue inchangé).
Ne dépend que de `tracing`, comme les autres modules feuilles du projet
(voir PATTERNS.md, "Absence de dépendances circulaires entre modules").
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from tracing import traced


class LocalDeadLetterQueue:
    """Consigne dans un fichier JSONL local les documents rejetés de façon permanente.

    Une ligne par document, format :
        {"@dlq_timestamp": "<ISO-8601 UTC>", "@dlq_index": "<index visé>",
         "@dlq_error": "<message d'erreur>", "document": {...}}

    Pas de rotation ni de purge automatique : ce fichier est destiné à une
    relecture/réindexation manuelle ponctuelle une fois la cause du rejet
    corrigée (ex. mapping de l'index ajusté) — voir FEATURES.md, "Limites
    connues". L'écriture se fait dans un thread séparé (`asyncio.to_thread`)
    pour ne jamais bloquer la boucle asyncio d'`omprog` le temps d'un appel
    système disque, cohérent avec le reste du projet (voir CLAUDE.md,
    session 4, passage du modèle à threads vers asyncio).
    """

    @traced
    def __init__(self, path: str) -> None:
        """Prépare le chemin du fichier DLQ (dossier parent créé si besoin).

        Args:
            path: Chemin du fichier JSONL, créé (ou complété s'il existe
                déjà) au premier appel à `write`.
        """
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @traced
    async def write(self, doc: dict, *, index: str, error: str) -> None:
        """Ajoute une ligne JSON au fichier DLQ pour ce document.

        Args:
            doc: Document qui aurait dû être indexé.
            index: Nom d'index OpenSearch visé au moment de l'échec.
            error: Message d'erreur (`str(exception)`), à titre indicatif
                seulement — jamais reparsé, jamais utilisé pour décider quoi
                que ce soit.
        """
        entry = {
            "@dlq_timestamp": datetime.now(timezone.utc).isoformat(),
            "@dlq_index": index,
            "@dlq_error": error,
            "document": doc,
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        await asyncio.to_thread(self._append, line)

    def _append(self, line: str) -> None:
        """Écriture disque proprement dite (appelée hors boucle asyncio, voir `write`)."""
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line)
