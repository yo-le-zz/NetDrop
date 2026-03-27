"""NetDrop — Écran Historique des transferts."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Label, Static

from ..widgets.modals import ConfirmModal

if TYPE_CHECKING:
    from ..app import NetDropApp


class HistoryScreen(Static):
    DEFAULT_CSS = """
    HistoryScreen {
        padding: 1;
        height: 1fr;
        layout: vertical;
    }
    HistoryScreen #actions { height: 3; align: left middle; margin-bottom: 1; }
    HistoryScreen #actions Button { margin-right: 1; }
    HistoryScreen #search-row { height: 3; align: left middle; margin-bottom: 1; }
    HistoryScreen #search-row Input { width: 40; }
    HistoryScreen #search-row Button { margin-left: 1; }
    HistoryScreen #stats { color: $text-muted; margin-bottom: 1; }
    HistoryScreen #table-section {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="actions"):
            yield Button("🔄 Actualiser",    id="btn-refresh",  variant="primary")
            yield Button("🗑️  Supprimer",     id="btn-delete",   variant="default")
            yield Button("💣 Tout effacer",   id="btn-clear",    variant="error")
            yield Button("📥 Export CSV",     id="btn-export",   variant="default")

        with Horizontal(id="search-row"):
            yield Input(placeholder="🔍 Fichier, identité, IP…", id="inp-search")
            yield Button("Chercher",   id="btn-search",  variant="primary")
            yield Button("Réinitialiser", id="btn-reset", variant="default")

        yield Label("", id="stats")

        with Vertical(id="table-section"):
            yield DataTable(id="hist-table", zebra_stripes=True, cursor_type="row")

    def on_mount(self) -> None:
        t = self.query_one("#hist-table", DataTable)
        t.add_columns("ID", "Date", "↕", "Fichier", "Taille",
                      "Pair", "IP", "✓", "Durée", "Vitesse")
        self.load()

    def _app(self) -> "NetDropApp":
        return self.app  # type: ignore

    # ── Chargement ────────────────────────────────────────────────────────────

    def load(self, query: str = "") -> None:
        app = self._app()
        t = self.query_one("#hist-table", DataTable)
        t.clear()
        records = app.history.search(query) if query else app.history.get_all(limit=300)
        for r in records:
            ip = r.peer_ip if app.config.show_peer_ip else "***"
            speed = r.human_speed if app.config.show_transfer_speed else ""
            t.add_row(
                str(r.id), r.short_date, r.direction_icon,
                r.filename[:32], r.human_size,
                r.peer_identity[:22], ip,
                r.status_icon, r.human_duration, speed,
                key=str(r.id),
            )
        self._update_stats()

    def _update_stats(self) -> None:
        s = self._app().history.get_stats()
        total = s.get("total", 0)
        sent  = s.get("sent_count", 0)
        recv  = s.get("recv_count", 0)
        from ...transfer import human_size
        total_bytes = human_size(int(s.get("total_bytes") or 0))
        self.query_one("#stats", Label).update(
            f"[dim]{total} transfert(s)  ·  ↑ {sent} envoyés  ·  "
            f"↓ {recv} reçus  ·  {total_bytes} au total[/dim]"
        )

    # ── Actions ───────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-refresh")
    def on_refresh_pressed(self) -> None:
        self.load(self.query_one("#inp-search", Input).value.strip())

    @on(Button.Pressed, "#btn-search")
    @on(Input.Submitted, "#inp-search")
    def search(self) -> None:
        self.load(self.query_one("#inp-search", Input).value.strip())

    @on(Button.Pressed, "#btn-reset")
    def reset_search(self) -> None:
        self.query_one("#inp-search", Input).value = ""
        self.load()

    @on(Button.Pressed, "#btn-delete")
    def delete_entry(self) -> None:
        t = self.query_one("#hist-table", DataTable)
        try:
            key = t.coordinate_to_cell_key(t.cursor_coordinate).row_key.value
            self._app().history.delete(int(key))
            self.load(self.query_one("#inp-search", Input).value.strip())
        except Exception:
            self.app.notify("Aucune ligne sélectionnée", severity="warning")

    @on(Button.Pressed, "#btn-clear")
    def clear_history(self) -> None:
        self.app.push_screen(
            ConfirmModal(
                "Effacer tout l'historique",
                "Cette action est irréversible. Continuer ?"
            ),
            self._on_clear_confirmed,
        )

    def _on_clear_confirmed(self, confirmed: bool) -> None:
        if not confirmed:
            return
        n = self._app().history.clear()
        self.load()
        self.app.notify(f"{n} entrée(s) supprimée(s)", severity="information")

    @on(Button.Pressed, "#btn-export")
    def export_csv(self) -> None:
        out = Path.home() / "netdrop_history.csv"
        try:
            n = self._app().history.export_csv(out)
            self.app.notify(f"Exporté : {out.name} ({n} lignes)", severity="information")
        except Exception as e:
            self.app.notify(f"Erreur export : {e}", severity="error")