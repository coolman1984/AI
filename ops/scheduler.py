"""Scheduled ingestion runner with alert on failure (MASTER_PLAN F.8)."""

from __future__ import annotations

from ops.alerts import AlertStore


def run_scheduled_ingestion(
    *,
    job_name: str,
    ingest_fn,
    alerts_path: str = ".brain/ingestion_alerts.json",
) -> dict:
    """Run a scheduled ingestion job; record alert on failure."""
    store = AlertStore(path=alerts_path)
    try:
        result = ingest_fn()
        return {
            "job_name": job_name,
            "status": "ok",
            "result": result,
        }
    except Exception as exc:  # noqa: BLE001 — scheduler must surface any ingestion failure
        alert = store.record_alert(
            alert_type="scheduled_ingestion_failed",
            message=str(exc),
            source=job_name,
            severity="error",
        )
        return {
            "job_name": job_name,
            "status": "failed",
            "error": str(exc),
            "alert": alert,
        }