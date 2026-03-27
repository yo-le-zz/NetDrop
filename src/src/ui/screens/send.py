"""NetDrop — Écran Envoi de fichiers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Label, Log, Static

from ..widgets.modals import FilePickerModal, PasswordModal
from ..widgets.progress import TransferProgressWidget
from ...transfer import TransferStats, human_size

if TYPE_CHECKING:
    from ..app import NetDropApp


class SendScreen(Static):
    DEFAULT_CSS = """
    SendScreen {
        padding: 1;
        height: 1fr;
        layout: vertical;
    }
    SendScreen #file-section {
        height: 10;
        border: solid $primary;
        padding: 0 1;
        margin-bottom: 1;
    }
    SendScreen #file-title { color: $accent; text-style: bold; }
    SendScreen #file-actions { height: 3; align: left middle; margin-bottom: 1; }
    SendScreen #file-actions Button { margin-right: 1; }
    SendScreen #target-row { height: 3; align: left middle; margin-bottom: 1; }
    SendScreen #target-row Label { width: 14; }
    SendScreen #target-row #inp-host { width: 26; }
    SendScreen #target-row #inp-port { width: 8; }
    SendScreen #target-row Button { margin-left: 1; }
    SendScreen #progress-section { height: 7; }
    SendScreen #log-section {
        height: 1fr;
        border: solid $surface;
        padding: 0 1;
    }
    SendScreen #log-title { color: $accent; text-style: bold; }
    """

    def __init__(self):
        super().__init__()
        self._files: list[Path] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="file-section"):
            yield Label("📁 Fichiers à envoyer", id="file-title")
            yield DataTable(id="file-table", zebra_stripes=True, cursor_type="row")

        with Horizontal(id="file-actions"):
            yield Button("➕ Ajouter",    id="btn-add",    variant="primary")
            yield Button("🗑️ Retirer",    id="btn-remove", variant="default")
            yield Button("🧹 Vider",      id="btn-clear",  variant="default")
            yield Label("", id="file-count")

        with Horizontal(id="target-row"):
            yield Label("Destinataire:")
            yield Input(placeholder="IP ou identité…", id="inp-host")
            yield Input(placeholder="5000",            id="inp-port", value="5000")
            yield Button("📤 Envoyer",  id="btn-send",  variant="success")

        with Vertical(id="progress-section"):
            yield TransferProgressWidget()

        with Vertical(id="log-section"):
            yield Label("📋 Journal", id="log-title")
            yield Log(id="send-log", auto_scroll=True)

    def on_mount(self) -> None:
        t = self.query_one("#file-table", DataTable)
        t.add_columns("Fichier", "Taille", "Chemin complet")

    def _app(self) -> "NetDropApp":
        return self.app  # type: ignore

    # ── API publique ──────────────────────────────────────────────────────────

    def set_target(self, ip: str, port: int) -> None:
        """Préremplir le destinataire depuis l'onglet Accueil."""
        self.query_one("#inp-host", Input).value = ip
        self.query_one("#inp-port", Input).value = str(port)

    def log(self, msg: str) -> None:
        """Thread-safe : appelé depuis des workers."""
        self.query_one("#send-log", Log).write_line(msg)

    def update_progress(self, stats: TransferStats) -> None:
        self.query_one(TransferProgressWidget).update_stats(stats)

    # ── Gestion des fichiers ──────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-add")
    def add_files(self) -> None:
        self.app.push_screen(FilePickerModal(), self._on_files_picked)

    def _on_files_picked(self, paths: list[Path]) -> None:
        for p in paths:
            if p not in self._files:
                self._files.append(p)
        self._refresh_table()

    def _refresh_table(self) -> None:
        t = self.query_one("#file-table", DataTable)
        t.clear()
        for p in self._files:
            size = p.stat().st_size if p.exists() else 0
            t.add_row(p.name, human_size(size), str(p.parent), key=str(p))
        n = len(self._files)
        self.query_one("#file-count", Label).update(
            f"[dim]{n} fichier(s)[/dim]" if n else ""
        )

    @on(Button.Pressed, "#btn-remove")
    def remove_file(self) -> None:
        t = self.query_one("#file-table", DataTable)
        try:
            key = t.coordinate_to_cell_key(t.cursor_coordinate).row_key.value
            self._files = [f for f in self._files if str(f) != key]
            self._refresh_table()
        except Exception:
            pass

    @on(Button.Pressed, "#btn-clear")
    def clear_files(self) -> None:
        self._files.clear()
        self._refresh_table()

    # ── Envoi ─────────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-send")
    def start_send(self) -> None:
        if not self._files:
            self.app.notify("Aucun fichier sélectionné", severity="warning"); return

        host = self.query_one("#inp-host", Input).value.strip()
        if not host:
            self.app.notify("Destinataire manquant", severity="warning"); return

        try:
            port = int(self.query_one("#inp-port", Input).value.strip() or "5000")
        except ValueError:
            port = 5000

        # Vérifier si le pair a un mot de passe
        has_pw = self._peer_has_password(host)
        if has_pw:
            self.app.push_screen(
                PasswordModal(host),
                lambda pw: self._do_send(host, port, pw),
            )
        else:
            self._do_send(host, port, None)

    def _peer_has_password(self, host: str) -> bool:
        disc = self._app().discovery
        if not disc:
            return False
        peers = disc.get_peers()
        peer = next((p for p in peers if p.ip == host or p.identity_id == host), None)
        return peer.has_password if peer else False

    @work(thread=True)
    def _do_send(self, host: str, port: int, password: Optional[str]) -> None:
        """Exécuté dans un thread worker — on ne touche JAMAIS les widgets directement."""
        app = self._app()
        files = list(self._files)

        def on_status(msg: str) -> None:
            # post_message est thread-safe dans Textual
            self.app.call_from_thread(self.log, msg)

        def on_progress(stats: TransferStats) -> None:
            self.app.call_from_thread(self.update_progress, stats)

        results = app.client.send_files(
            host=host, port=port, files=files,
            password=password,
            on_progress=on_progress,
            on_status=on_status,
        )

        ok   = sum(1 for r in results if r.success)
        fail = len(results) - ok
        self.app.call_from_thread(self.log, f"── {ok} envoyé(s) · {fail} échoué(s) ──")
        self.app.call_from_thread(
            self.query_one(TransferProgressWidget).reset
        )
        # Notifier l'app pour refresh historique
        self.app.call_from_thread(app.refresh_history)