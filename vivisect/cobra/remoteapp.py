'''
A utility for creating "remote applications" which are dcode
enabled and cobra driven.  All API arguments/returns *must* be
serializable using msgpack.

NOTE: enabling a dcode server means source for local python modules
      will be delivered directly to clients over the network!

Running a remote application will also attempt to prefer code from
the server rather than the local python current working directory.
( and uses multiprocessing for import/process isolation )
'''
import os
import sys
import optparse
import importlib
import subprocess
import multiprocessing

import cobra
import cobra.dcode

class RemoteAppServer:
    pass

def shareRemoteApp(name, appsrv=None, daemon=None):
    '''
    Fire an appropriate dcode enabled cobra daemon and share
    the appsrv object with the given name.
    '''
    if appsrv == None:
        appsrv = RemoteAppServer()

    if daemon == None:
        daemon = cobra.CobraDaemon(msgpack=True)
        daemon.fireThread()

    cobra.dcode.enableDcodeServer(daemon=daemon)
    return daemon.shareObject(appsrv, name)

def _getAndRunApp(uri):
    # We dont want our *local* code, we want the remote code.
    cwd = os.getcwd()
    if cwd in sys.path:
        sys.path.remove(cwd)
    if '' in sys.path:
        sys.path.remove('')

    duri = cobra.swapCobraObject(uri, 'DcodeServer')
    cobra.dcode.addDcodeUri(duri)

    server = cobra.CobraProxy(uri)
    scheme, host, port, name, urlparams = cobra.chopCobraUri( uri )

    module = importlib.import_module(name)

    if hasattr(module, 'remotemain'):
        module.remotemain(server)
    else:
        module.main()

def runRemoteApp(uri, join=True):
    p = multiprocessing.Process(target=_getAndRunApp, args=(uri,))
    p.start()
    if join:
        p.join()

def execRemoteApp(uri):
    '''
    Exec a remoteapp without using multiprocessig ( may be needed if fork()
    causes the child to have an unacceptably dirty environment )
    '''
    subprocess.Popen([sys.executable, '-m', 'cobra.remoteapp', uri])

def main():
    parser = optparse.OptionParser()
    #parser.add_option('--cacert', dest='cacert', default=None )
    #parser.add_option('--sslkey', dest='sslkey', default=None )
    #parser.add_option('--sslcert', dest='sslcert', default=None )

    opts,argv = parser.parse_args()
    # FIXME make a socket builder...
    runRemoteApp(argv[0])

if __name__ == '__main__':
    sys.exit(main())

