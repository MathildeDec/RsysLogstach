"""Ajoute `src/` au sys.path pour que les tests importent les modules
applicatifs (`templates`, `filters`, `enrichment`, `indexer`, `util`,
`tracing`) sans installation préalable — motif repris du squelette de
Mathilde.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
