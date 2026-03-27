"""NetDrop — Modaux Textual."""

from pathlib import Path
from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from ...transfer import human_size


# ── Saisie mot de passe (connexion à un pair) ─────────────────────────────────

class PasswordModal(ModalScreen[Optional[str]]):
    DEFAULT_CSS = """
    PasswordModal { align: center middle; }
    PasswordModal > Vertical {
        background: $surface; border: thick $primary;
        padding: 1 2; width: 52; height: auto;
    }
    PasswordModal Label { margin-bottom: 1; }
    PasswordModal Input { margin-bottom: 1; }
    PasswordModal Horizontal { align: right middle; }
    PasswordModal Button { margin-left: 1; }
    """

    def __init__(self, peer_id: str):
        super().__init__()
        self.peer_id = peer_id

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"🔐 Mot de passe requis\n[bold cyan]{self.peer_id}[/bold cyan]")
            yield Input(placeholder="Mot de passe…", password=True, id="pw-input")
            yield Label("", id="pw-err")
            with Horizontal():
                yield Button("Annuler", variant="default",  id="cancel")
                yield Button("Connexion", variant="primary", id="ok")

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None: self.dismiss(None)

    @on(Button.Pressed, "#ok")
    @on(Input.Submitted, "#pw-input")
    def _confirm(self) -> None:
        pw = self.query_one("#pw-input", Input).value
        if not pw:
            self.query_one("#pw-err", Label).update("[red]Mot de passe vide[/red]")
            return
        self.dismiss(pw)


# ── Acceptation d'un fichier entrant ─────────────────────────────────────────

class AcceptModal(ModalScreen[bool]):
    DEFAULT_CSS = """
    AcceptModal { align: center middle; }
    AcceptModal > Vertical {
        background: $surface; border: thick $warning;
        padding: 1 2; width: 58; height: auto;
    }
    AcceptModal Label { margin-bottom: 1; }
    AcceptModal Horizontal { align: right middle; margin-top: 1; }
    AcceptModal Button { margin-left: 1; }
    """

    def __init__(self, identity: str, filename: str, size: int):
        super().__init__()
        self.identity = identity
        self.filename = filename
        self.size = size

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("📥 [bold]Fichier entrant[/bold]")
            yield Label(f"De     : [bold cyan]{self.identity}[/bold cyan]")
            yield Label(f"Fichier: [bold]{self.filename}[/bold]")
            yield Label(f"Taille : {human_size(self.size)}")
            with Horizontal():
                yield Button("✗ Refuser", variant="error",   id="reject")
                yield Button("✓ Accepter", variant="success", id="accept")

    @on(Button.Pressed, "#reject")
    def _reject(self) -> None: self.dismiss(False)

    @on(Button.Pressed, "#accept")
    def _accept(self) -> None: self.dismiss(True)


# ── Définir / changer le mot de passe local ──────────────────────────────────

class SetPasswordModal(ModalScreen[Optional[str]]):
    DEFAULT_CSS = """
    SetPasswordModal { align: center middle; }
    SetPasswordModal > Vertical {
        background: $surface; border: thick $primary;
        padding: 1 2; width: 52; height: auto;
    }
    SetPasswordModal Label { margin-bottom: 1; }
    SetPasswordModal Input { margin-bottom: 1; }
    SetPasswordModal Horizontal { align: right middle; margin-top: 1; }
    SetPasswordModal Button { margin-left: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("🔐 [bold]Définir un mot de passe[/bold]")
            yield Input(placeholder="Nouveau mot de passe…",  password=True, id="pw1")
            yield Input(placeholder="Confirmer…",             password=True, id="pw2")
            yield Label("", id="err")
            with Horizontal():
                yield Button("Annuler",      variant="default", id="cancel")
                yield Button("Enregistrer",  variant="primary", id="save")

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None: self.dismiss(None)

    @on(Button.Pressed, "#save")
    def _save(self) -> None:
        pw1 = self.query_one("#pw1", Input).value
        pw2 = self.query_one("#pw2", Input).value
        err = self.query_one("#err", Label)
        if not pw1:
            err.update("[red]Le mot de passe est vide[/red]"); return
        if pw1 != pw2:
            err.update("[red]Les mots de passe ne correspondent pas[/red]"); return
        self.dismiss(pw1)


# ── Sélection de fichiers par chemin ─────────────────────────────────────────

class FilePickerModal(ModalScreen[list[Path]]):
    DEFAULT_CSS = """
    FilePickerModal { align: center middle; }
    FilePickerModal > Vertical {
        background: $surface; border: thick $primary;
        padding: 1 2; width: 70; height: auto;
    }
    FilePickerModal Label  { margin-bottom: 1; }
    FilePickerModal Static { color: $text-muted; margin-bottom: 1; }
    FilePickerModal Input  { margin-bottom: 1; }
    FilePickerModal Horizontal { align: right middle; margin-top: 1; }
    FilePickerModal Button { margin-left: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("📁 [bold]Ajouter des fichiers[/bold]")
            yield Static("Chemin(s) absolu(s), un par ligne — ex: C:\\Users\\moi\\doc.pdf")
            yield Input(placeholder="/chemin/vers/fichier.zip", id="path-input")
            yield Label("", id="path-err")
            with Horizontal():
                yield Button("Annuler", variant="default", id="cancel")
                yield Button("Ajouter", variant="primary", id="add")

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None: self.dismiss([])

    @on(Button.Pressed, "#add")
    @on(Input.Submitted, "#path-input")
    def _add(self) -> None:
        raw = self.query_one("#path-input", Input).value.strip()
        err = self.query_one("#path-err", Label)
        if not raw:
            self.dismiss([]); return
        paths, invalid = [], []
        for line in raw.splitlines():
            p = Path(line.strip())
            (paths if (p.exists() and p.is_file()) else invalid).append(p)
        if invalid:
            err.update(f"[red]Introuvable : {', '.join(str(p) for p in invalid)}[/red]"); return
        self.dismiss(paths)


# ── Confirmation générique ────────────────────────────────────────────────────

class ConfirmModal(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmModal { align: center middle; }
    ConfirmModal > Vertical {
        background: $surface; border: thick $error;
        padding: 1 2; width: 50; height: auto;
    }
    ConfirmModal Label { margin-bottom: 1; }
    ConfirmModal Horizontal { align: right middle; margin-top: 1; }
    ConfirmModal Button { margin-left: 1; }
    """

    def __init__(self, title: str, message: str):
        super().__init__()
        self._title   = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[bold]{self._title}[/bold]")
            yield Label(self._message)
            with Horizontal():
                yield Button("Annuler", variant="default", id="cancel")
                yield Button("Confirmer", variant="error", id="ok")

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None: self.dismiss(False)

    @on(Button.Pressed, "#ok")
    def _ok(self) -> None: self.dismiss(True)