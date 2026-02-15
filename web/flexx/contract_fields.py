# FILE: web/flexx/contract_fields.py  (новое — 2026-02-14)
# PURPOSE: Единый справочник полей contract (key->textarea) для многократного переиспользования в разных формах/панелях.

from __future__ import annotations

from typing import Final, List, TypedDict


class ContractField(TypedDict):
    key: str
    label_de: str
    rows: int


CONTRACT_FIELDS: Final[List[ContractField]] = [
    {"key": "unternehmen_emittent", "label_de": "Unternehmen / Emittent", "rows": 3},
    {"key": "ueberschrift_emission", "label_de": "Überschrift / Emission", "rows": 2},
    {"key": "text_zwischen_1", "label_de": "Text zwischen 1", "rows": 6},
    {"key": "banking", "label_de": "Bankverbindung des Emittenten", "rows": 6},
    {"key": "text_zwischen_2", "label_de": "Text zwischen 2", "rows": 6},
    {"key": "text_zwischen_3", "label_de": "Text zwischen 3", "rows": 15},
    {"key": "ueberschrift_ergaenzung", "label_de": "Überschrift Ergänzung", "rows": 2},
    {"key": "ergaenzung_text_1", "label_de": "Ergänzungstext 1", "rows": 8},
    {"key": "ergaenzung_beispiel", "label_de": "Ergänzung Beispiel", "rows": 8},
]
