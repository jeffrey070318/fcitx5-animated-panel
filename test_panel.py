"""Headless candidate window behavior tests."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PyQt5 import QtCore, QtTest, QtWidgets
from animated_panel import Window

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
        QtTest.QTest.qWait(130)
        self.assertFalse(self.w.isVisible())

if __name__ == '__main__': unittest.main()
