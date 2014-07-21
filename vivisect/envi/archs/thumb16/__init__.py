
from envi.archs.arm import *

import disasm as th_disasm

class Thumb16Module(ArmModule):

    def __init__(self):
        ArmModule.__init__(self, name='thumb16')
        self._arch_dis = th_disasm.Thumb16Disasm()
