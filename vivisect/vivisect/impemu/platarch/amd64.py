
import envi.archs.amd64 as e_amd64
import vivisect.impemu.emulator as v_i_emulator

########################################################################
#
# NOTE: For each architecture we intend to do workspace emulation on,
#       extend an emulator to allow any of the needed tweaks (rep prefix
#       etc).
# NOTE: ARCH UPDATE

class Amd64WorkspaceEmulator(v_i_emulator.WorkspaceEmulator, e_amd64.Amd64Emulator):

    taintregs = [ 
        e_amd64.REG_RAX, e_amd64.REG_RCX, e_amd64.REG_RDX,
        e_amd64.REG_RBX, e_amd64.REG_RBP, e_amd64.REG_RSI,
        e_amd64.REG_RDI,
    ]

    def __init__(self, vw, logwrite=False, logread=False):
        e_amd64.Amd64Emulator.__init__(self)
        v_i_emulator.WorkspaceEmulator.__init__(self, vw, logwrite=logwrite, logread=logread)

    def doRepPrefix(self, meth, op):
        # Fake out the rep prefix (cause ecx == 0x41414141 ;) )
        return meth(op)

