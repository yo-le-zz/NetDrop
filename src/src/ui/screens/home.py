"""NetDrop — Écran Accueil (découverte des pairs)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Label, Static

if TYPE_CHECKING:
    from ..app import NetDropApp


class HomeScreen(Static):
    """Onglet principal : carte d'identité + tableau des pairs."""

    DEFAULT_CSS = """
    HomeScreen {
        padding: 1;
        height: 1fr;
        layout: vertical;
    }
    HomeScreen #peer-section {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
        margin-top: 1;
    }
    HomeScreen #peer-title { color: $accent; text-style: bold; margin-bottom: 0; }
    HomeScreen #peer-actions {
        height: 3;
        margin-top: 1;
        align: left middle;
    }
    HomeScreen #peer-actions Button { margin-right: 1; }
    HomeScreen #scan-status { color: $text-muted; margin-left: 2; }
    """

    def compose(self) -> ComposeResult:
        # La carte d'identité est montée par l'App (elle connaît les données)
        yield Label("", id="identity-info")
        yield Label("", id="network-status")

        with Vertical(id="peer-section"):
            yield Label("Pairs découverts sur le LAN", id="peer-title")
            yield DataTable(id="peer-table", zebra_stripes=True, cursor_type="row")

        with Horizontal(id="peer-actions"):
            yield Button("🔄 Scanner LAN",          id="btn-scan",          variant="primary")
            yield Button("📤 Envoyer à ce pair",     id="btn-send-to-peer",  variant="success")
            yield Button("✏️  Renommer",              id="btn-rename-peer",   variant="default")
            yield Button("🗑️  Oublier",               id="btn-forget-peer",   variant="default")
            yield Label("", id="scan-status")

    def on_mount(self) -> None:
        self._init_table()
        self._refresh_identity_info()
        # Rafraîchissement périodique
        self.set_interval(3, self._refresh_peers)

    def _app(self) -> "NetDropApp":
        return self.app  # type: ignore

    def _init_table(self) -> None:
        t = self.query_one("#peer-table", DataTable)
        t.add_columns("Identité", "IP", "Port", "🔐", "Vu il y a", "Version")

    def _refresh_identity_info(self) -> None:
        app = self._app()
        ident = app.im.get_or_create()
        ip    = app.local_ip
        port  = app.config.tcp_port
        ssl   = "🔒 SSL" if app.config.ssl_enabled else "⚠ no-SSL"
        pw    = "🔐 Protégé" if (ident.has_password() and app.config.password_enabled) else "🔓 Ouvert"
        self.query_one("#identity-info", Label).update(
            f"[bold cyan]🆔 {ident.identity_id}[/bold cyan]  "
            f"[dim]📍 {ip}:{port}  {pw}  {ssl}[/dim]"
        )

    def _refresh_peers(self) -> None:
        app = self._app()
        disc = app.discovery
        if not disc:
            return
        t = self.query_one("#peer-table", DataTable)
        t.clear()
        for p in disc.get_peers():
            ip_display = p.ip if app.config.show_peer_ip else "***"
            t.add_row(
                p.identity_id,
                ip_display,
                str(p.tcp_port),
                "🔐" if p.has_password else "🔓",
                p.last_seen_str,
                p.version,
                key=p.identity_id,
            )
        # Màj du status réseau
        count = len(disc.get_peers())
        self.query_one("#network-status", Label).update(
            f"[dim]{count} pair(s) en ligne · port {app.config.tcp_port}[/dim]"
        )

    def refresh_identity(self) -> None:
        """Appelé depuis l'app quand l'identité change."""
        self._refresh_identity_info()

    # ── Boutons ───────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-scan")
    def do_scan(self) -> None:
        self.query_one("#scan-status", Label).update("[yellow]Scan en cours…[/yellow]")
        self._scan_worker()

    @work(thread=True)
    def _scan_worker(self) -> None:
        from ...discovery import scan_lan_range
        app = self._app()
        found = scan_lan_range(app.config.tcp_port, timeout=0.4)
        self.app.call_from_thread(
            self.query_one("#scan-status", Label).update,
            f"[green]{len(found)} machine(s) détectée(s)[/green]"
        )
        self.app.call_from_thread(self._refresh_peers)

    @on(Button.Pressed, "#btn-send-to-peer")
    def send_to_peer(self) -> None:
        peer = self._get_selected_peer()
        if not peer:
            return
        app = self._app()
        send_screen = app.query_one("SendScreen")
        send_screen.set_target(peer.ip, peer.tcp_port)
        app.query_one("TabbedContent").active = "tab-send"

    @on(Button.Pressed, "#btn-forget-peer")
    def forget_peer(self) -> None:
        peer = self._get_selected_peer()
        if not peer:
            return
        self._app().im.forget_peer(peer.identity_id)
        self._refresh_peers()

    @on(Button.Pressed, "#btn-rename-peer")
    def rename_peer(self) -> None:
        peer = self._get_selected_peer()
        if not peer:
            self.app.notify("Aucun pair sélectionné", severity="warning"); return
        # Demande le nom via une notification (simple)
        self.app.notify(f"Utilisez les paramètres pour renommer {peer.identity_id}",
                        severity="information")

    def _get_selected_peer(self):
        app = self._app()
        disc = app.discovery
        if not disc:
            return None
        t = self.query_one("#peer-table", DataTable)
        try:
            key = t.coordinate_to_cell_key(t.cursor_coordinate).row_key.value
            return next((p for p in disc.get_peers() if p.identity_id == key), None)
        except Exception:
            return None