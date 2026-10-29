#!/usr/bin/python3
"""Rounded X11 Fcitx5 Kimpanel frontend; release bus name to restore classicui."""
import argparse
import logging
import signal
import socket
import os
import sys
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from PyQt5 import QtCore, QtGui, QtWidgets

LOG = logging.getLogger(__name__)

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
        self.window.prev.setVisible(bool(prev))
        self.window.next.setVisible(bool(next_))

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
        self.words = []
        self.labels = []
        self.cursor = -1
        self.stable_width = 0
        self.lookup_visible = self.pre_visible = self.aux_visible = False
        self.buttons = []
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 18)
        self.card = QtWidgets.QFrame(objectName='card')
        outer.addWidget(self.card)
        self.card.setStyleSheet('''
            QFrame#card {background:#25282e; border-radius:12px;}
            QLabel {color:#bdc5d2; background:transparent; font:11pt "Noto Sans CJK SC";}
            QPushButton {color:#edf1f6; background:transparent; border:0;
                border-radius:7px; padding:6px 9px; font:13pt "Noto Sans CJK SC";}
            QPushButton:hover {background:#374039;}
            QPushButton[selected="true"] {background:#304c40; color:#a4efc3;}
        ''')
        shadow = QtWidgets.QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 3)
        shadow.setColor(QtGui.QColor(0, 0, 0, 85))
        self.card.setGraphicsEffect(shadow)
        box = QtWidgets.QVBoxLayout(self.card)
        box.setContentsMargins(9, 7, 9, 7)
        box.setSpacing(3)
        self.pre = QtWidgets.QLabel()
        self.aux = QtWidgets.QLabel()
        # Treat external input as plain text, never as HTML.
        self.pre.setTextFormat(QtCore.Qt.PlainText)
        self.aux.setTextFormat(QtCore.Qt.PlainText)
        box.addWidget(self.pre)
        box.addWidget(self.aux)
        self.row = QtWidgets.QHBoxLayout()
        self.row.setSpacing(2)
        box.addLayout(self.row)
        self.prev = self.make_button('‹', self.page_up.emit)
        self.next = self.make_button('›', self.page_down.emit)
        self.row.addWidget(self.prev)
        self.row.addWidget(self.next)
        self.prev.hide(); self.next.hide(); self.pre.hide(); self.aux.hide()
        self.fade = QtCore.QPropertyAnimation(self, b'windowOpacity', self)
        self.fade.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self.fade.finished.connect(self.finish_fade)
        self.target_visible = False
        self.flush_timer = QtCore.QTimer(self)
        self.flush_timer.setSingleShot(True)
        self.flush_timer.timeout.connect(self.flush)
        self.hide_timer = QtCore.QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.setInterval(24)
        self.hide_timer.timeout.connect(lambda: self.animate(False))

    def make_button(self, text, callback):
        button = QtWidgets.QPushButton(text)
        button.setFocusPolicy(QtCore.Qt.NoFocus)
        button.clicked.connect(lambda _checked=False: callback())
        return button

    def schedule(self):
        # Coalesce the protocol's text/visibility/position updates into one paint.
        if not self.flush_timer.isActive(): self.flush_timer.start(0)

    def set_spot(self, x, y):
        self.spot = QtCore.QPoint(x, y)
        self.schedule()

    def set_candidates(self, labels, words, cursor):
        self.words = [str(word) for word in words]
        self.labels = list(labels)
        self.cursor = cursor
        while len(self.buttons) < len(words):
            index = len(self.buttons)
            button = self.make_button('', lambda i=index: self.selected.emit(i))
            self.row.insertWidget(index, button)
            self.buttons.append(button)
        for i, button in enumerate(self.buttons):
            button.setVisible(i < len(words))
            if i >= len(words): continue
            text = f'{labels[i]}  {words[i]}' if i < len(labels) and labels[i] else str(words[i])
            if button.text() != text: button.setText(text)
            chosen = i == cursor
            if button.property('selected') != chosen:
                button.setProperty('selected', chosen)
                button.style().unpolish(button)
                button.style().polish(button)
        self.schedule()

    def flush(self):
        self.pre.setVisible(self.pre_visible and bool(self.pre.text()))
        self.aux.setVisible(self.aux_visible and bool(self.aux.text()))
        wanted = (self.lookup_visible and bool(self.words)) or (self.pre_visible and bool(self.pre.text())) or (self.aux_visible and bool(self.aux.text()))
        if wanted:
            self.hide_timer.stop()
            self.setMinimumWidth(self.stable_width)
            self.adjustSize()
            self.stable_width = max(self.stable_width, self.width())
            screen = QtWidgets.QApplication.screenAt(self.spot) or QtWidgets.QApplication.primaryScreen()
            rect = screen.availableGeometry()
            x = max(rect.left(), min(self.spot.x()-14, rect.right()-self.width()+1))
            y = self.spot.y()+3
            if y+self.height() > rect.bottom(): y = max(rect.top(), min(self.spot.y()-self.height()-20, rect.bottom()-self.height()+1))
            # Immediate tracking: interpolating cursor positions adds input lag.
            self.move(x, y)
            self.animate(True)
        elif self.target_visible and not self.hide_timer.isActive():
            self.hide_timer.start()

    def animate(self, show):
        if self.target_visible == show: return
        self.target_visible = show
        self.fade.stop()
        start = self.windowOpacity() if self.isVisible() else 0.
        if show and not self.isVisible():
            self.setWindowOpacity(0.)
            self.show()
        self.fade.setDuration(90 if show else 65)
        self.fade.setStartValue(start)
        self.fade.setEndValue(1. if show else 0.)
        self.fade.start()

    def finish_fade(self):
        if not self.target_visible:
            self.hide()
            self.stable_width = 0
            self.setMinimumWidth(0)

    def receive(self, *args, member=None):
        if member == 'UpdateSpotLocation': self.set_spot(int(args[0]), int(args[1]))
        elif member == 'UpdateLookupTable':
            self.set_candidates(args[0], args[1], self.cursor)
        elif member == 'UpdateLookupTableCursor':
            self.set_candidates(self.labels, self.words, int(args[0]))
        elif member == 'ShowLookupTable': self.lookup_visible = bool(args[0])
        elif member == 'UpdatePreeditText': self.pre.setText(str(args[0]))
        elif member == 'ShowPreedit': self.pre_visible = bool(args[0])
        elif member == 'UpdateAux': self.aux.setText(str(args[0]))
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
        window.pre.setText('jisuanji'); window.pre_visible = True
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
