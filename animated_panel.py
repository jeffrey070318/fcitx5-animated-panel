#!/usr/bin/python3
"""Rounded X11 Fcitx5 Kimpanel frontend; release bus name to restore classicui."""
import argparse
import logging
import math
import signal
import socket
import os
import sys
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from PyQt5 import QtCore, QtGui, QtWidgets

LOG = logging.getLogger(__name__)

class FrameClock(QtCore.QObject):
    """One elapsed-time clock for all active transitions; idle between them."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.elapsed = QtCore.QElapsedTimer()
        self.elapsed.start()
        self.animations = set()
        self.screen = None
        self.timer = QtCore.QTimer(self)
        self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.timer.timeout.connect(self.advance)
        self.set_refresh_rate(60.)

    def set_refresh_rate(self, rate):
        rate = float(rate)
        self.refresh_rate = rate if math.isfinite(rate) and rate >= 24 else 60.
        self.timer.setInterval(max(1, round(1000. / self.refresh_rate)))

    def set_screen(self, screen):
        if screen is self.screen: return
        if self.screen is not None:
            self.screen.refreshRateChanged.disconnect(self.set_refresh_rate)
        self.screen = screen
        self.set_refresh_rate(screen.refreshRate() if screen else 60.)
        if screen is not None:
            screen.refreshRateChanged.connect(self.set_refresh_rate)

    def add(self, animation):
        self.animations.add(animation)
        if not self.timer.isActive(): self.timer.start()

    def remove(self, animation):
        self.animations.discard(animation)
        if not self.animations: self.timer.stop()

    def advance(self):
        now = self.elapsed.elapsed()
        for animation in tuple(self.animations):
            if animation in self.animations: animation.advance(now)


class FrameAnimation(QtCore.QVariantAnimation):
    """Use Qt interpolation/easing without Qt5's default animation timer."""
    def __init__(self, target, property_name, clock):
        super().__init__(target)
        self.target = target
        self.property_name = property_name
        self.clock = clock
        self.running = False
        self.valueChanged.connect(lambda value: target.setProperty(property_name, value))

    def state(self):
        return self.Running if self.running else self.Stopped

    def start(self):
        self.stop()
        self.started_at = self.clock.elapsed.elapsed()
        self.setCurrentTime(0)
        self.target.setProperty(self.property_name, self.currentValue())
        self.running = True
        self.clock.add(self)

    def stop(self):
        self.running = False
        self.clock.remove(self)

    def advance(self, now):
        self.setCurrentTime(min(self.duration(), now - self.started_at))
        if self.currentTime() >= self.duration():
            self.stop()
            self.finished.emit()


class PanelBus(dbus.service.Object):
    def __init__(self, bus, window):
        super().__init__(bus, '/org/kde/impanel')
        self.window = window

    @dbus.service.signal('org.kde.impanel', signature='')
    def PanelCreated(self): pass

    @dbus.service.signal('org.kde.impanel', signature='i')
    def SelectCandidate(self, index): pass

    @dbus.service.signal('org.kde.impanel', signature='')
    def LookupTablePageUp(self): pass

    @dbus.service.signal('org.kde.impanel', signature='')
    def LookupTablePageDown(self): pass

    @dbus.service.method('org.kde.impanel2', in_signature='asasasbbii', out_signature='')
    def SetLookupTable(self, labels, words, attrs, prev, next_, cursor, layout):
        self.window.set_candidates(labels, words, int(cursor))
        self.window.has_prev = bool(prev)
        self.window.has_next = bool(next_)

    @dbus.service.method('org.kde.impanel2', in_signature='iiii', out_signature='')
    def SetSpotRect(self, x, y, width, height):
        self.window.set_spot(int(x), int(y) + int(height))

class Window(QtWidgets.QWidget):
    selected = QtCore.pyqtSignal(int)
    page_up = QtCore.pyqtSignal()
    page_down = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__(None, QtCore.Qt.ToolTip | QtCore.Qt.FramelessWindowHint |
                         QtCore.Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.spot = QtCore.QPoint(160, 160)
        self.words, self.labels = [], []
        self.cursor = -1
        self.lookup_visible = self.pre_visible = self.aux_visible = False
        self.has_prev = self.has_next = False
        self.pre_text = self.aux_text = ''
        self.buttons = []
        self.target_visible = False
        self._offset = 0.
        self._size_target = QtCore.QSize()
        self._shrink_size = None
        self._spot_changed = False
        self.card = QtWidgets.QFrame(self, objectName='card')
        self.card.setStyleSheet('''
            QFrame#card {background:#25282e; border-radius:12px;}
            QLabel {color:#bdc5d2; background:transparent; font:11pt "Noto Sans CJK SC";}
            QPushButton {color:#edf1f6; background:transparent; border:0;
                border-radius:7px; padding:6px 9px; font:13pt "Noto Sans CJK SC";}
            QPushButton:hover {background:#374039;}
            QPushButton[selected="true"] {background:#304c40; color:#a4efc3;}
        ''')
        # Absolute child geometry keeps glyphs at native size while the panel
        # expands around them. No layout compression or text scaling per frame.
        self.pre = QtWidgets.QLabel(self.card)
        self.aux = QtWidgets.QLabel(self.card)
        for label in (self.pre, self.aux): label.setTextFormat(QtCore.Qt.PlainText)
        self.prev = self.make_button('‹', self.page_up.emit)
        self.next = self.make_button('›', self.page_down.emit)
        self.prev.hide(); self.next.hide(); self.pre.hide(); self.aux.hide()
        self.frame_clock = FrameClock(self)
        self.frame_clock.set_screen(QtWidgets.QApplication.primaryScreen())
        self.fade = FrameAnimation(self, 'windowOpacity', self.frame_clock)
        self.fade.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self.fade.finished.connect(self.finish_fade)
        self.lift = FrameAnimation(self, 'revealOffset', self.frame_clock)
        self.lift.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self.morph = FrameAnimation(self, 'geometry', self.frame_clock)
        self.morph.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self.flush_timer = QtCore.QTimer(self)
        self.flush_timer.setSingleShot(True)
        self.flush_timer.timeout.connect(self.flush)
        self.hide_timer = QtCore.QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.setInterval(24)
        self.hide_timer.timeout.connect(lambda: self.animate(False))
        self.shrink_timer = QtCore.QTimer(self)
        self.shrink_timer.setSingleShot(True)
        self.shrink_timer.setInterval(90)
        self.shrink_timer.timeout.connect(self.shrink)

    @QtCore.pyqtProperty(float)
    def revealOffset(self): return self._offset

    @revealOffset.setter
    def revealOffset(self, value):
        self._offset = value
        self.place_card()

    def place_card(self):
        self.card.setGeometry(14, 12 + round(self._offset),
                              max(1, self.width()-28), max(1, self.height()-30))
        self.update()

    def resizeEvent(self, event):
        self.place_card()
        super().resizeEvent(event)

    def paintEvent(self, event):
        # Cheap shadow rings, independent of the text subtree. Avoid Gaussian
        # re-rasterization of every glyph on each animated resize.
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setBrush(QtCore.Qt.NoBrush)
        base = QtCore.QRectF(self.card.geometry()).translated(0, 3)
        for spread in range(10, 0, -1):
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 2 + (10-spread)), 1.5))
            painter.drawRoundedRect(base.adjusted(-spread, -spread, spread, spread),
                                    12+spread, 12+spread)

    def make_button(self, text, callback):
        button = QtWidgets.QPushButton(text, self.card)
        button.setFocusPolicy(QtCore.Qt.NoFocus)
        button.clicked.connect(lambda _checked=False: callback())
        return button

    def schedule(self):
        if not self.flush_timer.isActive(): self.flush_timer.start(0)

    def set_spot(self, x, y):
        point = QtCore.QPoint(x, y)
        self._spot_changed = self._spot_changed or point != self.spot
        self.spot = point
        screen = QtWidgets.QApplication.screenAt(point) or QtWidgets.QApplication.primaryScreen()
        self.frame_clock.set_screen(screen)
        self.schedule()

    def set_candidates(self, labels, words, cursor):
        self.words = [str(word) for word in words]
        self.labels = list(labels)
        self.cursor = cursor
        self.schedule()

    def layout_contents(self):
        """Update only for visible content; retain the previous frame on exit."""
        y, content_width = 7, 0
        for label, text, visible in ((self.pre, self.pre_text, self.pre_visible),
                                     (self.aux, self.aux_text, self.aux_visible)):
            label.setText(text)
            label.setVisible(visible and bool(text))
            if visible and text:
                size = label.sizeHint()
                label.setGeometry(9, y, size.width(), size.height())
                y += size.height() + 3
                content_width = max(content_width, size.width())
        active_words = self.words if self.lookup_visible else []
        while len(self.buttons) < len(active_words):
            index = len(self.buttons)
            self.buttons.append(self.make_button('', lambda i=index: self.selected.emit(i)))
        x, row_height = 9, 0
        for i, button in enumerate(self.buttons):
            button.setVisible(i < len(active_words))
            if i >= len(active_words): continue
            text = f'{self.labels[i]}  {active_words[i]}' if i < len(self.labels) and self.labels[i] else active_words[i]
            if text != button.text(): button.setText(text)
            chosen = i == self.cursor
            if button.property('selected') != chosen:
                button.setProperty('selected', chosen)
                button.style().unpolish(button); button.style().polish(button)
            size = button.sizeHint()
            button.setGeometry(x, y, size.width(), size.height())
            x += size.width() + 2
            row_height = max(row_height, size.height())
        for button, visible in ((self.prev, self.has_prev), (self.next, self.has_next)):
            button.setVisible(visible and self.lookup_visible)
            if visible and self.lookup_visible:
                size = button.sizeHint(); button.setGeometry(x, y, size.width(), size.height())
                x += size.width()+2; row_height = max(row_height, size.height())
        content_width = max(content_width, x-9)
        screen = QtWidgets.QApplication.screenAt(self.spot) or QtWidgets.QApplication.primaryScreen()
        return QtCore.QSize(min(content_width+46, screen.availableGeometry().width()),
                            y+row_height+7+30)

    def placement(self, size):
        screen = QtWidgets.QApplication.screenAt(self.spot) or QtWidgets.QApplication.primaryScreen()
        rect = screen.availableGeometry()
        x = max(rect.left(), min(self.spot.x()-14, rect.right()-size.width()+1))
        y = self.spot.y()+3
        if y+size.height() > rect.bottom():
            y = max(rect.top(), min(self.spot.y()-size.height()-20, rect.bottom()-size.height()+1))
        return QtCore.QRect(QtCore.QPoint(x, y), size)

    def resize_to(self, size):
        destination = self.placement(size)
        if self.morph.state() == QtCore.QAbstractAnimation.Running and self.morph.endValue() == destination:
            return
        self.morph.stop()
        self._size_target = QtCore.QSize(size)
        if not self.isVisible(): self.setGeometry(destination); return
        if self.geometry() == destination: return
        self.morph.setStartValue(self.geometry())
        self.morph.setEndValue(destination)
        self.morph.setDuration(135 if size.width() >= self.width() else 155)
        self.morph.start()

    def shrink(self):
        if self._shrink_size is not None and self.target_visible:
            self.resize_to(self._shrink_size)
        self._shrink_size = None

    def flush(self):
        wanted = (self.lookup_visible and bool(self.words)) or (self.pre_visible and bool(self.pre_text)) or (self.aux_visible and bool(self.aux_text))
        if wanted:
            self.hide_timer.stop()
            desired = self.layout_contents()
            if self._spot_changed:
                # Follow the real caret immediately, independent of size easing.
                self.morph.stop()
                if self.isVisible(): self.setGeometry(self.placement(self.size()))
                self._spot_changed = False
            if self.isVisible() and desired.width() < self.width():
                if self._shrink_size != desired:
                    self._shrink_size = desired; self.shrink_timer.start()
            else:
                self.shrink_timer.stop(); self._shrink_size = None
                self.resize_to(desired)
            self.animate(True)
        elif self.target_visible and not self.hide_timer.isActive():
            # Do not clear labels/buttons before the exit animation finishes.
            self.shrink_timer.stop(); self._shrink_size = None
            self.hide_timer.start()

    def animate(self, show):
        if self.target_visible == show: return
        self.target_visible = show
        self.fade.stop(); self.lift.stop()
        opacity = self.windowOpacity() if self.isVisible() else 0.
        if show and not self.isVisible():
            self.revealOffset = 3.
            self.setWindowOpacity(0.)
            self.show()
        # Scale duration by remaining opacity to avoid pauses when reversing.
        duration = max(35, round((115 if show else 100) * abs((1. if show else 0.)-opacity)))
        self.fade.setDuration(duration)
        self.fade.setStartValue(opacity)
        self.fade.setEndValue(1. if show else 0.)
        self.lift.setDuration(duration)
        self.lift.setStartValue(self.revealOffset)
        self.lift.setEndValue(0. if show else 2.)
        self.lift.start(); self.fade.start()

    def finish_fade(self):
        if not self.target_visible:
            self.hide(); self.morph.stop(); self.shrink_timer.stop()
            self._shrink_size = None

    def receive(self, *args, member=None):
        if member == 'UpdateSpotLocation': self.set_spot(int(args[0]), int(args[1]))
        elif member == 'UpdateLookupTable': self.set_candidates(args[0], args[1], self.cursor)
        elif member == 'UpdateLookupTableCursor': self.set_candidates(self.labels, self.words, int(args[0]))
        elif member == 'ShowLookupTable': self.lookup_visible = bool(args[0])
        elif member == 'UpdatePreeditText': self.pre_text = str(args[0])
        elif member == 'ShowPreedit': self.pre_visible = bool(args[0])
        elif member == 'UpdateAux': self.aux_text = str(args[0])
        elif member == 'ShowAux': self.aux_visible = bool(args[0])
        elif member == 'Enable' and not args[0]:
            self.lookup_visible = self.pre_visible = self.aux_visible = False
        self.schedule()

def notify(message):
    address = os.environ.get('NOTIFY_SOCKET')
    if not address: return
    if address.startswith('@'): address = '\0' + address[1:]
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
        sock.connect(address)
        sock.sendall(message.encode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--render', metavar='PNG')
    args = parser.parse_args()
    DBusGMainLoop(set_as_default=True)
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    # Ubuntu's Qt uses QEventDispatcherGlib: D-Bus shares its main context.
    # Refuse unsupported dispatchers instead of silently dropping input events.
    if not (args.preview or args.render) and 'Glib' not in app.eventDispatcher().metaObject().className():
        raise RuntimeError('This build requires Qt GLib event integration')
    window = Window()
    if args.preview or args.render:
        window.pre_text = 'jisuanji'; window.pre_visible = True
        window.set_candidates(['1','2','3'], ['计算机','计算机视觉','计算机科学'], 0)
        window.lookup_visible = True; window.flush()
        if args.render:
            app.processEvents(); window.grab().save(args.render); return 0
    else:
        bus = dbus.SessionBus()
        # Do not take over from an existing panel.
        name = dbus.service.BusName('org.kde.impanel', bus, do_not_queue=True)
        endpoint = PanelBus(bus, window)
        window.selected.connect(endpoint.SelectCandidate)
        window.page_up.connect(endpoint.LookupTablePageUp)
        window.page_down.connect(endpoint.LookupTablePageDown)
        bus.add_signal_receiver(window.receive, dbus_interface='org.kde.kimpanel.inputmethod',
                                bus_name='org.kde.kimpanel.inputmethod', member_keyword='member')
        endpoint.PanelCreated()
        notify('READY=1')
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    heartbeat = QtCore.QTimer()
    heartbeat.timeout.connect(lambda: notify('WATCHDOG=1'))
    heartbeat.start(1000)
    return app.exec_()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
