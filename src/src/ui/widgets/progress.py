"""NetDrop — Widget de progression de transfert."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, ProgressBar, Static

from ...transfer import TransferStats, human_size


class TransferProgressWidget(Static):
    DEFAULT_CSS = """
    TransferProgressWidget {
        background: $surface;
        border: solid $accent;
        padding: 0 1;
        height: 6;
        margin-bottom: 1;
    }
    TransferProgressWidget #tp-filename { color: $text; text-style: bold; margin-top: 1; }
    TransferProgressWidget #tp-detail   { color: $text-muted; }
    TransferProgressWidget ProgressBar  { margin-top: 0; }
    """

    def compose(self) -> ComposeResult:
        yield Label("En attente…", id="tp-filename")
        yield Label("",            id="tp-detail")
        yield ProgressBar(total=100, show_eta=False, id="tp-bar")

    def update_stats(self, stats: TransferStats) -> None:
        pct  = int(stats.progress * 100)
        eta  = stats.eta_seconds
        eta_str = f" — ETA {eta:.0f}s" if eta is not None and eta < 9999 else ""

        self.query_one("#tp-filename", Label).update(stats.filename)
        self.query_one("#tp-detail",   Label).update(
            f"{human_size(stats.transferred_bytes)} / {human_size(stats.total_bytes)}"
            f"  {stats.speed_human}{eta_str}"
        )
        self.query_one("#tp-bar", ProgressBar).progress = pct

    def reset(self) -> None:
        self.query_one("#tp-filename", Label).update("En attente…")
        self.query_one("#tp-detail",   Label).update("")
        self.query_one("#tp-bar", ProgressBar).progress = 0