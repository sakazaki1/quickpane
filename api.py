"""Streaming Responses API client. No ChatGPT credentials enter the UI layer."""

from __future__ import annotations

import json
import threading

import requests
from PyQt6.QtCore import QObject, pyqtSignal

from auth import AuthManager, RESOURCE


class ChatApi(QObject):
    delta = pyqtSignal(str)
    completed = pyqtSignal(str)
    failed = pyqtSignal(str)
    models_ready = pyqtSignal(list)

    def __init__(self, auth: AuthManager) -> None:
        super().__init__()
        self.auth = auth
        self.history: list[dict] = []
        self.model = ""
        self.busy = False

    def fetch_models(self) -> None:
        threading.Thread(target=self._fetch_models_worker, daemon=True).start()

    def _fetch_models_worker(self) -> None:
        try:
            token = self.auth.access_token()
            response = requests.get(f"{RESOURCE}/models", headers={"Authorization": f"Bearer {token}"}, timeout=25)
            response.raise_for_status()
            body = response.json()
            entries = body.get("models", body.get("data", []))
            models = [m for m in entries if m.get("visibility", "list") == "list"]
            if not models:
                raise RuntimeError("Nenhum modelo disponível para esta conta.")
            self.models_ready.emit(models)
        except Exception as exc:
            self.failed.emit(f"Não foi possível carregar os modelos: {exc}")

    def send(self, text: str, image_url: str | None = None) -> None:
        if self.busy:
            return
        if not self.model:
            self.failed.emit("Selecione um modelo antes de enviar.")
            return
        content: list[dict] = []
        if text.strip():
            content.append({"type": "input_text", "text": text.strip()})
        if image_url:
            content.append({"type": "input_image", "image_url": image_url})
        if not content:
            return
        self.busy = True
        user_item = {"role": "user", "content": content}
        context = self.history[-12:] + [user_item]
        threading.Thread(target=self._send_worker, args=(context, user_item), daemon=True).start()

    def _send_worker(self, context: list[dict], user_item: dict) -> None:
        chunks: list[str] = []
        completed = False
        try:
            token = self.auth.access_token()
            with requests.post(
                f"{RESOURCE}/responses",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"model": self.model, "input": context, "store": False, "stream": True},
                stream=True, timeout=(15, 180),
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines(decode_unicode=True):
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")
                    if not line or not line.startswith("data: "):
                        continue
                    try:
                        event = json.loads(line[6:])
                    except ValueError:
                        continue
                    kind = event.get("type")
                    if kind == "response.output_text.delta":
                        piece = event.get("delta", "")
                        chunks.append(piece)
                        self.delta.emit(piece)
                    elif kind == "response.completed":
                        completed = True
                    elif kind == "response.failed":
                        error = event.get("response", {}).get("error", {}) or {}
                        raise RuntimeError(error.get("message", "A resposta falhou."))
                    elif kind == "error":
                        raise RuntimeError(event.get("message", "Falha na conexão."))
            if not completed:
                raise RuntimeError("A conexão terminou sem confirmar a conclusão da resposta.")
            answer = "".join(chunks)
            self.history.extend([user_item, {"role": "assistant", "content": answer}])
            self.completed.emit(answer)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.busy = False

    def new_chat(self) -> None:
        if not self.busy:
            self.history.clear()
