import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

import auth as auth_module
from api import ChatApi
from ui import Panel
from i18n import system_language, tr


class FakeAuth(QObject):
    connected = pyqtSignal(str)
    failed = pyqtSignal(str)
    ready = False
    email = ""


class FakeApi(QObject):
    delta = pyqtSignal(str)
    completed = pyqtSignal(str)
    failed = pyqtSignal(str)
    models_ready = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.history = []
        self.busy = False
        self.model = "test-model"

    def send(self, *_args):
        pass

    def new_chat(self):
        self.history.clear()

    def fetch_models(self):
        pass


class QuickPaneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_new_chat_clears_context_and_previous_chat_can_be_restored(self):
        api = FakeApi()
        panel = Panel(FakeAuth(), api)
        panel.add_message("Question", True)
        panel.add_message("Answer", False)
        api.history = [{"role": "user", "content": "Question"}]

        panel.new_chat()

        self.assertEqual(api.history, [])
        self.assertTrue(panel.restore_button.isEnabled())
        panel.restore_last_chat()
        self.assertEqual([item["text"] for item in panel.current_messages], ["Question", "Answer"])
        panel.close()

    def test_response_can_be_copied(self):
        panel = Panel(FakeAuth(), FakeApi())
        panel.add_message("A test answer", False)

        panel.copy_answer()

        self.assertEqual(self.app.clipboard().text(), "A test answer")
        panel.close()

    def test_language_follows_system_locale_and_defaults_to_english(self):
        self.assertEqual(system_language("pt_BR"), "pt")
        self.assertEqual(system_language("pt-PT"), "pt")
        self.assertEqual(system_language("en_US"), "en")
        self.assertEqual(system_language("fr_FR"), "en")
        self.assertEqual(tr("Continuar com ChatGPT", "en"), "Continue with ChatGPT")
        self.assertEqual(tr("Continuar com ChatGPT", "pt"), "Continuar com ChatGPT")

    def test_oauth_session_is_written_with_owner_only_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            config = os.path.join(directory, "private-config")
            session = os.path.join(config, "session.json")
            with patch("auth.CONFIG_DIR", __import__("pathlib").Path(config)), \
                 patch("auth.SESSION_FILE", __import__("pathlib").Path(session)):
                auth_module._save_private({"test": "not-a-real-credential"})

            self.assertEqual(os.stat(config).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(session).st_mode & 0o777, 0o600)

    def test_responses_request_is_ephemeral_and_streamed(self):
        auth = Mock()
        auth.access_token.return_value = "test-token"
        api = ChatApi(auth)
        api.model = "test-model"
        fake_response = Mock()
        fake_response.iter_lines.return_value = [
            b'data: {"type":"response.output_text.delta","delta":"Hello"}',
            b'data: {"type":"response.completed"}',
        ]
        response_context = Mock()
        response_context.__enter__ = Mock(return_value=fake_response)
        response_context.__exit__ = Mock(return_value=False)
        with patch("api.requests.post", return_value=response_context) as post:
            api._send_worker([], {"role": "user", "content": [{"type": "input_text", "text": "Hi"}]})

        self.assertTrue(api.history)
        self.assertEqual(post.call_args.kwargs["json"]["store"], False)
        self.assertEqual(post.call_args.kwargs["json"]["stream"], True)


if __name__ == "__main__":
    unittest.main()
