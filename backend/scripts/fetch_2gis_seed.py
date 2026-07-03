"""One-off: fetch 2GIS leads and write suppliers_seed.json (run from backend/)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dgis import CITY_PRESETS, DEFAULT_QUERIES, collect_leads

OUT = Path(__file__).resolve().parent.parent / "suppliers_seed.json"


def main() -> None:
    preset = CITY_PRESETS["krasnodar"]
    leads = collect_leads(
        list(DEFAULT_QUERIES),
        lat=float(preset["lat"]),  # type: ignore[arg-type]
        lon=float(preset["lon"]),  # type: ignore[arg-type]
        city_label=str(preset["label"]),
        page_size=20,
    )
    rows = []
    for lead in leads:
        rows.append(
            {
                k: v
                for k, v in lead.items()
                if not str(k).startswith("_") and k != "id"
            }
            | {"id": lead.get("id") or f"dgis-{lead.get('dgis_id', '')}"}
        )
    OUT.write_text(json.dumps({"city": preset["label"], "items": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} suppliers to {OUT}")


if __name__ == "__main__":
    main()
