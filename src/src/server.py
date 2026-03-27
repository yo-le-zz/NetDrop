"""NetDrop — Serveur de réception.

Threading : le serveur tourne dans ses propres threads daemon.
Il communique avec l'UI via un callable `on_event` qui doit être
thread-safe (typiquement app.post_message via call_from_thread).
"""

import socket, ssl, threading, time
from pathlib import Path
from typing import Callable, Optional

from .auth import IdentityManager
from .config import NetDropConfig
from .crypto import create_server_ssl_context, ensure_certs
from .history import HistoryDB
from .transfer import PROTOCOL_VERSION, SocketIO, TransferStats, receive_file_from_meta

# Signature du callback : (event_name: str, data: dict) -> None
ServerEventCallback = Callable[[str, dict], None]


class NetDropServer:
    def __init__(self, config: NetDropConfig, identity_manager: IdentityManager,
                 history: HistoryDB, on_event: Optional[ServerEventCallback] = None):
        self.config = config
        self.im     = identity_manager
        self.history = history
        self._on_event = on_event

        self._server_sock: Optional[socket.socket] = None
        self._running   = False
        self._main_thread: Optional[threading.Thread] = None

        # pending accept : key -> threading.Event
        self._accept_events: dict[str, threading.Event] = {}
        self._accept_results: dict[str, bool] = {}
        self._accept_lock = threading.Lock()

    # ── Cycle de vie ─────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running: return
        self._running = True
        self._main_thread = threading.Thread(
            target=self._serve_forever, daemon=True, name="nd-server")
        self._main_thread.start()

    def stop(self) -> None:
        self._running = False
        if self._server_sock:
            try: self._server_sock.close()
            except Exception: pass

    def is_running(self) -> bool:
        return self._running

    # ── Réponse à une demande d'acceptation (appelé depuis le thread UI) ─────

    def respond_accept(self, key: str, accepted: bool) -> None:
        """Appelé depuis le thread UI via call_from_thread."""
        with self._accept_lock:
            self._accept_results[key] = accepted
            evt = self._accept_events.get(key)
        if evt:
            evt.set()

    # ── Boucle principale ─────────────────────────────────────────────────────

    def _serve_forever(self) -> None:
        while self._running:
            try:
                self._listen()
            except Exception:
                if self._running:
                    time.sleep(2)

    def _listen(self) -> None:
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        raw.bind((self.config.bind_host, self.config.tcp_port))
        raw.listen(10)
        raw.settimeout(1.0)
        self._server_sock = raw

        if self.config.ssl_enabled and ensure_certs():
            try:
                server_sock = create_server_ssl_context().wrap_socket(raw, server_side=True)
            except Exception:
                server_sock = raw
        else:
            server_sock = raw

        while self._running:
            try:
                client_sock, addr = server_sock.accept()
                threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, addr[0]),
                    daemon=True,
                    name=f"nd-client-{addr[0]}",
                ).start()
            except socket.timeout:
                continue
            except Exception:
                break

    # ── Gestion d'un client ───────────────────────────────────────────────────

    def _handle_client(self, sock: socket.socket, ip: str) -> None:
        sio = SocketIO(sock)
        identity_id = "?"
        try:
            # 1. Handshake
            hello = sio.recv_msg()
            if hello.get("msg") != "hello" or hello.get("version") != PROTOCOL_VERSION:
                sio.send_msg({"msg": "error", "reason": "Protocole incompatible"})
                return

            identity_id = hello.get("identity", "?")
            my_id = self.im.get_or_create()
            self._emit("client_connected", {"identity": identity_id, "ip": ip})

            # 2. Auth
            needs_pw = my_id.has_password() and self.config.password_enabled
            sio.send_msg({
                "msg": "auth_info",
                "password_required": needs_pw,
                "identity": my_id.identity_id,
                "version": PROTOCOL_VERSION,
            })

            if needs_pw:
                auth = sio.recv_msg()
                if auth.get("msg") != "auth":
                    sio.send_msg({"msg": "auth_fail", "reason": "Réponse manquante"}); return
                if not my_id.check_password(auth.get("password", "")):
                    sio.send_msg({"msg": "auth_fail", "reason": "Mot de passe incorrect"})
                    self._emit("client_auth_fail", {"identity": identity_id, "ip": ip,
                                                    "reason": "Mot de passe incorrect"})
                    return
                token = None
                if self.config.tokens_enabled:
                    token = self.im.generate_token(identity_id, self.config.token_lifetime_seconds)
                sio.send_msg({"msg": "auth_ok", "token": token})
            else:
                sio.send_msg({"msg": "auth_ok", "token": None})

            # 3. Réception des fichiers
            while self._running:
                try:
                    cmd = sio.recv_msg()
                except ConnectionError:
                    break

                if cmd.get("msg") == "bye":
                    break
                elif cmd.get("msg") == "file_meta":
                    self._process_file(sio, cmd, identity_id, ip)
                else:
                    sio.send_msg({"msg": "error", "reason": f"Commande inconnue: {cmd.get('msg')}"})

        except Exception as e:
            self._emit("transfer_error", {"error": str(e), "identity": identity_id, "ip": ip})
        finally:
            sio.close()
            self._emit("client_disconnected", {"identity": identity_id, "ip": ip})

    def _process_file(self, sio: SocketIO, meta: dict, identity_id: str, ip: str) -> None:
        filename = meta.get("name", "?")
        size     = int(meta.get("size", 0))

        # Acceptation manuelle si nécessaire
        if not self.config.auto_accept:
            key = f"{ip}-{filename}-{time.monotonic_ns()}"
            evt = threading.Event()
            with self._accept_lock:
                self._accept_events[key] = evt

            # Notifier l'UI — elle appellera respond_accept() en retour
            self._emit("accept_request", {
                "key": key,
                "identity": identity_id,
                "ip": ip,
                "filename": filename,
                "size": size,
            })

            # Attendre la décision (30s max)
            evt.wait(timeout=30)

            with self._accept_lock:
                accepted = self._accept_results.pop(key, True)
                self._accept_events.pop(key, None)

            if not accepted:
                sio.send_msg({"msg": "error", "reason": "Transfert refusé par l'utilisateur"})
                return

        # Callback de progression (thread-safe : l'UI ne doit PAS toucher les widgets ici)
        def on_progress(stats: TransferStats) -> None:
            self._emit("transfer_progress", {"stats": stats})

        stats = receive_file_from_meta(
            sio=sio,
            meta=meta,
            dest_dir=Path(self.config.download_dir),
            max_size_mb=self.config.max_file_size_mb,
            progress_cb=on_progress,
        )

        self._emit("transfer_done", {"stats": stats, "identity": identity_id, "ip": ip})

        if self.config.history_enabled:
            try:
                self.history.log(
                    direction="received",
                    filename=stats.filename,
                    size_bytes=stats.total_bytes,
                    peer_identity=identity_id,
                    peer_ip=ip,
                    status="success" if stats.success else ("checksum_fail" if "Checksum" in (stats.error or "") else "failed"),
                    duration_sec=(stats.end_time - stats.start_time),
                    speed_bps=stats.speed_bps,
                    local_path=stats.local_path,
                    error_msg=stats.error,
                )
                self.history.trim(self.config.history_max_entries)
            except Exception:
                pass

    def _emit(self, event: str, data: dict) -> None:
        if self._on_event:
            try: self._on_event(event, data)
            except Exception: pass