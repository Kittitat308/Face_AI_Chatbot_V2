import unittest
from types import SimpleNamespace

from app.services.face_service import FaceScanResult
from app.services.face_service import (
    DETECTION_SIZE,
    DETECTION_THRESHOLD,
    FACE_MATCH_THRESHOLD,
    SWITCH_MATCH_THRESHOLD,
)
from app.services.presence_service import (
    LOGOUT_COUNTDOWN_SECONDS,
    MAX_MISSED_SCANS,
    MonitorAction,
    MonitorState,
    NORMAL_SCAN_INTERVAL,
    SessionMonitorState,
    SWITCH_CONFIRM_COUNT,
    SWITCH_VERIFY_INTERVAL,
    WARNING_SCAN_INTERVAL,
)


class PresenceStateTests(unittest.TestCase):
    def setUp(self):
        self.a = SimpleNamespace(id=1, display_name="A")
        self.b = SimpleNamespace(id=2, display_name="B")
        self.c = SimpleNamespace(id=3, display_name="C")
        self.state = SessionMonitorState(self.a.id)

    @staticmethod
    def result(face_count, current=False, user=None, unknown=False):
        return FaceScanResult(
            face_count,
            current,
            user,
            unknown_face_found=unknown,
        )

    def test_required_constants(self):
        self.assertEqual(NORMAL_SCAN_INTERVAL, 60000)
        self.assertEqual(WARNING_SCAN_INTERVAL, 1000)
        self.assertEqual(SWITCH_VERIFY_INTERVAL, 1000)
        self.assertEqual(MAX_MISSED_SCANS, 5)
        self.assertEqual(LOGOUT_COUNTDOWN_SECONDS, 5)
        self.assertEqual(SWITCH_CONFIRM_COUNT, 2)
        self.assertEqual(DETECTION_THRESHOLD, 0.45)
        self.assertEqual(FACE_MATCH_THRESHOLD, 0.50)
        self.assertEqual(SWITCH_MATCH_THRESHOLD, 0.55)
        self.assertEqual(DETECTION_SIZE, (640, 640))

    def test_case_1_current_alone_continues(self):
        decision = self.state.process(self.result(1, True, self.a))
        self.assertEqual(decision.action, MonitorAction.CONTINUE)

    def test_cases_2_and_3_current_has_priority_with_multiple_faces(self):
        for face_count in (2, 3):
            with self.subTest(face_count=face_count):
                decision = self.state.process(
                    self.result(face_count, True, self.a)
                )
                self.assertEqual(decision.action, MonitorAction.CONTINUE)
                self.assertEqual(self.state.miss_count, 0)

    def test_case_4_no_face_increments_miss_count(self):
        decision = self.state.process(self.result(0))
        self.assertEqual(decision.action, MonitorAction.NO_FACE)
        self.assertEqual(self.state.miss_count, 1)

    def test_case_5_five_no_face_scans_show_warning(self):
        decision = None
        for _ in range(MAX_MISSED_SCANS):
            decision = self.state.process(self.result(0))
        self.assertEqual(decision.action, MonitorAction.SHOW_WARNING)
        self.assertEqual(self.state.monitor_state, MonitorState.LOGOUT_WARNING)

    def test_case_6_current_return_cancels_warning(self):
        for _ in range(MAX_MISSED_SCANS):
            self.state.process(self.result(0))
        decision = self.state.process(self.result(1, True, self.a))
        self.assertEqual(decision.action, MonitorAction.CONTINUE)
        self.assertEqual(self.state.miss_count, 0)
        self.assertEqual(self.state.monitor_state, MonitorState.ACTIVE)

    def test_single_unknown_increments_miss_count(self):
        self.state.miss_count = 3
        decision = self.state.process(self.result(1, False, None))
        self.assertEqual(decision.action, MonitorAction.NO_FACE)
        self.assertEqual(self.state.miss_count, 4)

    def test_multiple_with_unknown_increments_miss_count(self):
        self.state.miss_count = 3
        decision = self.state.process(self.result(2, unknown=True))
        self.assertEqual(decision.action, MonitorAction.NO_FACE)
        self.assertEqual(self.state.miss_count, 4)

    def test_multiple_registered_others_log_out(self):
        self.state.miss_count = 3
        decision = self.state.process(self.result(2, unknown=False))
        self.assertEqual(decision.action, MonitorAction.LOGOUT_IMMEDIATELY)
        self.assertEqual(self.state.miss_count, 3)

    def test_case_10_same_other_user_twice_switches(self):
        first = self.state.process(self.result(1, False, self.b))
        second = self.state.process(self.result(1, False, self.b))
        self.assertEqual(first.action, MonitorAction.VERIFY_SWITCH)
        self.assertEqual(second.action, MonitorAction.SWITCH_USER)
        self.assertEqual(second.user.id, self.b.id)
        self.assertEqual(self.state.current_user_id, self.b.id)

    def test_case_11_current_return_cancels_switch(self):
        self.state.process(self.result(1, False, self.b))
        decision = self.state.process(self.result(1, True, self.a))
        self.assertEqual(decision.action, MonitorAction.CONTINUE)
        self.assertIsNone(self.state.switch_candidate)
        self.assertEqual(self.state.switch_confirm_count, 0)

    def test_case_12_different_candidate_does_not_switch(self):
        self.state.process(self.result(1, False, self.b))
        decision = self.state.process(self.result(1, False, self.c))
        self.assertEqual(decision.action, MonitorAction.VERIFY_SWITCH)
        self.assertEqual(self.state.switch_candidate.id, self.c.id)
        self.assertEqual(self.state.switch_confirm_count, 1)

    def test_no_face_during_verify_cancels_stale_candidate(self):
        self.state.process(self.result(1, False, self.b))
        decision = self.state.process(self.result(0))
        self.assertEqual(decision.action, MonitorAction.NO_FACE)
        self.assertIsNone(self.state.switch_candidate)
        self.assertEqual(self.state.switch_confirm_count, 0)
        self.assertEqual(self.state.miss_count, 1)

    def test_registered_other_can_switch_during_warning(self):
        for _ in range(MAX_MISSED_SCANS):
            self.state.process(self.result(0))
        first = self.state.process(self.result(1, False, self.b))
        second = self.state.process(self.result(1, False, self.b))
        self.assertEqual(first.action, MonitorAction.VERIFY_SWITCH)
        self.assertEqual(second.action, MonitorAction.SWITCH_USER)

    def test_unknown_during_warning_keeps_warning_and_increments(self):
        for _ in range(MAX_MISSED_SCANS):
            self.state.process(self.result(0))
        decision = self.state.process(self.result(1, False, None))
        self.assertEqual(decision.action, MonitorAction.SHOW_WARNING)
        self.assertEqual(
            self.state.monitor_state,
            MonitorState.LOGOUT_WARNING,
        )
        self.assertEqual(self.state.miss_count, MAX_MISSED_SCANS + 1)

    def test_multiple_with_unknown_during_warning_increments(self):
        for _ in range(MAX_MISSED_SCANS):
            self.state.process(self.result(0))
        decision = self.state.process(self.result(2, unknown=True))
        self.assertEqual(decision.action, MonitorAction.SHOW_WARNING)
        self.assertEqual(
            self.state.monitor_state,
            MonitorState.LOGOUT_WARNING,
        )
        self.assertEqual(self.state.miss_count, MAX_MISSED_SCANS + 1)


if __name__ == "__main__":
    unittest.main()
