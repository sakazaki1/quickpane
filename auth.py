"""Local Sign in with ChatGPT flow for a personal desktop application."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import tempfile
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import jwt
import requests
from PyQt6.QtCore import QObject, pyqtSignal


AUTH_ORIGIN = "https://auth.openai.com"
RESOURCE = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "painel-chat"
SESSION_FILE = CONFIG_DIR / "session.json"


def _save_private(data: dict) -> None:
    CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="session-", dir=CONFIG_DIR)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file)
        os.replace(name, SESSION_FILE)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _load_private() -> dict:
    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class AuthManager(QObject):
    connected = pyqtSignal(str)
    failed = pyqtSignal(str)
    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.RLock()
        self.data = _load_private()
        if "host_id" not in self.data:
            self.data["host_id"] = f"urn:uuid:{uuid.uuid4()}"
            _save_private(self.data)

    @property
    def email(self) -> str:
        with self._lock:
            return self.data.get("account", {}).get("email", "")

    @property
    def ready(self) -> bool:
        with self._lock:
            account = self.data.get("account", {})
            return bool(account.get("refresh_token") and "chatgpt.tokens.use.direct" in account.get("scopes", []))

    def sign_in(self) -> None:
        threading.Thread(target=self._sign_in_worker, daemon=True).start()

    def _sign_in_worker(self) -> None:
        server = None
        try:
            verifier = secrets.token_urlsafe(48)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            callback: dict = {}

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    parsed = urlparse(self.path)
                    if parsed.path != "/auth/callback":
                        self.send_error(404)
                        return
                    callback.update({k: v[0] for k, v in parse_qs(parsed.query).items()})
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"<h2>Connection complete. You can return to QuickPane.</h2>")

                def log_message(self, *_args):
                    pass

            server = HTTPServer(("127.0.0.1", 0), Handler)
            server.timeout = 1
            redirect_uri = f"http://127.0.0.1:{server.server_port}/auth/callback"
            with self._lock:
                previous = self.data.get("account", {}).copy()
                host_id = self.data["host_id"]
            client_id = previous.get("client_id", "dynamic_agent_client")
            params = {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "scope": SCOPES,
                "resource": RESOURCE,
                "state": state,
                "nonce": nonce,
                "code_challenge_method": "S256",
                "code_challenge": challenge,
                "ext_agent_host_id": host_id,
            }
            if client_id == "dynamic_agent_client":
                params["agent_name_hint"] = "QuickPane"
            else:
                if previous.get("id_token"):
                    params["id_token_hint"] = previous["id_token"]
                if previous.get("email"):
                    params["login_hint"] = previous["email"]
            webbrowser.open(f"{AUTH_ORIGIN}/api/accounts/authorize?{urlencode(params)}")
            deadline = time.monotonic() + 240
            while not callback and time.monotonic() < deadline:
                server.handle_request()
            if not callback:
                raise RuntimeError("O login expirou. Tente novamente.")
            if not secrets.compare_digest(callback.get("state", ""), state):
                raise RuntimeError("O retorno do login não passou pela validação de segurança.")
            if callback.get("error"):
                raise RuntimeError("A autorização foi cancelada ou recusada.")
            issued_id = callback.get("client_id", client_id)
            if issued_id == "dynamic_agent_client" or (previous and issued_id != client_id):
                raise RuntimeError("Não foi possível validar o registro do aplicativo.")
            code = callback.get("code")
            if not code:
                raise RuntimeError("O login não retornou um código de autorização.")
            response = requests.post(
                f"{AUTH_ORIGIN}/api/accounts/oauth/token",
                data={"grant_type": "authorization_code", "client_id": issued_id,
                      "code": code, "code_verifier": verifier,
                      "redirect_uri": redirect_uri, "resource": RESOURCE},
                timeout=25,
            )
            response.raise_for_status()
            tokens = response.json()
            scopes = tokens.get("scope", "").split()
            if "chatgpt.tokens.use.direct" not in scopes:
                raise RuntimeError("O uso do plano ChatGPT não foi autorizado para este aplicativo.")
            oidc = requests.get(f"{AUTH_ORIGIN}/.well-known/openid-configuration", timeout=15).json()
            jwk_client = jwt.PyJWKClient(oidc["jwks_uri"])
            id_token = tokens["id_token"]
            signing_key = jwk_client.get_signing_key_from_jwt(id_token)
            claims = jwt.decode(id_token, signing_key.key, algorithms=["RS256"],
                                audience=issued_id, issuer=AUTH_ORIGIN)
            if not secrets.compare_digest(claims.get("nonce", ""), nonce):
                raise RuntimeError("O login retornou um nonce inválido.")
            if previous and claims.get("sub") != previous.get("subject"):
                raise RuntimeError("A conta retornada é diferente da conta salva.")
            account = {
                "client_id": issued_id, "subject": claims["sub"],
                "email": claims.get("email", "Conta ChatGPT"),
                "id_token": id_token, "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"], "scopes": scopes,
                "expires_at": time.time() + int(tokens.get("expires_in", 3600)),
            }
            with self._lock:
                self.data["account"] = account
                _save_private(self.data)
            self.connected.emit(account["email"])
            self.changed.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if server:
                server.server_close()

    def access_token(self) -> str:
        with self._lock:
            account = self.data.get("account", {})
            if not account.get("refresh_token"):
                raise RuntimeError("Conecte sua conta ChatGPT primeiro.")
            if time.time() < account.get("expires_at", 0) - 120:
                return account["access_token"]
            response = requests.post(
                f"{AUTH_ORIGIN}/api/accounts/oauth/token",
                data={"grant_type": "refresh_token", "client_id": account["client_id"],
                      "refresh_token": account["refresh_token"], "resource": RESOURCE},
                timeout=25,
            )
            response.raise_for_status()
            tokens = response.json()
            account.update({"access_token": tokens["access_token"],
                            "refresh_token": tokens.get("refresh_token", account["refresh_token"]),
                            "expires_at": time.time() + int(tokens.get("expires_in", 3600))})
            if "scope" in tokens:
                account["scopes"] = tokens["scope"].split()
            _save_private(self.data)
            return account["access_token"]

