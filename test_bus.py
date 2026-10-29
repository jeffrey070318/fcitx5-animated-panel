import os, subprocess, sys, time
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
bus=dbus.SessionBus()
p=subprocess.Popen(['/usr/bin/python3',sys.argv[1]], env={**os.environ,'QT_QPA_PLATFORM':'offscreen'})
try:
 for _ in range(60):
  if bus.name_has_owner('org.kde.impanel'): break
  if p.poll() is not None: raise RuntimeError('panel startup failed')
  time.sleep(.05)
 else: raise RuntimeError('bus name not acquired')
 obj=bus.get_object('org.kde.impanel','/org/kde/impanel')
 method=dbus.Interface(obj,'org.kde.impanel2')
 method.SetSpotRect(100,100,2,20)
 method.SetLookupTable(dbus.Array(['1','2'],signature='s'),dbus.Array(['你好','世界'],signature='s'),dbus.Array(['',''],signature='s'),False,True,1,0)
 print('PASS: live SetSpotRect and SetLookupTable method calls')
finally:
 p.terminate();p.wait(timeout=5)
 for _ in range(30):
  if not bus.name_has_owner('org.kde.impanel'): break
  time.sleep(.03)
 assert not bus.name_has_owner('org.kde.impanel'), 'bus name leaked'
 print('PASS: termination releases frontend ownership')
