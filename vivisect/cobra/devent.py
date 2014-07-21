'''
Cobra Distributed Event subsystem.
'''
import json
import Queue
import socket
import struct
import itertools
import threading
import collections

# FIXME add chan timeout teardown

class CobraEventCore:

    def __init__(self):
        self._ce_chanids = itertools.count()

        self._ce_chans = []
        self._ce_mcastport = None
        self._ce_mcasthost = None
        self._ce_ecastsock = None
        self._ce_chanlookup = {}

    def initEventChannel(self, qmax=0):
        '''
        Create a new channel id and allocate an
        event Queue.
        '''
        chanid = self._ce_chanids.next()
        q = Queue.Queue(maxsize=qmax)
        self._ce_chans.append( q )
        self._ce_chanlookup[ chanid ] = q
        return chanid

    def finiEventChannel(self, chanid):
        '''
        Close the specified event channel by adding a
        (None,None) event and removing the channel's
        Queue object.
        '''
        q = self._ce_chanlookup.pop( chanid )
        q.put((None,None))
        self._ce_chans.remove( q )

    def finiEventChannels(self):
        '''
        Close down all event channels by adding a (None,None)
        event and removing the event Q from the datastructs.
        '''
        [ self.finiEventChannel( chanid ) for chanid in self._ce_chanlookup.keys() ]

    def getNextEventForChan(self, chanid, timeout=None):
        '''
        Get the next event for a previously initialized
        event channel.  If "timeout" is specified, the
        call will return None after the timeout interval.
        Each returned event is a tuple of ( eventname, eventinfo ).

        When the channel returns (None, None) it has closed.
        '''
        q = self._ce_chanlookup.get( chanid )
        try:
            return q.get(timeout=timeout)
        except Queue.Empty:
            return None

    def fireEvent(self, event, einfo):
        '''
        Fire an even into the event distribution system.
        '''
        etup = (event,einfo)
        # Speed hack
        [ q.put( etup ) for q in self._ce_chans ]

        if self._ce_ecastsock:
            self._ce_ecastsock.sendto( json.dumps( etup ), (self._ce_mcasthost, self._ce_mcastport))

    def addEventCallback(self, callback, qmax=0, firethread=True):
        '''
        Create a new event channel and fire a thread which
        listens for events and hands them off to the function
        "callback"

        def mycallback(event, einfo):
            dostuff()

        evt = CobraEventCore()
        evt.addEventCallback( mycallback )

        NOTE: This API is *not* cobra proxy call safe.
        '''
        if firethread:
            thr = threading.Thread(target=self.addEventCallback, args=(callback, qmax, False))
            thr.setDaemon(True)
            thr.start()
            return

        chanid = self.initEventChannel(qmax=qmax)
        q = self._ce_chanlookup.get( chanid )
        while True:

            event,einfo = q.get()
            if event == None:
                break

            try:
                callback(event,einfo)
            except Exception, e:
                print('Event Callback Exception (chan: %d): %s' % (chanid,e))

    def setEventCast(self, mcast='224.56.56.56', port=45654, bind='0.0.0.0'):
        '''
        Tie this CobraEventCore to any others which share the same multicast
        ip and port.  This basically creates a ( udp "unreliable" ) "bus" on
        which events are serialized using json.
        '''
        # Setup a UDP casting socket
        self._ce_mcastport = port
        self._ce_mcasthost = mcast
        self._ce_ecastsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._ce_ecastsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._ce_ecastsock.bind((bind,port))

        # Join the multicast IP
        mreq = struct.pack("4sL", socket.inet_aton(mcast), socket.INADDR_ANY)
        self._ce_ecastsock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        thr = threading.Thread(target=self._runSocketListener)
        thr.setDaemon(True)
        thr.start()

    def _runSocketListener(self):
        sock = self._ce_ecastsock
        while True:
            sockdata,sockaddr = sock.recvfrom(4096)
            etup = json.loads(sockdata)
            [ q.put( etup ) for q in self._ce_chans ]

if __name__ == '__main__':

    ecore = CobraEventCore()

    chan = ecore.initEventChannel()
    print('Channel: %d' % chan)

    #ecore.setEventCast(bind='192.168.1.2')
    ecore.setEventCast(bind='192.168.1.117')
    ecore.fireEvent('woot',('some','woot','info'))

    while True:
        print 'GOT',ecore.getNextEventForChan( chan )

