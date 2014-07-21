
import vivisect
import vivisect.impemu as viv_imp
import vivisect.impemu.monitor as viv_monitor

import envi
import envi.archs.amd64 as e_amd64

from vivisect.const import *

regops = set(['cmp','sub'])

class AnalysisMonitor(viv_monitor.AnalysisMonitor):

    def __init__(self, vw, fva):
        viv_monitor.AnalysisMonitor.__init__(self, vw, fva)
        self.retbytes = None
        self.badop = vw.arch.archParseOpcode("\x00\x00\x00\x00\x00")

    def prehook(self, emu, op, starteip):

        if op == self.badop:
            raise Exception("Hit known BADOP at 0x%.8x %s" % (starteip, repr(op) ))

        viv_monitor.AnalysisMonitor.prehook(self, emu, op, starteip)

        if op.iflags & envi.IF_RET:
            if len(op.opers):
                self.retbytes = op.opers[0].imm

argnames = {
    0:'rcx',
    1:'rdx',
    2:'r8',
    3:'r9',
}

def msx64name(idx):
    ret = argnames.get(idx)
    if ret == None:
        ret = 'arg%d' % idx
    return ret

def buildFunctionApi(vw, fva, emu, emumon):
    
    argc = 0
    funcargs = []
    callconv = vw.getMeta('DefaultCall')
    undefregs = set(emu.getUninitRegUse())

    if callconv == 'msx64call':

        if e_amd64.REG_R9 in undefregs:
            argc = 4

        elif e_amd64.REG_R8 in undefregs:
            argc = 3

        elif e_amd64.REG_RDX in undefregs:
            argc = 2

        elif e_amd64.REG_RCX in undefregs:
            argc = 1

        # For msx64call there's the shadow space..
        if emumon.stackmax >= 40:
            #argc += ((emumon.stackmax - 40) / 8)
            argc = (emumon.stackmax / 8) - 1
            if argc > 40:
                emumon.logAnomaly(fva, 'Crazy Stack Offset Touched: 0x%.8x' % emumon.stackmax)
                argc = 0

        # Add the shadow space "locals"
        vw.setFunctionLocal(fva, 8,  LSYM_NAME, ('void *','shadow0'))
        vw.setFunctionLocal(fva, 16, LSYM_NAME, ('void *','shadow1'))
        vw.setFunctionLocal(fva, 24, LSYM_NAME, ('void *','shadow2'))
        vw.setFunctionLocal(fva, 32, LSYM_NAME, ('void *','shadow3'))

        funcargs = [ ('int',msx64name(i)) for i in xrange(argc) ]

    api = ('int',None,callconv,None,funcargs)

    vw.setFunctionApi(fva, api)
    return api

def analyzeFunction(vw, fva):

    emu = vw.getEmulator()
    emumon = AnalysisMonitor(vw, fva)

    emu.setEmulationMonitor(emumon)
    emu.runFunction(fva, maxhit=1)

    # Do we already have API info in meta?
    # NOTE: do *not* use getFunctionApi here, it will make one!
    api = vw.getFunctionMeta(fva, 'api')
    if api == None:
        api = buildFunctionApi(vw, fva, emu, emumon)

    rettype,retname,callconv,callname,callargs = api

    argc = len(callargs)
    cc = emu.getCallingConvention(callconv)
    stcount = cc.getNumStackArgs(emu, argc)
    stackidx = argc - stcount

    # Register our stack args as function locals
    for i in xrange( argc ):
        if i < stackidx:
            continue

        vw.setFunctionLocal(fva, 4 + ( i * 8 ), LSYM_FARG, i)

    emumon.addAnalysisResults(vw, emu)

