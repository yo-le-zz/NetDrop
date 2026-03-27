"""NetDrop — Client d'envoi."""

import socket, time
from pathlib import Path
from typing import Callable, Optional

from .config import NetDropConfig
from .crypto import create_client_ssl_context
from .history import HistoryDB
from .transfer import PROTOCOL_VERSION, SocketIO, TransferStats, send_file

ProgressCallback = Callable[[TransferStats], None]
StatusCallback   = Callable[[str], None]


class NetDropClient:
    def __init__(self, config: NetDropConfig, history: HistoryDB, my_identity_id: str):
        self.config = config
        self.history = history
        self.my_identity_id = my_identity_id

    def send_files(
        self,
        host: str,
        port: int,
        files: list[Path],
        password: Optional[str] = None,
        on_progress: Optional[ProgressCallback] = None,
        on_status: Optional[StatusCallback] = None,
    ) -> list[TransferStats]:
        results: list[TransferStats] = []

        def status(msg: str) -> None:
            if on_status:
                try: on_status(msg)
                except Exception: pass

        # ── Connexion ────────────────────────────────────────────────────────
        status(f"Connexion à {host}:{port}…")
        try:
            raw = socket.create_connection((host, port), timeout=10)
        except Exception as e:
            return [TransferStats(filename=f.name,
                                  total_bytes=f.stat().st_size if f.exists() else 0,
                                  error=f"Connexion échouée: {e}",
                                  start_time=time.monotonic(),
                                  end_time=time.monotonic())
                    for f in files]

        if self.config.ssl_enabled:
            try:
                sock = create_client_ssl_context().wrap_socket(raw, server_hostname=host)
            except Exception:
                sock = raw
        else:
            sock = raw

        sio = SocketIO(sock)
        peer_identity = host

        try:
            # Handshake
            status("Handshake…")
            sio.send_msg({"msg": "hello", "identity": self.my_identity_id,
                          "version": PROTOCOL_VERSION})

            auth_info = sio.recv_msg()
            if auth_info.get("msg") == "error":
                raise ConnectionError(auth_info.get("reason", "Erreur serveur"))
            peer_identity = auth_info.get("identity", host)

            # Auth
            if auth_info.get("password_required"):
                if password is None:
                    raise PermissionError("Ce pair demande un mot de passe")
                status("Authentification…")
                sio.send_msg({"msg": "auth", "password": password})
                resp = sio.recv_msg()
                if resp.get("msg") != "auth_ok":
                    raise PermissionError(resp.get("reason", "Authentification échouée"))
                status("Authentifié ✓")
            else:
                status("Connecté ✓")

            # Envoi fichiers
            for filepath in files:
                if not filepath.exists():
                    results.append(TransferStats(filename=filepath.name, total_bytes=0,
                                                 error="Fichier introuvable",
                                                 start_time=time.monotonic(),
                                                 end_time=time.monotonic()))
                    continue

                size = filepath.stat().st_size
                max_mb = self.config.max_file_size_mb
                if max_mb > 0 and size > max_mb * 1024 * 1024:
                    results.append(TransferStats(filename=filepath.name, total_bytes=size,
                                                 error=f"Trop grand (max {max_mb} MB)",
                                                 start_time=time.monotonic(),
                                                 end_time=time.monotonic()))
                    continue

                status(f"Envoi de {filepath.name}…")
                stats = send_file(sio, filepath, progress_cb=on_progress,
                                  chunk_size=self.config.chunk_size)
                results.append(stats)

                if self.config.history_enabled:
                    self._log(stats, "sent", peer_identity, host)

            sio.send_msg({"msg": "bye"})
            status("Terminé ✓")

        except (PermissionError, ConnectionError) as e:
            for f in files:
                if not any(r.filename == f.name for r in results):
                    results.append(TransferStats(filename=f.name,
                                                 total_bytes=f.stat().st_size if f.exists() else 0,
                                                 error=str(e),
                                                 start_time=time.monotonic(),
                                                 end_time=time.monotonic()))
        except Exception as e:
            status(f"Erreur: {e}")
            for f in files:
                if not any(r.filename == f.name for r in results):
                    results.append(TransferStats(filename=f.name,
                                                 total_bytes=f.stat().st_size if f.exists() else 0,
                                                 error=str(e),
                                                 start_time=time.monotonic(),
                                                 end_time=time.monotonic()))
        finally:
            sio.close()

        return results

    def probe_peer(self, host: str, port: int) -> Optional[dict]:
        try:
            raw = socket.create_connection((host, port), timeout=3)
            sock = raw
            if self.config.ssl_enabled:
                try: sock = create_client_ssl_context().wrap_socket(raw, server_hostname=host)
                except Exception: pass
            sio = SocketIO(sock)
            sio.send_msg({"msg": "hello", "identity": self.my_identity_id,
                          "version": PROTOCOL_VERSION})
            resp = sio.recv_msg()
            sio.send_msg({"msg": "bye"})
            sio.close()
            return resp
        except Exception:
            return None

    def _log(self, stats: TransferStats, direction: str, identity: str, ip: str) -> None:
        try:
            self.history.log(
                direction=direction, filename=stats.filename,
                size_bytes=stats.total_bytes, peer_identity=identity, peer_ip=ip,
                status="success" if stats.success else "failed",
                duration_sec=(stats.end_time - stats.start_time) if stats.end_time else 0,
                speed_bps=stats.speed_bps, local_path=stats.local_path, error_msg=stats.error,
            )
        except Exception:
            pass