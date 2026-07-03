"""Queryable ingestion and ops alerts (MASTER_PLAN F.8)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class AlertStore:
    def __init__(self, path: str = ".brain/ingestion_alerts.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._data: list[dict] = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self._data = []

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def record_alert(
        self,
        *,
        alert_type: str,
        message: str,
        source: str = "",
        severity: str = "warning",
    ) -> dict:
        record = {
            "alert_id": f"alert-{uuid4().hex[:12]}",
            "alert_type": alert_type,
            "message": message,
            "source": source,
            "severity": severity,
            "created_at": datetime.now(UTC).isoformat(),
            "resolved": False,
        }
        self._data.append(record)
        self._save()
        return record

    def list_alerts(
        self,
        *,
        alert_type: str | None = None,
        include_resolved: bool = False,
    ) -> list[dict]:
        results = []
        for alert in self._data:
            if alert_type and alert.get("alert_type") != alert_type:
                continue
            if not include_resolved and alert.get("resolved"):
                continue
            results.append(alert)
        return results

    def resolve_alert(self, alert_id: str) -> dict:
        for alert in self._data:
            if alert.get("alert_id") == alert_id:
                alert["resolved"] = True
                alert["resolved_at"] = datetime.now(UTC).isoformat()
                self._save()
                return alert
        raise KeyError(f"alert '{alert_id}' not found")