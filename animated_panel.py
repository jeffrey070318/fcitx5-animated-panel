#!/usr/bin/python3
"""Experimental X11 Fcitx5 Kimpanel frontend. Exit to restore classicui."""
import sys
import logging
import dbus, dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from PyQt5 import QtCore, QtGui, QtWidgets

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

class PanelBus(dbus.service.Object):
    @dbus.service.signal('org.kde.kimpanel.panel', signature='')
    def PanelCreated(self): pass
    @dbus.service.signal('org.kde.kimpanel.panel', signature='i')
    def SelectCandidate(self, index): pass
    @dbus.service.signal('org.kde.kimpanel.panel', signature='')
    def LookupTablePageUp(self): pass
    @dbus.service.signal('org.kde.kimpanel.panel', signature='')
    def LookupTablePageDown(self): pass

class Window(QtWidgets.QWidget):
    def __init__(self):
        super().__init__(None, QtCore.Qt.ToolTip | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.outer=QtWidgets.QVBoxLayout(self); self.outer.setContentsMargins(12,12,12,14)
        self.card=QtWidgets.QFrame(); self.card.setObjectName('card'); self.outer.addWidget(self.card)
        self.card.setStyleSheet('QFrame#card { background:#25272c; border-radius:12px; } QLabel {color:#bfc5cf; background:transparent;} QPushButton { color:#eceff4; background:transparent; border:0; border-radius:7px; padding:7px 10px; font:13pt "Noto Sans CJK SC"; } QPushButton:hover {background:#3a414b;} QPushButton[selected="true"] {background:#304d43; color:#8de3b5;}')
        sh=QtWidgets.QGraphicsDropShadowEffect(self.card);sh.setBlurRadius(22);sh.setOffset(0,3);sh.setColor(QtGui.QColor(0,0,0,90));self.card.setGraphicsEffect(sh)
        self.layout=QtWidgets.QVBoxLayout(self.card);self.layout.setContentsMargins(10,8,10,8);self.layout.setSpacing(5)
        self.pre=QtWidgets.QLabel(); self.pre.setFont(QtGui.QFont('Noto Sans CJK SC',11));self.layout.addWidget(self.pre); self.pre.hide()
        self.row=QtWidgets.QHBoxLayout();self.row.setSpacing(3); self.layout.addLayout(self.row)
        self.anim=QtCore.QPropertyAnimation(self,b'windowOpacity');self.anim.setDuration(110);self.anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self.spot=QtCore.QPoint(100,100);self.labels=[];self.words=[];self.selected=0
    def position(self):
        self.adjustSize(); screen=QtWidgets.QApplication.screenAt(self.spot) or QtWidgets.QApplication.primaryScreen(); r=screen.availableGeometry()
        x=max(r.left(),min(self.spot.x()-12,r.right()-self.width())); y=self.spot.y()+4
        if y+self.height()>r.bottom(): y=max(r.top(),self.spot.y()-self.height()-24)
        self.move(x,y)
    def reveal(self,on):
        if not on: self.anim.stop();self.hide();return
        self.position()
        if not self.isVisible():
            self.setWindowOpacity(0);self.show();self.anim.setStartValue(0.);self.anim.setEndValue(1.);self.anim.start()
    def update_words(self,labels,words,attrs):
        self.labels=list(labels);self.words=list(words)
        while self.row.count():
            item=self.row.takeAt(0);item.widget().deleteLater()
        for i,word in enumerate(words):
            b=QtWidgets.QPushButton(f'{labels[i] if i<len(labels) else i+1}  {word}');b.setFocusPolicy(QtCore.Qt.NoFocus)
            attr=str(attrs[i]) if i<len(attrs) else ''
            b.setProperty('selected', i==self.selected or 'highlight' in attr.lower())
            b.clicked.connect(lambda _,j=i: endpoint.SelectCandidate(j));self.row.addWidget(b)
        self.position()
    def receive(self,*args,member=None,**kw):
        logging.debug('%s %r', member, args)
        if member=='UpdateSpotLocation': self.spot=QtCore.QPoint(int(args[0]),int(args[1]));self.position()
        elif member=='UpdateLookupTable':
            self.update_words(list(args[0]), list(args[1]), list(args[2]))
        elif member=='ShowLookupTable': self.reveal(bool(args[0]) and bool(self.words))
        elif member=='UpdatePreeditText': self.pre.setText(str(args[0]));self.position()
        elif member=='ShowPreedit': self.pre.setVisible(bool(args[0]));self.position()
        elif member in ('Hide','ExecDialog','ShowAux'): self.reveal(False)

app=QtWidgets.QApplication(sys.argv);app.setQuitOnLastWindowClosed(False)
w=Window()
if '--preview' in sys.argv:
    w.pre.setText('jisuanji'); w.pre.show();w.update_words(['1','2','3'],['计算机','计算机视觉','计算机科学'],[]);w.reveal(True)
else:
    DBusGMainLoop(set_as_default=True);bus=dbus.SessionBus()
    bus.add_signal_receiver(w.receive,dbus_interface='org.kde.kimpanel.inputmethod',member_keyword='member')
    name=dbus.service.BusName('org.kde.impanel',bus,do_not_queue=True)
    endpoint=PanelBus(bus,'/org/kde/impanel');endpoint.PanelCreated()
    timer=QtCore.QTimer();timer.timeout.connect(lambda: GLib.MainContext.default().iteration(False));timer.start(5)
sys.exit(app.exec_())
