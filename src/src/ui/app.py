"""NetDrop — Application Textual (shell minimal)."""

from __future__ import annotations

from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Footer, Header, TabbedContent, TabPane

from .screens import HomeScreen, SendScreen, HistoryScreen, SettingsScreen
from ..auth import IdentityManager
from ..client import NetDropClient
from ..config import NetDropConfig
from ..crypto import get_local_ip
from ..discovery import DiscoveryService
from ..history import HistoryDB
from ..server import NetDropServer
from ..transfer import TransferStats


class NetDropApp(App):
    TITLE     = "NetDrop"
    SUB_TITLE = "Transfert LAN sécurisé — v1.0.0"

    BINDINGS = [
        Binding("ctrl+q", "quit",          "Quitter",    priority=True),
        Binding("ctrl+s", "tab_send",      "Envoyer"),
        Binding("ctrl+h", "tab_history",   "Historique"),
        Binding("ctrl+p", "tab_settings",  "Paramètres"),
        Binding("f1",     "show_help",     "Aide"),
    ]

    CSS = """
    Screen { background: $background; }
    TabbedContent { height: 1fr; }
    ContentSwitcher { height: 1fr; }
    TabPane { padding: 0; height: 1fr; }
    """

    # ── Message interne thread-safe ──────────────────────────────────────────
    # Toutes les notifs du serveur arrivent ici via post_message()
    # (post_message est thread-safe dans Textual)

    class ServerEvent(Message):
        def __init__(self, event_type: str, data: dict):
            self.event_type = event_type
            self.data = data
            super().__init__()

    # ── Initialisation ────────────────────────────────────────────────────────

    def __init__(self, config: NetDropConfig, im: IdentityManager, history: HistoryDB):
        super().__init__()
        self.config   = config
        self.im       = im
        self.history  = history

        self.local_ip       = get_local_ip()
        self.local_identity = im.get_or_create()

        self.server:    Optional[NetDropServer]   = None
        self.discovery: Optional[DiscoveryService] = None
        self.client:    NetDropClient             = self._build_client()

    def _build_client(self) -> NetDropClient:
        return NetDropClient(self.config, self.history, self.local_identity.identity_id)

    # ── Composition ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="tab-home"):
            with TabPane("🏠 Accueil",    id="tab-home"):
                yield HomeScreen()
            with TabPane("📤 Envoyer",   id="tab-send"):
                yield SendScreen()
            with TabPane("📋 Historique", id="tab-history"):
                yield HistoryScreen()
            with TabPane("⚙️  Paramètres", id="tab-settings"):
                yield SettingsScreen()
        yield Footer()

    # ── Montage ───────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self.config.ensure_dirs()
        self._start_server()
        if self.config.discovery_enabled:
            self._start_discovery()

    # ── Backend ───────────────────────────────────────────────────────────────

    def _start_server(self) -> None:
        self.server = NetDropServer(
            config=self.config,
            identity_manager=self.im,
            history=self.history,
            # Ce callback est appelé depuis les threads serveur.
            # post_message() est thread-safe → pas besoin de call_from_thread ici.
            on_event=lambda evt, data: self.post_message(self.ServerEvent(evt, data)),
        )
        self.server.start()

    def _start_discovery(self) -> None:
        ident = self.local_identity
        self.discovery = DiscoveryService(
            identity_id=ident.identity_id,
            tcp_port=self.config.tcp_port,
            udp_port=self.config.udp_port,
            has_password=ident.has_password() and self.config.password_enabled,
            interval=self.config.discovery_interval,
            # Pas de callback ici : HomeScreen poll en set_interval
        )
        self.discovery.start()

    # ── Gestion des événements serveur (thread UI) ────────────────────────────

    def on_net_drop_app_server_event(self, msg: "NetDropApp.ServerEvent") -> None:
        """Appelé dans le thread UI — on peut toucher les widgets ici."""
        evt  = msg.event_type
        data = msg.data

        if evt == "transfer_progress":
            stats: TransferStats = data["stats"]
            try:
                self.query_one("SendScreen", SendScreen).update_progress(stats)
            except Exception:
                pass

        elif evt == "transfer_done":
            stats: TransferStats = data["stats"]
            identity = data.get("identity", "?")
            icon = "✓" if stats.success else "✗"
            try:
                self.query_one("SendScreen", SendScreen).log(
                    f"[{icon}] Reçu de {identity} : {stats.filename}"
                )
            except Exception:
                pass
            self.refresh_history()
            self.notify(
                f"{'✓' if stats.success else '✗'} {stats.filename} reçu de {identity}",
                severity="information" if stats.success else "error",
            )

        elif evt == "transfer_error":
            self.notify(f"Erreur transfert : {data.get('error', '?')}", severity="error")

        elif evt == "client_auth_fail":
            self.notify(
                f"Auth échouée : {data.get('identity', '?')} — {data.get('reason', '?')}",
                severity="warning",
            )

        elif evt == "accept_request":
            self._handle_accept_request(data)

        elif evt == "client_connected":
            try:
                self.query_one("SendScreen", SendScreen).log(
                    f"[+] Connexion de {data.get('identity','?')} ({data.get('ip','?')})"
                )
            except Exception:
                pass

    def _handle_accept_request(self, data: dict) -> None:
        from .widgets.modals import AcceptModal

        def on_decision(accepted: bool) -> None:
            if self.server:
                self.server.respond_accept(data["key"], accepted)
            try:
                self.query_one("SendScreen", SendScreen).log(
                    f"{'✓ Accepté' if accepted else '✗ Refusé'} : {data['filename']}"
                )
            except Exception:
                pass

        self.push_screen(
            AcceptModal(data["identity"], data["filename"], data["size"]),
            on_decision,
        )

    # ── API pour les screens ──────────────────────────────────────────────────

    def refresh_history(self) -> None:
        try:
            self.query_one("HistoryScreen", HistoryScreen).load()
        except Exception:
            pass

    # ── Raccourcis ────────────────────────────────────────────────────────────

    def action_tab_send(self)     -> None: self.query_one(TabbedContent).active = "tab-send"
    def action_tab_history(self)  -> None: self.query_one(TabbedContent).active = "tab-history"
    def action_tab_settings(self) -> None: self.query_one(TabbedContent).active = "tab-settings"

    def action_show_help(self) -> None:
        self.notify(
            "Ctrl+Q Quitter · Ctrl+S Envoyer · Ctrl+H Historique · Ctrl+P Paramètres",
            timeout=6,
        )

    # ── Nettoyage ─────────────────────────────────────────────────────────────

    def on_unmount(self) -> None:
        if self.server:    self.server.stop()
        if self.discovery: self.discovery.stop()