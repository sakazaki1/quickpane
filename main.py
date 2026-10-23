"""Run the floating desktop panel."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QImage
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QFileDialog, QMenu, QSystemTrayIcon

from api import ChatApi
from auth import AuthManager
from i18n import tr
from ui import ASSETS, Panel


SOCKET_NAME = f"quickpane-{os.getuid()}"


def notify_existing(command: bytes = b"show\n") -> bool:
    socket = QLocalSocket()
    socket.connectToServer(SOCKET_NAME)
    if socket.waitForConnected(350):
        socket.write(command)
        socket.flush()
        socket.waitForBytesWritten(350)
        socket.disconnectFromServer()
        return True
    return False


class CaptureBridge(QObject):
    captured = pyqtSignal(QImage)
    failed = pyqtSignal(str)

    def capture(self):
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            with tempfile.TemporaryDirectory(prefix="quickpane-") as directory:
                path = Path(directory) / "screenshot.png"
                result = subprocess.run(
                    ["spectacle", "--region", "--background", "--nonotify", "--output", str(path)],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode or not path.exists():
                    raise RuntimeError(tr("Captura cancelada ou indisponível. Use Ctrl+V para colar um print."))
                image = QImage(str(path))
                if image.isNull():
                    raise RuntimeError(tr("Não foi possível abrir o print capturado."))
                self.captured.emit(image)
        except FileNotFoundError:
            self.failed.emit(tr("O Spectacle não está instalado. Cole um print com Ctrl+V."))
        except Exception as exc:
            self.failed.emit(str(exc))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("QuickPane")
    app.setDesktopFileName("quickpane")
    app.setWindowIcon(QIcon(str(ASSETS / "quickpane-icon.png")))
    app.setQuitOnLastWindowClosed(False)
    command = b"capture\n" if "--capture" in sys.argv else (b"toggle\n" if "--toggle" in sys.argv else b"show\n")
    if notify_existing(command):
        return 0

    auth = AuthManager()
    api = ChatApi(auth)
    panel = Panel(auth, api)
    bridge = CaptureBridge()
    bridge.captured.connect(panel.set_image)
    bridge.failed.connect(panel.show_error)

    def toggle():
        if panel.isVisible():
            panel.hide()
        else:
            panel.show(); panel.raise_(); panel.activateWindow(); panel.composer.setFocus()

    server = QLocalServer()
    QLocalServer.removeServer(SOCKET_NAME)
    if server.listen(SOCKET_NAME):
        def receive():
            while server.hasPendingConnections():
                client = server.nextPendingConnection()
                client.waitForReadyRead(300)
                request = bytes(client.readAll())
                if b"capture" in request:
                    capture()
                elif b"toggle" in request:
                    toggle()
                elif b"show" in request:
                    panel.show(); panel.raise_(); panel.activateWindow(); panel.composer.setFocus()
                client.disconnectFromServer()
        server.newConnection.connect(receive)

    def attach():
        path, _ = QFileDialog.getOpenFileName(panel, tr("Anexar print"), str(Path.home()),
                                              tr("Imagens (*.png *.jpg *.jpeg *.webp)"))
        if path:
            image = QImage(path)
            if image.isNull(): panel.show_error(tr("Esta imagem não pôde ser aberta."))
            else: panel.set_image(image)

    def capture():
        panel.hide()
        bridge.capture()

    panel.attach_requested.connect(attach)
    panel.capture_requested.connect(capture)
    bridge.captured.connect(lambda _image: panel.show())
    bridge.failed.connect(lambda _message: panel.show())
    panel.composer.pasted_image.connect(panel.set_image)

    tray = QSystemTrayIcon(app.windowIcon(), app)
    tray.setToolTip("QuickPane")
    menu = QMenu()
    menu.addAction(tr("Abrir ou ocultar"), toggle)
    menu.addAction(tr("Capturar print"), capture)
    menu.addSeparator()
    menu.addAction(tr("Sair"), app.quit)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: toggle() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray.show()

    panel.show()
    if command == b"capture\n":
        QTimer.singleShot(0, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
