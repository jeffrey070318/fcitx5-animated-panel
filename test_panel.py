"""Headless candidate window behavior tests."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PyQt5 import QtCore, QtTest, QtWidgets
from animated_panel import FrameClock, Window

class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self): self.w = Window()
    def tearDown(self): self.w.close()

    def compose(self):
        self.w.set_candidates(['1','2'], ['你好','拟好'], 1)
        self.w.lookup_visible = True
        self.w.flush()
        QtTest.QTest.qWait(130)

    def test_reuses_buttons_and_preserves_full_opacity(self):
        self.compose()
        button = self.w.buttons[0]
        self.w.set_candidates(['1','2'], ['您好','拟好'], 0)
        self.w.flush()
        self.assertIs(button, self.w.buttons[0])
        self.assertAlmostEqual(self.w.windowOpacity(), 1, places=2)
        self.assertFalse(self.w.buttons[1].property('selected'))

    def test_false_aux_does_not_hide_lookup(self):
        self.compose()
        self.w.receive(False, member='ShowAux')
        QtTest.QTest.qWait(40)
        self.assertTrue(self.w.target_visible)

    def test_fade_out_reversal(self):
        self.compose()
        self.w.lookup_visible = False; self.w.flush()
        QtTest.QTest.qWait(45)
        self.w.lookup_visible = True; self.w.flush()
        QtTest.QTest.qWait(130)
        self.assertTrue(self.w.isVisible())
        self.assertAlmostEqual(self.w.windowOpacity(), 1, places=2)

    def test_candidate_click_index(self):
        self.compose()
        chosen = []
        self.w.selected.connect(chosen.append)
        self.w.buttons[1].click()
        self.assertEqual(chosen, [1])

    def test_position_clamped(self):
        self.w.set_spot(100000,100000)
        self.compose()
        rect = self.app.primaryScreen().availableGeometry()
        self.assertTrue(rect.contains(self.w.geometry()))

    def test_empty_lookup_fades_away(self):
        self.compose()
        self.w.lookup_visible = False; self.w.flush()
        QtTest.QTest.qWait(175)
        self.assertFalse(self.w.isVisible())

    def test_growing_panel_has_intermediate_width_without_scaling_text(self):
        self.compose()
        start = self.w.width()
        font = self.w.buttons[0].font()
        self.w.set_candidates(['1','2'], ['计算机视觉系统','计算机科学与技术'], 0)
        self.w.flush()
        end = self.w.morph.endValue().width()
        self.assertGreater(end, start)
        self.assertEqual(self.w.width(), start)
        QtTest.QTest.qWait(50)
        self.assertGreater(self.w.width(), start)
        self.assertLess(self.w.width(), end)
        self.assertEqual(self.w.buttons[0].font(), font)
        QtTest.QTest.qWait(150)
        self.assertEqual(self.w.width(), end)

    def test_exit_retains_last_frame_instead_of_fading_empty_box(self):
        self.compose()
        text = self.w.buttons[0].text()
        self.w.set_candidates([], [], -1)
        self.w.receive(False, member='ShowLookupTable')
        self.w.flush()
        QtTest.QTest.qWait(45)
        self.assertTrue(self.w.isVisible())
        self.assertEqual(self.w.buttons[0].text(), text)
        self.assertFalse(self.w.buttons[0].isHidden())
        QtTest.QTest.qWait(140)
        self.assertFalse(self.w.isVisible())

    def test_shrink_waits_for_typing_pause_and_then_eases(self):
        self.w.set_candidates(['1','2'], ['计算机视觉系统','计算机科学与技术'], 0)
        self.w.lookup_visible = True; self.w.flush()
        QtTest.QTest.qWait(140)
        start = self.w.width()
        self.w.set_candidates(['1'], ['我'], 0); self.w.flush()
        QtTest.QTest.qWait(45)
        self.assertEqual(self.w.width(), start)
        QtTest.QTest.qWait(120)
        self.assertLess(self.w.width(), start)
        QtTest.QTest.qWait(160)
        self.assertEqual(self.w.width(), self.w._size_target.width())

    def test_caret_tracking_remains_immediate(self):
        self.compose()
        start = self.w.pos()
        self.w.set_spot(self.w.spot.x()+50, self.w.spot.y()+30)
        self.w.flush()
        self.assertEqual(self.w.pos()-start, QtCore.QPoint(50,30))

    def test_duplicate_spot_message_keeps_pending_caret_move(self):
        self.compose()
        start = self.w.pos()
        point = self.w.spot + QtCore.QPoint(50,30)
        self.w.set_spot(point.x(), point.y())
        self.w.set_spot(point.x(), point.y())
        self.w.flush()
        self.assertEqual(self.w.pos()-start, QtCore.QPoint(50,30))

    def test_animation_clock_stops_when_idle(self):
        self.assertFalse(self.w.frame_clock.timer.isActive())
        self.w.set_candidates(['1'], ['你好'], 0)
        self.w.lookup_visible = True; self.w.flush()
        self.assertTrue(self.w.frame_clock.timer.isActive())
        QtTest.QTest.qWait(160)
        self.assertFalse(self.w.frame_clock.timer.isActive())
        self.w.lookup_visible = False; self.w.flush()
        QtTest.QTest.qWait(180)
        self.assertFalse(self.w.frame_clock.timer.isActive())

    def test_animation_uses_elapsed_time_after_delayed_frame(self):
        self.w.fade.setStartValue(0.)
        self.w.fade.setEndValue(1.)
        self.w.fade.setDuration(100)
        finished = []
        self.w.fade.finished.connect(lambda: finished.append(True))
        self.w.fade.start()
        self.w.fade.advance(self.w.fade.started_at + 50)
        self.assertAlmostEqual(self.w.windowOpacity(), .875, delta=.01)
        self.w.fade.advance(self.w.fade.started_at + 250)
        self.assertAlmostEqual(self.w.windowOpacity(), 1.)
        self.assertEqual(finished, [True])
        self.assertFalse(self.w.frame_clock.timer.isActive())

    def test_identical_update_does_not_restart_geometry_animation(self):
        self.compose()
        self.w.set_candidates(['1'], ['计算机视觉与计算机科学'], 0); self.w.flush()
        QtTest.QTest.qWait(40)
        elapsed = self.w.morph.currentTime()
        self.w.flush()
        self.assertGreaterEqual(self.w.morph.currentTime(), elapsed)

    def test_preedit_clear_does_not_resurrect_stale_text(self):
        self.w.receive('nihao','',member='UpdatePreeditText')
        self.w.receive(True,member='ShowPreedit'); self.w.flush()
        QtTest.QTest.qWait(140)
        self.w.receive('','',member='UpdatePreeditText'); self.w.flush()
        QtTest.QTest.qWait(175)
        self.assertFalse(self.w.isVisible())

class ClockTests(unittest.TestCase):
    def test_screen_changes_and_refresh_rate_updates(self):
        class Screen(QtCore.QObject):
            refreshRateChanged = QtCore.pyqtSignal(float)
            def __init__(self, rate):
                super().__init__(); self.rate = rate
            def refreshRate(self): return self.rate
        clock = FrameClock()
        slow, fast = Screen(60.), Screen(240.)
        clock.set_screen(fast)
        self.assertEqual(clock.timer.interval(), 4)
        fast.refreshRateChanged.emit(144.)
        self.assertEqual(clock.timer.interval(), 7)
        clock.set_screen(slow)
        self.assertEqual(clock.timer.interval(), 17)
        fast.refreshRateChanged.emit(240.)
        self.assertEqual(clock.timer.interval(), 17)
        self.assertFalse(clock.timer.isActive())

    def test_invalid_refresh_rate_falls_back_to_60(self):
        clock = FrameClock()
        for rate in (0., -1., float('nan'), float('inf')):
            clock.set_refresh_rate(rate)
            self.assertEqual(clock.refresh_rate, 60.)
            self.assertEqual(clock.timer.interval(), 17)

if __name__ == '__main__': unittest.main()
