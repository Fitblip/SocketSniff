import sys
import functools
import traceback

from Queue import Queue
from threading import currentThread

from PyQt4 import QtCore, QtGui

import envi.threads as e_threads

def idlethread(func):
    '''
    A decorator which causes the function to be called by the qt
    main thread rather than synchronously...

    NOTE: This makes the call async handled by the qt main
    loop code.  you can NOT return anything.
    '''
    def idleadd(*args, **kwargs):

        if iAmQtSafeThread():
            return func(*args, **kwargs)

        guiq.append( (func, args, kwargs) )

    functools.update_wrapper(idleadd,func)
    return idleadd

def workthread(func):
    '''
    Proxy a call through the single vqt.main worker thread
    (who exists to keep the GUI from blocking on stuff... )
    '''
    # If we're already the work thread, just do it.
    def workadd(*args, **kwargs):
        if getattr(currentThread(),'VQtWorkerThread',False):
            return func(*args, **kwargs)

        workerq.append( (func,args,kwargs) )

    functools.update_wrapper(workadd,func)
    return workadd

def boredthread(func):
    '''
    The same as "workthread" above, but drop the request on the
    floor if the worker thread already has better things to do...
    '''
    # If we're already the work thread, just do it.
    def workadd(*args, **kwargs):
        if getattr(currentThread(),'VQtWorkerThread',False):
            return func(*args, **kwargs)

        if not len(workerq):
            workerq.append( (func,args,kwargs) )

    functools.update_wrapper(workadd,func)
    return workadd

def idlethreadsync(func):
    '''
    Similar to idlethread except that it is synchronous and able
    to return values.
    '''
    q = Queue()
    def dowork(*args, **kwargs):
        try:
            q.put(func(*args, **kwargs))
        except Exception, e:
            q.put(e)

    def idleadd(*args, **kwargs):
        if iAmQtSafeThread():
            return func(*args, **kwargs)

        guiq.append( (dowork, args, kwargs) )
        return q.get()

    functools.update_wrapper(idleadd,func)
    return idleadd

def iAmQtSafeThread():
    return getattr(currentThread(),'QtSafeThread',False)

class QEventThread(QtCore.QThread):
    '''
    A thread who exists to consume callback requests from the
    given workq and fire them into Qt *safely*.
    '''
    idleadd = QtCore.pyqtSignal(object,object,object)

    def __init__(self, workq):
        QtCore.QThread.__init__(self)
        self.workq = workq

    def run(self):
        while True:
            try:

                todo = self.workq.get()
                if todo == None:
                    continue

                func,args,kwargs = todo
                if func == None:
                    return

                self.idleadd.emit(func,args,kwargs)

            except Exception, e:
                print('vqt event thread: %s' % e)

class VQApplication(QtGui.QApplication):

    guievents = QtCore.pyqtSignal(str,object)

    def __init__(self, *args, **kwargs):
        QtGui.QApplication.__init__(self, *args, **kwargs)
        self.vqtchans = {}

    def callFromQtLoop(self, callback, args, kwargs):
        callback(*args,**kwargs)

class QEventChannel(QtCore.QObject):
    guievents = QtCore.pyqtSignal(str,object)

@e_threads.firethread
def workerThread():
    # We are *not* allowed to make Qt API calls
    currentThread().VQtWorkerThread = True
    while True:
        try:
            todo = workerq.get()
            if todo != None:
                func,args,kwargs = todo

                if func == None:
                    return

                func(*args,**kwargs)

        except Exception, e:
            print('vqt worker warning: %s' % e)


def startup(css=None):
    # yea yea.... globals suck...
    global qapp     # the main QApplication
    global guiq     # queue of GUI calls to proxy
    global ethread  # QtThread that consumes guiq
    global workerq  # queue of "worker" calls to proxy

    guiq = e_threads.Queue()
    workerq = e_threads.Queue()

    currentThread().QtSafeThread = True
    qapp = VQApplication(sys.argv)
    if css:
        qapp.setStyleSheet( css )

    ethread = QEventThread(guiq)
    ethread.idleadd.connect( qapp.callFromQtLoop )
    ethread.start()

    workerThread()

def main():
    global qapp

    if not iAmQtSafeThread():
        raise Exception('main() must be called by same thread as startup()!')

    qapp.exec_()

def eatevents():
    global qapp
    qapp.processEvents()

def vqtevent(event,einfo):
    '''
    Fire an event into the application wide GUI events subsystem.
    Each event should be an event name ( str ) and arbitrary event
    info context.
    '''
    global qapp
    qapp.guievents.emit(event,einfo)
    chan = qapp.vqtchans.get(event)
    if chan != None:
        chan.guievents.emit(event,einfo)

def vqtconnect(callback, event=None):
    '''
    Connect to the application wide "gui events" which has
    a callback syntax:
        callback(event,einfo)

    Optionally specify an event name to only recieve events
    of the specified type.
    '''
    global qapp
    if event == None:
        qapp.guievents.connect( callback )
        return
        
    chan = qapp.vqtchans.get(event)
    if chan == None:
        chan = QEventChannel()
        qapp.vqtchans[event] = chan

    chan.guievents.connect(callback)

def vqtdisconnect(callback, event=None):
    '''
    Connect to the application wide "gui events" which has
    a callback syntax:
        callback(event,einfo)

    Optionally specify an event name to only recieve events
    of the specified type.
    '''
    global qapp
    if event == None:
        qapp.guievents.disconnect( callback )
        return
        
    chan = qapp.vqtchans.get(event)
    if chan != None:
        chan.guievents.disconnect(callback)

