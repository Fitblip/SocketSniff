"""
Find all undefined reference targets and attempt to determine
if they are code by emulation behaviorial analysis.

(This module works best very late in the analysis passes)
"""
import envi
import vivisect
import vivisect.reports as viv_rep
import vivisect.impemu.monitor as viv_imp_monitor

from vivisect.const import *

vasetdef = (("va",VASET_ADDRESS),)
report = "vivisect.reports.undeftargets"
verbose = False

class watcher(viv_imp_monitor.EmulationMonitor):

    def __init__(self, vw, tryva):
        viv_imp_monitor.EmulationMonitor.__init__(self)
        self.vw = vw
        self.badop = vw.arch.archParseOpcode("\x00\x00\x00\x00\x00")
        self.tryva = tryva
        self.hasret = False
        self.mndist = {}
        self.insn_count = 0
        self.lastop = None
        

    def looksgood(self):
        if not self.hasret: 
            return False

        # if there is 1 mnem that makes up over 50% of all instructions then flag it as invalid
        for mnem, count in self.mndist.items():
            if round(float( float(count) / float(self.insn_count)), 3) >= .50:
                return False

        return True

    def iscode(self):
        op = self.lastop

        if not self.lastop:
            return False

        if not (op.iflags & envi.IF_RET) and not (op.iflags & envi.IF_BRANCH) and not (op.iflags & envi.IF_CALL):
            return False

        for mnem, count in self.mndist.items():
            # XXX - CONFIG OPTION
            if round(float( float(count) / float(self.insn_count)), 3) >= .60:
                return False

        return True


    def prehook(self, emu, op, eip):

        if op.mnem == "out": #FIXME arch specific. see above idea.
            raise Exception("Out instruction...")

        if op == self.badop:
            raise Exception("Hit known BADOP at 0x%.8x %s" % (eip,repr(op)))

        if op.iflags & envi.IF_RET:
            self.hasret = True

        self.lastop = op
        # Make sure we didn't run into any other
        # defined locations...
        if self.vw.isFunction(eip):
            raise Exception("Fell Through Into Function: %.8x" % eip)

        loc = self.vw.getLocation(eip)
        if loc != None:
            va, size, ltype, linfo = loc
            if ltype != vivisect.LOC_OP:
                raise Exception("HIT %d AT %.8x" % (ltype, va))
        cnt = self.mndist.get(op.mnem, 0)
        self.mndist[ op.mnem ] = cnt+1
        self.insn_count += 1

        # FIXME do we need a way to terminate emulation here?

def analyze(vw):

    flist = vw.getFunctions()

    tried = {}
    vasetrows = []
    while True:
        docode = []
        bcode  = []
        

        vatodo = []
        #for va, name in viv_rep.runReportModule(vw, report).items():
        vatodo = [ va for va, name in vw.getNames() if vw.getLocation(va) == None ]
        vatodo.extend( [ va for addr, va in vw.findPointers() if vw.getLocation(va) == None] )    
        
        for va in vatodo:
            if vw.getLocation(va) != None:
                continue

            # Make sure it's executable
            if not vw.isExecutable(va):
                continue

            # Skip it if we've tried it already.
            if tried.get(va):
                continue

            tried[va] = True

            emu = vw.getEmulator()
            wat = watcher(vw, va)
            emu.setEmulationMonitor(wat)
            try:
                emu.runFunction(va, maxhit=1)
            except Exception, e:
                continue

            if wat.looksgood():
                docode.append(va)
            # flag to tell us to be greedy w/ finding code
            # XXX - visi is going to hate this..
            elif wat.iscode() and vw.greedycode:
                bcode.append(va)
            else:
                if vw.isProbablyString(va):
                    vw.makeString(va)
                elif vw.isProbablyUnicode(va):
                    vw.makeUnicode(va)

        if len(docode) == 0:
            break

        docode.sort()
        for va in docode:
            if vw.getLocation(va) != None:
                continue
            # XXX - RP 
            try:
                vw.makeFunction(va)
            except: 
                continue
            vasetrows.append((va,))
    
        bcode.sort()
        for va in bcode:
            if vw.getLocation(va) != None:
                continue
            vw.makeCode(va)

    vw.addVaSet("Made By Emucode", vasetdef, vasetrows)
    dlist = vw.getFunctions()

    vw.verbprint("emucode: %d new functions defined (now total: %d)" % (len(dlist)-len(flist), len(dlist)))

