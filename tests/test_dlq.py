"""Tests pytest pour dlq.py::LocalDeadLetterQueue (session 13).

Pas de dépendance à pytest-asyncio (absente de requirements-dev.txt,
même convention que test_indexer.py) : `write` est piloté via
`asyncio.run()` directement.
"""

from __future__ import annotations

import asyncio
import json

from dlq import LocalDeadLetterQueue


class TestWrite:
    def test_creates_parent_directory_if_missing(self, tmp_path) -> None:
        path = tmp_path / "nested" / "dir" / "dlq.jsonl"
        LocalDeadLetterQueue(str(path))  # ne doit pas lever, même si "nested/dir" n'existe pas encore
        assert path.parent.is_dir()
        assert not path.exists()  # le fichier lui-même n'est créé qu'au premier write

    def test_writes_one_json_line_per_call(self, tmp_path) -> None:
        path = tmp_path / "dlq.jsonl"
        dlq = LocalDeadLetterQueue(str(path))
        asyncio.run(dlq.write({"message": "un"}, index="idx-1", error="boom"))
        asyncio.run(dlq.write({"message": "deux"}, index="idx-1", error="boom encore"))

        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["document"] == {"message": "un"}
        assert json.loads(lines[1])["document"] == {"message": "deux"}

    def test_entry_contains_expected_keys(self, tmp_path) -> None:
        path = tmp_path / "dlq.jsonl"
        dlq = LocalDeadLetterQueue(str(path))
        asyncio.run(dlq.write({"message": "hello"}, index="switch-logs-2026.09.14", error="mapper_parsing_exception"))

        entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        assert entry["@dlq_index"] == "switch-logs-2026.09.14"
        assert entry["@dlq_error"] == "mapper_parsing_exception"
        assert entry["document"] == {"message": "hello"}
        assert "@dlq_timestamp" in entry

    def test_timestamp_is_iso8601_utc(self, tmp_path) -> None:
        from datetime import datetime

        path = tmp_path / "dlq.jsonl"
        dlq = LocalDeadLetterQueue(str(path))
        asyncio.run(dlq.write({"message": "hello"}, index="idx-1", error="boom"))

        entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        parsed = datetime.fromisoformat(entry["@dlq_timestamp"])
        assert parsed.tzinfo is not None  # timezone-aware, pas un timestamp naïf

    def test_non_ascii_content_preserved(self, tmp_path) -> None:
        """`ensure_ascii=False` : un champ accentué reste lisible tel quel dans le fichier."""
        path = tmp_path / "dlq.jsonl"
        dlq = LocalDeadLetterQueue(str(path))
        asyncio.run(dlq.write({"message": "événement réseau"}, index="idx-1", error="erreur"))

        raw = path.read_text(encoding="utf-8")
        assert "événement réseau" in raw

    def test_appends_without_truncating_existing_content(self, tmp_path) -> None:
        path = tmp_path / "dlq.jsonl"
        path.write_text(json.dumps({"pre_existing": True}) + "\n", encoding="utf-8")
        dlq = LocalDeadLetterQueue(str(path))
        asyncio.run(dlq.write({"message": "nouveau"}, index="idx-1", error="boom"))

        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"pre_existing": True}
        assert json.loads(lines[1])["document"] == {"message": "nouveau"}
