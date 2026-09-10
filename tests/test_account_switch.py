import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.presence_service import SessionMonitorState
from app.ui.main_window import MainWindow


class AccountSwitchTests(unittest.TestCase):
    def test_switch_reuses_chat_ui_and_updates_monitor_identity(self):
        current = SimpleNamespace(id=1)
        target = SimpleNamespace(id=2)
        fake_window = SimpleNamespace(
            current_user=current,
            session_monitor_state=SessionMonitorState(current.id),
            presence_monitor=SimpleNamespace(
                set_current_user=MagicMock(),
                set_interval=MagicMock(),
            ),
            cancel_logout_warning=MagicMock(),
            update_profile_button=MagicMock(),
            load_chats=MagicMock(),
        )
        with patch("app.ui.main_window.get_user", return_value=target), patch(
            "app.ui.main_window.FaceService.update_cached_user"
        ):
            MainWindow.switch_current_user(fake_window, target)

        self.assertIs(fake_window.current_user, target)
        self.assertEqual(fake_window.session_monitor_state.current_user_id, target.id)
        fake_window.presence_monitor.set_current_user.assert_called_once_with(target.id)
        fake_window.update_profile_button.assert_called_once()
        fake_window.load_chats.assert_called_once()


if __name__ == "__main__":
    unittest.main()
