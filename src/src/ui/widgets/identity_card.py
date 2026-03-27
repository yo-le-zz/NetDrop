"""NetDrop — Widget carte d'identité."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label, Static


class IdentityCard(Static):
    DEFAULT_CSS = """
    IdentityCard {
        background: $surface;
        border: solid $primary;
        padding: 0 2;
        height: 3;
        margin-bottom: 1;
    }
    IdentityCard Horizontal { height: 3; align: left middle; }
    IdentityCard #id-label  { width: auto; margin-right: 3; color: $accent; text-style: bold; }
    IdentityCard #ip-label  { width: auto; margin-right: 2; color: $text-muted; }
    IdentityCard #pw-label  { width: auto; margin-right: 2; color: $text-muted; }
    IdentityCard #ssl-label { width: auto; color: $text-muted; }
    """

    def __init__(self, identity_id: str, ip: str, port: int,
                 has_password: bool, ssl_on: bool):
        super().__init__()
        self._iid = identity_id
        self._ip  = ip
        self._port = port
        self._has_pw = has_password
        self._ssl = ssl_on

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label(f"🆔 {self._iid}", id="id-label")
            yield Label(f"📍 {self._ip}:{self._port}", id="ip-label")
            yield Label("🔐 Protégé" if self._has_pw else "🔓 Ouvert", id="pw-label")
            yield Label("🔒 SSL" if self._ssl else "⚠ no-SSL", id="ssl-label")

    def refresh_data(self, identity_id: str, ip: str, port: int,
                     has_password: bool, ssl_on: bool) -> None:
        self.query_one("#id-label",  Label).update(f"🆔 {identity_id}")
        self.query_one("#ip-label",  Label).update(f"📍 {ip}:{port}")
        self.query_one("#pw-label",  Label).update("🔐 Protégé" if has_password else "🔓 Ouvert")
        self.query_one("#ssl-label", Label).update("🔒 SSL" if ssl_on else "⚠ no-SSL")