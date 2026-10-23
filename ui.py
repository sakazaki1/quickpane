"""Floating glass-like panel inspired by the approved second concept."""

from __future__ import annotations

import base64
import time
from pathlib import Path

from PyQt6.QtCore import QAbstractAnimation, QByteArray, QBuffer, QEasingCurve, QIODevice, QPoint, QSettings, QSize, Qt, QTimer, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QImage, QKeyEvent, QKeySequence, QPainter, QPainterPath, QPen, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton,
    QScrollArea, QTextEdit, QVBoxLayout, QWidget,
)

from api import ChatApi
from auth import AuthManager
from i18n import tr


ASSETS = Path(__file__).resolve().parent / "assets"


class StatusDot(QWidget):
    def __init__(self, color: str = "#f7b527", pulse: bool = False):
        super().__init__()
        self.setFixedSize(36, 36)
        self.color = QColor(color)
        self.pulse = pulse
        self.phase = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        if pulse:
            self.timer.start(55)

    def set_state(self, color: str, pulse: bool):
        self.color = QColor(color)
        self.pulse = pulse
        if pulse:
            self.timer.start(55)
        else:
            self.timer.stop()
        self.update()

    def tick(self):
        self.phase = (self.phase + 1) % 28
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        alpha = 32 + (20 * abs(14 - self.phase) // 14 if self.pulse else 0)
        glow = QColor(self.color)
        glow.setAlpha(alpha)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(1, 1, 34, 34)
        glow.setAlpha(85)
        painter.setBrush(glow)
        painter.drawEllipse(6, 6, 24, 24)
        painter.setBrush(self.color)
        painter.drawEllipse(11, 11, 14, 14)


class GlyphButton(QPushButton):
    def __init__(self, glyph: str, tooltip: str = "", color: str = "#e5e8eb"):
        super().__init__()
        self.glyph = glyph
        self.glyph_color = QColor(color)
        self.setToolTip(tr(tooltip))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(34, 34)
        self.setObjectName("glyphButton")

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.underMouse():
            p.setBrush(QColor(255, 255, 255, 23))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 9, 9)
        p.setPen(QPen(self.glyph_color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if self.glyph == "close":
            p.drawLine(12, 12, 22, 22); p.drawLine(22, 12, 12, 22)
        elif self.glyph == "min":
            p.drawLine(12, 17, 22, 17)
        elif self.glyph == "send":
            path = QPainterPath(); path.moveTo(8, 17); path.lineTo(25, 9); path.lineTo(19, 25); path.lineTo(16, 19); path.closeSubpath()
            p.drawPath(path); p.drawLine(16, 19, 25, 9)
        elif self.glyph == "capture":
            for x, y, dx, dy in [(9, 9, 6, 0), (9, 9, 0, 6), (25, 9, -6, 0), (25, 9, 0, 6),
                                 (9, 25, 6, 0), (9, 25, 0, -6), (25, 25, -6, 0), (25, 25, 0, -6)]:
                p.drawLine(x, y, x + dx, y + dy)
        elif self.glyph == "attach":
            path = QPainterPath(); path.moveTo(11, 21); path.cubicTo(7, 17, 11, 13, 14, 10)
            path.cubicTo(19, 5, 25, 10, 22, 14); path.lineTo(16, 21)
            path.cubicTo(13, 24, 10, 20, 13, 17); path.lineTo(18, 12)
            p.drawPath(path)
        elif self.glyph == "menu":
            for x in (11, 17, 23): p.drawEllipse(x - 1, 16, 2, 2)
        elif self.glyph == "chat":
            p.drawRoundedRect(9, 10, 16, 12, 5, 5)
            p.drawLine(13, 22, 12, 25); p.drawLine(12, 25, 17, 22)
        elif self.glyph == "clock":
            p.drawEllipse(9, 9, 16, 16); p.drawLine(17, 17, 17, 12); p.drawLine(17, 17, 21, 19)
        elif self.glyph == "resize":
            p.drawRoundedRect(10, 10, 14, 14, 2, 2)
            p.drawLine(17, 10, 17, 15); p.drawLine(10, 17, 15, 17)
        elif self.glyph == "help":
            p.setFont(self.font())
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "?")


class DragHeader(QFrame):
    """Lets KWin perform the drag on Wayland; falls back to manual movement."""

    def __init__(self):
        super().__init__()
        self._offset = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is None or not handle.startSystemMove():
                self._offset = event.globalPosition().toPoint() - self.window().pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._offset = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)


class Composer(QTextEdit):
    submit = pyqtSignal()
    pasted_image = pyqtSignal(QImage)

    def __init__(self):
        super().__init__()
        self.setPlaceholderText(tr("Digite ou cole um print..."))
        self.setFixedHeight(58)
        self.setAcceptRichText(False)
        self.setObjectName("composer")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.submit.emit(); return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        if source.hasImage():
            image = QApplication.clipboard().image()
            if not image.isNull():
                self.pasted_image.emit(image)
                return
        super().insertFromMimeData(source)


class DashboardPreview(QWidget):
    """Small illustrative print in the empty state; replaced by the user's real print."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(198)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = self.rect().adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(255, 255, 255, 34), 1))
        p.setBrush(QColor(255, 255, 255, 11))
        p.drawRoundedRect(outer, 14, 14)
        page = outer.adjusted(27, 22, -27, -22)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#ecf0f3"))
        p.drawRoundedRect(page, 8, 8)
        p.setBrush(QColor("#dce3e8"))
        p.drawRoundedRect(page.x() + 9, page.y() + 9, 65, page.height() - 18, 5, 5)
        p.setBrush(QColor("#bac8d3"))
        for index in range(4):
            p.drawRoundedRect(page.x() + 20, page.y() + 27 + index * 23, 43, 5, 2, 2)
        chart_x = page.x() + 94
        chart_y = page.y() + 31
        p.setPen(QColor("#43515e"))
        p.drawText(chart_x, chart_y - 9, "Relatórios")
        p.setPen(QPen(QColor("#d0d9e0"), 1))
        p.drawLine(chart_x, page.bottom() - 25, page.right() - 15, page.bottom() - 25)
        bars = [34, 49, 62, 54, 78, 91]
        width = max(15, (page.right() - chart_x - 37) // 10)
        for index, height in enumerate(bars):
            p.setBrush(QColor("#6296d6" if index < 5 else "#edaa34"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(chart_x + 9 + index * (width + 9), page.bottom() - 25 - height,
                              width, height, 3, 3)


def image_data_url(image: QImage) -> str:
    array = QByteArray()
    buffer = QBuffer(array)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(bytes(array)).decode()


class Panel(QWidget):
    COMPACT_SIZE = (430, 470)
    EXPANDED_SIZE = (544, 750)

    def __init__(self, auth: AuthManager, api: ChatApi):
        super().__init__()
        self.auth, self.api = auth, api
        self.pending_image: QImage | None = None
        self.reply_label: QLabel | None = None
        self.reply_text = ""
        self.current_messages: list[dict] = []
        self.last_chat: dict | None = None
        self.reply_index: int | None = None
        self.last_activity = time.monotonic()
        self.settings = QSettings("Painel Chat", "Painel Chat")
        self.idle_minutes = int(self.settings.value("new_chat_after_minutes", 15))
        self.expanded = False
        self.resize_animation = QVariantAnimation(self)
        self.resize_animation.setDuration(250)
        self.resize_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.resize_animation.valueChanged.connect(self._animate_size)
        self.collapse_timer = QTimer(self)
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(lambda: self.set_expanded(False))
        self.setWindowTitle("QuickPane")
        self.setWindowIcon(QIcon(str(ASSETS / "quickpane-icon.png")))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(*self.COMPACT_SIZE)
        self.build()
        self.apply_style()
        self.position_right()
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_chat)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self.copy_answer)
        auth.connected.connect(self.on_connected)
        auth.failed.connect(self.show_error)
        api.delta.connect(self.on_delta)
        api.completed.connect(self.on_complete)
        api.failed.connect(self.show_error)
        api.models_ready.connect(self.on_models)
        if auth.ready:
            self.account_label.setText(auth.email)
            self.login_button.setText(tr("Conta conectada"))
            api.fetch_models()

    def position_right(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 18, screen.top() + max(24, (screen.height() - self.height()) // 2))

    def _label(self, text: str, name: str = "") -> QLabel:
        label = QLabel(tr(text))
        label.setObjectName(name)
        label.setWordWrap(True)
        return label

    def build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(5)
        card = QFrame(); card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(13)
        root.addWidget(card, 1)
        rail = QFrame(); rail.setObjectName("rail"); rail.setFixedWidth(51)
        rail_layout = QVBoxLayout(rail); rail_layout.setContentsMargins(7, 17, 7, 14); rail_layout.setSpacing(9)
        self.rail_dot = StatusDot("#f7b527", False); rail_layout.addWidget(self.rail_dot)
        self.rail_status = self._label("Pronto", "railStatus"); self.rail_status.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        rail_layout.addWidget(self.rail_status)
        rail_layout.addSpacing(16)
        chat_button = GlyphButton("chat", "Conversa"); chat_button.clicked.connect(lambda: self.composer.setFocus())
        rail_layout.addWidget(chat_button)
        rail_layout.addStretch()
        help_button = GlyphButton("help", "Ações e atalhos")
        help_button.clicked.connect(lambda: self.show_help(help_button))
        rail_layout.addWidget(help_button)
        root.addWidget(rail)

        drag_header = DragHeader()
        drag_header.setObjectName("dragHeader")
        header = QHBoxLayout(drag_header); header.setContentsMargins(0, 0, 0, 0); header.setSpacing(3)
        title = self._label("Chat rápido", "title")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        header.addWidget(title, 1)
        self.new_chat_button = QPushButton(tr("+ Novo chat"))
        self.new_chat_button.setObjectName("newChatButton")
        self.new_chat_button.setToolTip(tr("Nova conversa sem o contexto anterior · Ctrl+N"))
        self.new_chat_button.clicked.connect(self.new_chat)
        header.addWidget(self.new_chat_button)
        size_button = GlyphButton("resize", "Expandir ou reduzir")
        size_button.clicked.connect(lambda: self.set_expanded(not self.expanded))
        min_button = GlyphButton("min", "Ocultar"); min_button.clicked.connect(self.hide)
        close_button = GlyphButton("close", "Sair"); close_button.clicked.connect(QApplication.quit)
        header.addWidget(size_button); header.addWidget(min_button); header.addWidget(close_button)
        card_layout.addWidget(drag_header)

        self.account_label = self._label("Seu painel de acesso rápido", "subtle")
        card_layout.addWidget(self.account_label)
        self.login_button = QPushButton(tr("Continuar com ChatGPT"))
        self.login_button.setObjectName("loginButton")
        self.login_button.clicked.connect(self.on_login)
        card_layout.addWidget(self.login_button)

        self.model_picker = QComboBox(); self.model_picker.setObjectName("modelPicker")
        self.model_picker.addItem(tr("Modelo · conecte sua conta"))
        self.model_picker.currentIndexChanged.connect(self.on_model_changed)
        card_layout.addWidget(self.model_picker)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("scroll")
        self.messages_widget = QWidget(); self.messages_widget.setObjectName("messages")
        self.messages = QVBoxLayout(self.messages_widget)
        self.messages.setSpacing(13); self.messages.setContentsMargins(0, 0, 2, 0)
        self.empty = self.make_empty_state(); self.messages.addWidget(self.empty)
        self.messages.addStretch()
        scroll.setWidget(self.messages_widget)
        self.scroll = scroll
        card_layout.addWidget(scroll, 1)

        self.status_card = QFrame(); self.status_card.setObjectName("statusCard")
        status_layout = QHBoxLayout(self.status_card); status_layout.setContentsMargins(10, 7, 10, 7)
        self.status_dot = StatusDot("#f7b527", False); status_layout.addWidget(self.status_dot)
        status_texts = QVBoxLayout(); status_texts.setSpacing(0)
        self.status_title = self._label("Pronto para começar", "statusTitle")
        self.status_detail = self._label("Envie uma mensagem ou um print", "statusDetail")
        status_texts.addWidget(self.status_title); status_texts.addWidget(self.status_detail)
        status_layout.addLayout(status_texts, 1)
        card_layout.addWidget(self.status_card)

        actions = QHBoxLayout(); actions.setSpacing(7)
        self.restore_button = QPushButton(tr("↶  Último chat"))
        self.restore_button.setObjectName("secondaryAction")
        self.restore_button.setToolTip(tr("Reabrir a conversa anterior desta sessão"))
        self.restore_button.setEnabled(False)
        self.restore_button.clicked.connect(self.restore_last_chat)
        actions.addWidget(self.restore_button)
        self.copy_button = QPushButton(tr("⧉  Copiar resposta"))
        self.copy_button.setObjectName("secondaryAction")
        self.copy_button.setToolTip(tr("Copiar a última resposta · Ctrl+Shift+C"))
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_answer)
        actions.addWidget(self.copy_button)
        card_layout.addLayout(actions)

        self.preview_frame = QFrame(); self.preview_frame.setObjectName("previewFrame")
        preview_layout = QHBoxLayout(self.preview_frame); preview_layout.setContentsMargins(10, 8, 10, 8)
        self.preview_image = QLabel(); self.preview_image.setFixedSize(62, 44); self.preview_image.setScaledContents(True)
        preview_layout.addWidget(self.preview_image)
        preview_layout.addWidget(self._label("Print anexado", "previewTitle"), 1)
        remove_button = GlyphButton("close", "Remover print"); remove_button.clicked.connect(self.remove_image)
        preview_layout.addWidget(remove_button)
        self.preview_frame.hide(); card_layout.addWidget(self.preview_frame)

        attach_row = QHBoxLayout(); attach_row.setSpacing(8)
        self.capture_button = QPushButton(tr("▣   Cole um print ou clique para capturar"))
        self.capture_button.setObjectName("captureBox")
        self.capture_button.clicked.connect(self.capture_requested.emit)
        attach_row.addWidget(self.capture_button)
        card_layout.addLayout(attach_row)

        compose_frame = QFrame(); compose_frame.setObjectName("composeFrame")
        compose_layout = QHBoxLayout(compose_frame); compose_layout.setContentsMargins(8, 6, 7, 6); compose_layout.setSpacing(2)
        attach_button = GlyphButton("attach", "Anexar imagem")
        attach_button.clicked.connect(self.attach_requested.emit)
        compose_layout.addWidget(attach_button)
        self.composer = Composer(); self.composer.submit.connect(self.send)
        compose_layout.addWidget(self.composer, 1)
        capture_button = GlyphButton("capture", "Capturar uma área")
        capture_button.clicked.connect(self.capture_requested.emit)
        compose_layout.addWidget(capture_button)
        self.send_button = GlyphButton("send", "Enviar · Ctrl+Enter", "#172027")
        self.send_button.setObjectName("sendButton")
        self.send_button.clicked.connect(self.send)
        compose_layout.addWidget(self.send_button)
        card_layout.addWidget(compose_frame)


    attach_requested = pyqtSignal()
    capture_requested = pyqtSignal()

    def make_empty_state(self) -> QWidget:
        wrapper = QWidget(); layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(4, 3, 4, 4); layout.setSpacing(8)
        self.empty_intro = self._label("Envie texto ou print", "emptyTitle")
        layout.addWidget(self.empty_intro)
        self.empty_description = self._label("Capture a tela ou escreva sua pergunta. A resposta aparece aqui enquanto é gerada.", "emptyText")
        self.empty_description.setVisible(self.expanded)
        layout.addWidget(self.empty_description)
        self.empty_visual = DashboardPreview()
        self.empty_visual.setVisible(self.expanded)
        layout.addWidget(self.empty_visual)
        layout.addStretch()
        return wrapper

    def apply_style(self):
        self.setStyleSheet("""
            QWidget { color: #eef0f2; font-family: 'Inter', 'Noto Sans', sans-serif; font-size: 13px; }
            #card { background: rgba(25, 29, 34, 188); border: 1px solid rgba(255,255,255,67); border-radius: 18px; }
            #rail { background: rgba(41, 36, 33, 170); border: 1px solid rgba(255,255,255,52); border-radius: 17px; }
            #title { color: #fff; font-size: 18px; font-weight: 700; }
            #subtle { color: #bec4ca; font-size: 12px; }
            #railStatus { color: #ffc35b; font-size: 10px; font-weight: 700; }
            #newChatButton { background: rgba(255,255,255,19); border: 1px solid rgba(255,255,255,57); border-radius: 8px; padding: 6px 8px; color: #f1f3f5; font-size: 12px; font-weight: 600; }
            #newChatButton:hover { background: rgba(255,255,255,36); }
            #newChatButton:disabled { color: #80868d; border-color: rgba(255,255,255,23); }
            #loginButton { background: rgba(249,185,56,25); border: 1px solid rgba(255,193,76,92); border-radius: 9px; padding: 9px; color: #ffd485; font-weight: 600; }
            #loginButton:hover { background: rgba(249,185,56,45); }
            #modelPicker { background: rgba(255,255,255,12); border: 1px solid rgba(255,255,255,31); border-radius: 8px; padding: 7px; color: #d9dde1; }
            #modelPicker QAbstractItemView { background: #292b2f; color: white; selection-background-color: #69563c; }
            #scroll, #messages { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 6px; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,54); border-radius: 3px; }
            #emptyTitle { font-size: 15px; font-weight: 600; }
            #emptyText { color: #aeb4bc; line-height: 1.4; }
            #statusCard { background: rgba(91,75,40,72); border: 1px solid rgba(249,184,49,90); border-radius: 12px; }
            #statusTitle { font-size: 13px; font-weight: 700; color: #ffc349; }
            #statusDetail { font-size: 12px; color: #d4cbc0; }
            #secondaryAction { background: rgba(255,255,255,15); border: 1px solid rgba(255,255,255,35); border-radius: 8px; padding: 6px 7px; font-size: 11px; color: #dfe3e6; }
            #secondaryAction:hover { background: rgba(255,255,255,33); }
            #secondaryAction:disabled { color: #797f85; border-color: rgba(255,255,255,15); }
            #previewFrame { background: rgba(255,255,255,18); border: 1px solid rgba(255,255,255,43); border-radius: 11px; }
            #previewTitle { font-weight: 600; }
            #captureBox { text-align: left; background: rgba(255,255,255,10); border: 1px dashed rgba(255,255,255,62); border-radius: 10px; padding: 13px 9px; color: #d4d9de; font-size: 12px; }
            #captureBox:hover { background: rgba(255,255,255,24); }
            #composeFrame { background: rgba(255,255,255,15); border: 1px solid rgba(255,255,255,67); border-radius: 12px; }
            #composer { background: transparent; border: none; color: #f4f5f6; selection-background-color: #966b29; }
            #sendButton { background: #f5b42e; border-radius: 9px; }
            #messageUser { background: rgba(255,255,255,26); border: 1px solid rgba(255,255,255,27); border-radius: 13px; padding: 11px; }
            #messageAssistant { background: rgba(34,43,43,170); border: 1px solid rgba(91,166,134,56); border-radius: 13px; padding: 11px; }
            #messageImage { border-radius: 8px; }
        """)

    def on_login(self):
        self.login_button.setText(tr("Aguardando autorização no navegador..."))
        self.auth.sign_in()

    def on_connected(self, email: str):
        self.account_label.setText(email)
        self.login_button.setText(tr("Conta conectada"))
        self.set_status("Pronto", "Conta conectada", "#42d17d", False)
        self.api.fetch_models()

    def on_models(self, models: list):
        self.model_picker.blockSignals(True)
        self.model_picker.clear()
        for model in models:
            slug = model.get("slug", model.get("id", ""))
            if slug:
                self.model_picker.addItem(model.get("display_name", slug), slug)
        preferred = self.model_picker.findData("gpt-6.1-sol")
        self.model_picker.setCurrentIndex(max(preferred, 0))
        self.model_picker.blockSignals(False)
        self.on_model_changed()

    def on_model_changed(self):
        self.api.model = self.model_picker.currentData() or ""

    def set_status(self, title: str, detail: str, color: str, pulse: bool):
        title, detail = tr(title), tr(detail)
        self.status_title.setText(title); self.status_detail.setText(detail)
        self.status_title.setStyleSheet(f"color: {color};")
        self.status_dot.set_state(color, pulse); self.rail_dot.set_state(color, pulse)
        rail_label = tr({"Working...": "Ativo", "Completed": "Feito", "Error": "Erro"}.get(title, "Pronto"))
        self.rail_status.setText(rail_label)
        self.rail_status.setToolTip(f"{title}: {detail}")
        self.rail_status.setStyleSheet(f"color: {color};")

    def set_image(self, image: QImage):
        if image.isNull():
            return
        self.pending_image = image
        pix = QPixmap.fromImage(image).scaled(62, 44, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        self.preview_image.setPixmap(pix)
        self.preview_frame.show()

    def remove_image(self):
        self.pending_image = None
        self.preview_frame.hide()

    def add_message(self, text: str, mine: bool, image: QImage | None = None) -> QLabel:
        if self.empty:
            self.empty.hide()
        frame = QFrame(); frame.setObjectName("messageUser" if mine else "messageAssistant")
        layout = QVBoxLayout(frame); layout.setContentsMargins(11, 9, 11, 9); layout.setSpacing(7)
        label = self._label("Você" if mine else "Chat rápido", "messageWho")
        label.setStyleSheet("color: #f9bc47; font-weight: 700;" if not mine else "color: #d4d9df; font-weight: 700;")
        layout.addWidget(label)
        if image is not None:
            preview = QLabel(); preview.setObjectName("messageImage")
            preview.setPixmap(QPixmap.fromImage(image).scaledToWidth(365, Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(preview)
        body = self._label(text or "", "messageBody")
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(body)
        self.messages.insertWidget(self.messages.count() - 1, frame)
        self.current_messages.append({"text": text, "mine": mine, "image": image.copy() if image is not None else None})
        QTimer.singleShot(0, self.scroll_bottom)
        return body

    def scroll_bottom(self):
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def send(self):
        if self.api.busy:
            return
        text = self.composer.toPlainText().strip()
        image = self.pending_image
        if not text and image is None:
            return
        if not self.auth.ready:
            self.show_error("Conecte sua conta ChatGPT para enviar.")
            return
        if not self.api.model:
            self.show_error("Aguarde a lista de modelos ou selecione um modelo.")
            return
        if self.current_messages and self.idle_minutes and time.monotonic() - self.last_activity >= self.idle_minutes * 60:
            self._start_new_chat(clear_draft=False, detail="Novo chat após período de inatividade")
        self.add_message(text or "Print anexado", True, image)
        self.composer.clear(); self.remove_image()
        self.reply_text = ""
        self.reply_label = self.add_message("", False)
        self.reply_index = len(self.current_messages) - 1
        self.last_activity = time.monotonic()
        self.set_status("Executando...", "Preparando sua resposta", "#f7b527", True)
        self.new_chat_button.setEnabled(False)
        self.restore_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.api.send(text, image_data_url(image) if image is not None else None)

    def on_delta(self, piece: str):
        if not self.expanded:
            self.set_expanded(True)
        self.reply_text += piece
        if self.reply_label:
            self.reply_label.setText(self.reply_text)
        if self.reply_index is not None:
            self.current_messages[self.reply_index]["text"] = self.reply_text
        self.scroll_bottom()

    def on_complete(self, _answer: str):
        self.new_chat_button.setEnabled(True)
        self.restore_button.setEnabled(self.last_chat is not None)
        self.copy_button.setEnabled(bool(self.reply_text))
        self.last_activity = time.monotonic()
        self.set_status("Concluído", "Resposta pronta", "#3ee073", True)
        self.collapse_timer.start(20000)
        QApplication.alert(self, 0)

    def show_error(self, message: str):
        self.new_chat_button.setEnabled(True)
        self.restore_button.setEnabled(self.last_chat is not None)
        self.copy_button.setEnabled(bool(self._latest_answer()))
        self.collapse_timer.stop()
        message = tr(message)
        self.set_status("Erro", message, "#f47172", False)
        self.login_button.setText(tr("Continuar com ChatGPT") if not self.auth.ready else tr("Conta conectada"))
        if self.reply_label and not self.reply_text:
            error_text = f"{tr('Não foi possível concluir: ')}{message}"
            self.reply_label.setText(error_text)
            if self.reply_index is not None:
                self.current_messages[self.reply_index]["text"] = error_text

    def new_chat(self):
        if self.api.busy:
            self.set_status("Executando...", "Aguarde esta resposta para iniciar outra conversa", "#f7b527", True)
            return
        self._start_new_chat(clear_draft=True, detail="Novo chat sem contexto anterior")

    def _snapshot(self) -> dict:
        return {"messages": [dict(item) for item in self.current_messages], "history": list(self.api.history)}

    def _clear_messages(self):
        self.reply_label = None
        self.reply_text = ""
        self.reply_index = None
        self.current_messages.clear()
        while self.messages.count() > 1:
            item = self.messages.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.empty = self.make_empty_state()
        self.messages.insertWidget(0, self.empty)

    def _start_new_chat(self, clear_draft: bool, detail: str):
        if self.current_messages:
            self.last_chat = self._snapshot()
            self.restore_button.setEnabled(True)
        self.api.new_chat()
        if clear_draft:
            self.composer.clear()
            self.remove_image()
        self._clear_messages()
        self.copy_button.setEnabled(False)
        self.collapse_timer.stop()
        self.last_activity = time.monotonic()
        self.set_status("Pronto", detail, "#42d17d", False)
        self.set_expanded(False)
        self.composer.setFocus()

    def restore_last_chat(self):
        if self.api.busy or self.last_chat is None:
            return
        previous = self.last_chat
        self.last_chat = self._snapshot() if self.current_messages else None
        self.api.history = list(previous["history"])
        self._clear_messages()
        for item in previous["messages"]:
            self.add_message(item["text"], item["mine"], item["image"])
        self.restore_button.setEnabled(self.last_chat is not None)
        self.copy_button.setEnabled(bool(self._latest_answer()))
        self.last_activity = time.monotonic()
        self.set_status("Pronto", "Conversa anterior reaberta", "#42d17d", False)

    def _latest_answer(self) -> str:
        for item in reversed(self.current_messages):
            if not item["mine"] and not item["text"].startswith("Não foi possível concluir:"):
                return item["text"]
        return ""

    def copy_answer(self):
        answer = self._latest_answer()
        if answer:
            QApplication.clipboard().setText(answer)
            self.status_detail.setText(tr("Resposta copiada"))

    def show_help(self, source: QWidget):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background: #262b30; color: #f2f4f6; border: 1px solid #59616b; padding: 6px; } QMenu::item { padding: 7px 14px; } QMenu::item:selected { background: #4b5159; }")
        menu.addSection(tr("Ações"))
        menu.addAction(tr("Novo chat   Ctrl+N"), self.new_chat)
        restore = menu.addAction(tr("Reabrir último chat"), self.restore_last_chat)
        restore.setEnabled(self.last_chat is not None and not self.api.busy)
        copy = menu.addAction(tr("Copiar resposta   Ctrl+Shift+C"), self.copy_answer)
        copy.setEnabled(bool(self._latest_answer()))
        idle_menu = menu.addMenu(tr("Novo chat após inatividade"))
        for minutes, label in ((5, "5 minutos"), (15, "15 minutos"), (30, "30 minutos"), (0, "Nunca")):
            action = idle_menu.addAction(tr(label))
            action.setCheckable(True)
            action.setChecked(self.idle_minutes == minutes)
            action.triggered.connect(lambda _checked=False, value=minutes: self.set_idle_minutes(value))
        menu.addAction(tr("Capturar área"), self.capture_requested.emit)
        menu.addAction(tr("Anexar imagem"), self.attach_requested.emit)
        menu.addSection(tr("Atalhos"))
        for hint in ("Ctrl+V   Colar print", "Ctrl+Enter   Enviar", "Esc   Ocultar janela"):
            item = menu.addAction(tr(hint))
            item.setEnabled(False)
        menu.popup(source.mapToGlobal(QPoint(-205, -150)))
        self.help_menu = menu

    def set_idle_minutes(self, minutes: int):
        self.idle_minutes = minutes
        self.settings.setValue("new_chat_after_minutes", minutes)

    def set_expanded(self, expanded: bool):
        self.collapse_timer.stop()
        if self.expanded == expanded and self.resize_animation.state() != QAbstractAnimation.State.Running:
            return
        self.resize_animation.stop()
        self.expanded = expanded
        if hasattr(self, "empty_visual"):
            self.empty_visual.setVisible(expanded and self.empty.isVisible())
            self.empty_description.setVisible(expanded and self.empty.isVisible())
        self._anchor_right = self.x() + self.width()
        self._anchor_top = self.y()
        self.resize_animation.setStartValue(QSize(self.width(), self.height()))
        self.resize_animation.setEndValue(QSize(*(self.EXPANDED_SIZE if expanded else self.COMPACT_SIZE)))
        self.resize_animation.start()

    def _animate_size(self, size):
        width, height = size.width(), size.height()
        screen = self.screen().availableGeometry()
        self.setFixedSize(width, height)
        x = max(screen.left(), min(self._anchor_right - width, screen.right() - width + 1))
        y = max(screen.top(), min(self._anchor_top, screen.bottom() - height + 1))
        self.move(x, y)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide(); return
        super().keyPressEvent(event)
