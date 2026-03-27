"""NetDrop — Écran Paramètres."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import Button, Input, Label, Static, Switch

from ..widgets.modals import SetPasswordModal

if TYPE_CHECKING:
    from ..app import NetDropApp


def _row(label: str, *widgets) -> Horizontal:
    h = Horizontal(classes="s-row")
    # On ne peut pas yield dans __init__, on retourne un Horizontal dont on ajoute les enfants
    return h


class SettingsScreen(Static):
    DEFAULT_CSS = """
    SettingsScreen {
        padding: 1;
        height: 1fr;
        layout: vertical;
    }
    SettingsScreen ScrollableContainer { height: 1fr; }
    SettingsScreen .s-section {
        border: solid $surface;
        background: $surface;
        padding: 1 2;
        margin-bottom: 1;
    }
    SettingsScreen .s-title {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
        height: 1;
    }
    SettingsScreen .s-row {
        height: 3;
        align: left middle;
        margin-bottom: 0;
    }
    SettingsScreen .s-row Label  { width: 32; }
    SettingsScreen .s-row Switch { width: 8; }
    SettingsScreen .s-row Input  { width: 24; }
    SettingsScreen .s-row Button { margin-left: 1; }
    SettingsScreen #btn-save {
        margin-top: 1;
        width: 30;
    }
    """

    def compose(self) -> ComposeResult:
        with ScrollableContainer():
            # ── Sécurité ────────────────────────────────────────────────────
            with Vertical(classes="s-section"):
                yield Static("🔐 Sécurité", classes="s-title")

                with Horizontal(classes="s-row"):
                    yield Label("SSL/TLS activé")
                    yield Switch(id="sw-ssl")
                with Horizontal(classes="s-row"):
                    yield Label("Mot de passe requis")
                    yield Switch(id="sw-password")
                    yield Button("Changer le mdp",    id="btn-change-pw",  variant="primary")
                    yield Button("Supprimer le mdp",  id="btn-remove-pw",  variant="default")
                with Horizontal(classes="s-row"):
                    yield Label("Tokens temporaires")
                    yield Switch(id="sw-tokens")
                with Horizontal(classes="s-row"):
                    yield Label("Durée token (secondes)")
                    yield Input(id="inp-token-ttl")

            # ── Réseau ───────────────────────────────────────────────────────
            with Vertical(classes="s-section"):
                yield Static("🌐 Réseau", classes="s-title")

                with Horizontal(classes="s-row"):
                    yield Label("Port TCP")
                    yield Input(id="inp-tcp-port")
                with Horizontal(classes="s-row"):
                    yield Label("Port UDP (découverte)")
                    yield Input(id="inp-udp-port")
                with Horizontal(classes="s-row"):
                    yield Label("Découverte automatique")
                    yield Switch(id="sw-discovery")
                with Horizontal(classes="s-row"):
                    yield Label("Scan LAN actif")
                    yield Switch(id="sw-lan-scan")
                with Horizontal(classes="s-row"):
                    yield Label("Intervalle annonce (s)")
                    yield Input(id="inp-disc-interval")

            # ── Transferts ───────────────────────────────────────────────────
            with Vertical(classes="s-section"):
                yield Static("📁 Transferts", classes="s-title")

                with Horizontal(classes="s-row"):
                    yield Label("Dossier de réception")
                    yield Input(id="inp-dl-dir")
                with Horizontal(classes="s-row"):
                    yield Label("Acceptation automatique")
                    yield Switch(id="sw-auto-accept")
                with Horizontal(classes="s-row"):
                    yield Label("Confirmer avant envoi")
                    yield Switch(id="sw-confirm-send")
                with Horizontal(classes="s-row"):
                    yield Label("Taille max (MB, 0=∞)")
                    yield Input(id="inp-max-size")

            # ── Affichage ────────────────────────────────────────────────────
            with Vertical(classes="s-section"):
                yield Static("🖥️  Affichage", classes="s-title")

                with Horizontal(classes="s-row"):
                    yield Label("Afficher les IP des pairs")
                    yield Switch(id="sw-show-ip")
                with Horizontal(classes="s-row"):
                    yield Label("Afficher la vitesse")
                    yield Switch(id="sw-show-speed")

            # ── Historique ───────────────────────────────────────────────────
            with Vertical(classes="s-section"):
                yield Static("📋 Historique", classes="s-title")

                with Horizontal(classes="s-row"):
                    yield Label("Historique activé")
                    yield Switch(id="sw-history")
                with Horizontal(classes="s-row"):
                    yield Label("Entrées max")
                    yield Input(id="inp-hist-max")

            # ── Identité ─────────────────────────────────────────────────────
            with Vertical(classes="s-section"):
                yield Static("🆔 Identité", classes="s-title")
                yield Label("", id="lbl-current-id")
                with Horizontal(classes="s-row"):
                    yield Label("Nouvel identifiant (vide = aléatoire)")
                    yield Input(placeholder="SWIFT-EAGLE-1234", id="inp-new-id")
                    yield Button("Régénérer", id="btn-regen-id", variant="warning")

            yield Button("💾 Sauvegarder", id="btn-save", variant="success")

    def on_mount(self) -> None:
        self._load_values()

    def _app(self) -> "NetDropApp":
        return self.app  # type: ignore

    def _load_values(self) -> None:
        cfg   = self._app().config
        ident = self._app().im.get_or_create()

        self.query_one("#sw-ssl",           Switch).value = cfg.ssl_enabled
        self.query_one("#sw-password",      Switch).value = cfg.password_enabled
        self.query_one("#sw-tokens",        Switch).value = cfg.tokens_enabled
        self.query_one("#inp-token-ttl",    Input).value  = str(cfg.token_lifetime_seconds)
        self.query_one("#inp-tcp-port",     Input).value  = str(cfg.tcp_port)
        self.query_one("#inp-udp-port",     Input).value  = str(cfg.udp_port)
        self.query_one("#sw-discovery",     Switch).value = cfg.discovery_enabled
        self.query_one("#sw-lan-scan",      Switch).value = cfg.lan_scan_enabled
        self.query_one("#inp-disc-interval",Input).value  = str(cfg.discovery_interval)
        self.query_one("#inp-dl-dir",       Input).value  = cfg.download_dir
        self.query_one("#sw-auto-accept",   Switch).value = cfg.auto_accept
        self.query_one("#sw-confirm-send",  Switch).value = cfg.confirm_before_send
        self.query_one("#inp-max-size",     Input).value  = str(cfg.max_file_size_mb)
        self.query_one("#sw-show-ip",       Switch).value = cfg.show_peer_ip
        self.query_one("#sw-show-speed",    Switch).value = cfg.show_transfer_speed
        self.query_one("#sw-history",       Switch).value = cfg.history_enabled
        self.query_one("#inp-hist-max",     Input).value  = str(cfg.history_max_entries)
        self.query_one("#lbl-current-id",   Label).update(
            f"Identité actuelle : [bold cyan]{ident.identity_id}[/bold cyan]"
        )

    # ── Mot de passe ─────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-change-pw")
    def change_pw(self) -> None:
        self.app.push_screen(SetPasswordModal(), self._apply_pw)

    def _apply_pw(self, pw: Optional[str]) -> None:
        if pw:
            self._app().im.set_password(pw)
            disc = self._app().discovery
            if disc: disc.update_password_status(True)
            self.app.notify("Mot de passe mis à jour ✓", severity="information")

    @on(Button.Pressed, "#btn-remove-pw")
    def remove_pw(self) -> None:
        self._app().im.remove_password()
        disc = self._app().discovery
        if disc: disc.update_password_status(False)
        self.app.notify("Mot de passe supprimé", severity="information")

    # ── Identité ─────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-regen-id")
    def regen_id(self) -> None:
        new_id = self.query_one("#inp-new-id", Input).value.strip() or None
        app = self._app()
        new_ident = app.im.change_identity(new_id)
        app.local_identity = new_ident
        app.client = app._build_client()
        disc = app.discovery
        if disc: disc.update_identity(new_ident.identity_id)
        self.query_one("#lbl-current-id", Label).update(
            f"Identité actuelle : [bold cyan]{new_ident.identity_id}[/bold cyan]"
        )
        # Rafraîchir la carte dans HomeScreen
        try: app.query_one("HomeScreen").refresh_identity()
        except Exception: pass
        self.app.notify(f"Nouvelle identité : {new_ident.identity_id}", severity="information")

    # ── Sauvegarde ────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-save")
    def save(self) -> None:
        app = self._app()
        cfg = app.config
        try:
            cfg.ssl_enabled           = self.query_one("#sw-ssl",            Switch).value
            cfg.password_enabled      = self.query_one("#sw-password",       Switch).value
            cfg.tokens_enabled        = self.query_one("#sw-tokens",         Switch).value
            cfg.token_lifetime_seconds= int(self.query_one("#inp-token-ttl", Input).value or "3600")
            cfg.tcp_port              = int(self.query_one("#inp-tcp-port",  Input).value or "5000")
            cfg.udp_port              = int(self.query_one("#inp-udp-port",  Input).value or "5001")
            cfg.discovery_enabled     = self.query_one("#sw-discovery",      Switch).value
            cfg.lan_scan_enabled      = self.query_one("#sw-lan-scan",       Switch).value
            cfg.discovery_interval    = int(self.query_one("#inp-disc-interval", Input).value or "5")
            cfg.download_dir          = self.query_one("#inp-dl-dir",        Input).value
            cfg.auto_accept           = self.query_one("#sw-auto-accept",    Switch).value
            cfg.confirm_before_send   = self.query_one("#sw-confirm-send",   Switch).value
            cfg.max_file_size_mb      = int(self.query_one("#inp-max-size",  Input).value or "0")
            cfg.show_peer_ip          = self.query_one("#sw-show-ip",        Switch).value
            cfg.show_transfer_speed   = self.query_one("#sw-show-speed",     Switch).value
            cfg.history_enabled       = self.query_one("#sw-history",        Switch).value
            cfg.history_max_entries   = int(self.query_one("#inp-hist-max",  Input).value or "1000")
            cfg.save()
            cfg.ensure_dirs()
            self.app.notify("Paramètres sauvegardés ✓", severity="information")
        except ValueError as e:
            self.app.notify(f"Valeur invalide : {e}", severity="error")
        except Exception as e:
            self.app.notify(f"Erreur : {e}", severity="error")