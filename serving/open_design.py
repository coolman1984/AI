"""Output layer (MASTER_PLAN K.1 layer 6).

Open Design (nexu-io) is the real renderer for dashboards/decks/PDF/PPTX and plugs in
HERE. It is OUTPUT ONLY: it renders an already-audited, signed-off card — it never
computes or invents a number. Until the Open Design app is wired, a built-in HTML
renderer produces a real artifact so the pipeline is end-to-end.
"""
from __future__ import annotations

from shared.contracts.models import ManagerCard


class Renderer:
    def render_html(self, card: ManagerCard, audited: bool, signed_by: str | None) -> str:
        raise NotImplementedError


class BuiltinHtmlRenderer(Renderer):
    def render_html(self, card: ManagerCard, audited: bool, signed_by: str | None) -> str:
        nums = "".join(
            f"<li><b>{n.label}:</b> {n.value:+,.2f} "
            f"<small>[{n.evidence.source} · {n.evidence.method}]</small></li>"
            for n in card.key_numbers
        )
        status = f"audited={audited}, signed_by={signed_by or 'UNSIGNED'}"
        return (
            "<!doctype html><meta charset='utf-8'>"
            "<style>body{font-family:sans-serif;max-width:720px;margin:2rem auto}</style>"
            f"<h2>{card.headline}</h2>"
            f"<p><b>Decision:</b> {card.decision_needed}</p>"
            f"<ul>{nums}</ul>"
            f"<p><b>Drivers:</b> {'; '.join(card.drivers)}</p>"
            f"<p><b>Confidence:</b> {card.confidence['confidence']}</p>"
            f"<hr><small>{status}</small>"
        )


class OpenDesignRenderer(Renderer):
    """Adapter for the real nexu-io/open-design app (HTML/PDF/PPTX)."""
    def render_html(self, card: ManagerCard, audited: bool, signed_by: str | None) -> str:
        raise NotImplementedError(
            "Open Design not installed. Install the nexu-io/open-design app and point this "
            "adapter at it; until then config tools.renderer=builtin_html."
        )


def get_renderer(name: str) -> Renderer:
    return {"builtin_html": BuiltinHtmlRenderer, "open_design": OpenDesignRenderer}[name]()
