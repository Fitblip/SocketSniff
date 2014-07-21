from envi.const import *
import envi.archs.amd64 as e_amd64

from vivisect.symboliks.common import *
import vivisect.symboliks.archs.i386 as vsym_i386
import vivisect.symboliks.analysis as vsym_analysis
import vivisect.symboliks.callconv as vsym_callconv

class Amd64SymbolikTranslator(vsym_i386.IntelSymbolikTranslator):
    __arch__ = e_amd64.Amd64Module
    __ip__ = 'rip' # we could use regctx.getRegisterName if we want.
    __sp__ = 'rsp' # we could use regctx.getRegisterName if we want.
    __srcp__ = 'rsi'
    __destp__ = 'rdi'

    def setRegObj(self, regidx, obj):
        ridx = regidx & 0xffff
        rname = self._reg_ctx.getRegisterName(ridx)
        rbitwidth = self._reg_ctx.getRegisterWidth(ridx)
        val = Var(rname, rbitwidth / 8 )

        # Translate to native if needed...
        if ridx != regidx:
            # 64 bit mode setting to 32bit regs, 0-extends to 64 bits
            if regidx == ridx | e_amd64.RMETA_LOW32:
                val = Var(rname, 8)
            else:
                # we cannot call _xlateToNativReg since we'd pass in a symbolik
                # object that would trigger an or operation; the code in envi
                # obviously is NOT symboliks aware (2nd op in | operation is NOT
                # a symbolik); so we do it manually here since we are symbolik
                # aware.
                #obj = self._reg_ctx._xlateToNativeReg(regidx, obj)
                basemask = (2**rbitwidth) - 1
                rreg, lshift, mask = self._reg_ctx.getMetaRegInfo(regidx)
                # cut hole in mask
                finalmask = basemask ^ (mask << lshift)
                if lshift != 0:
                    obj <<= Const(lshift, rbitwidth / 8)

                obj = obj | (val & Const(finalmask, rbitwidth / 8))

        self.effSetVariable(rname, obj)

    def getOperAddrObj(self, op, idx):
        oper = op.opers[idx]
        if isinstance(oper, e_amd64.Amd64RipRelOper):
            return Const(op.va + len(op) + oper.imm, 8)

        return vsym_i386.IntelSymbolikTranslator.getOperAddrObj(self, op, idx)

    def getOperObj(self, op, idx):
        oper = op.opers[idx]
        if isinstance(oper, e_amd64.Amd64RipRelOper):
            return Mem( Const( op.va + len(op) + oper.imm, 8), Const(oper.tsize, 8))

        return vsym_i386.IntelSymbolikTranslator.getOperObj(self, op, idx)

    def i_movsxd(self, op):
        dsize = op.opers[0].tsize
        ssize = op.opers[1].tsize
        v2 = o_sextend( Const(ssize, self._psize), Const(dsize, self._psize), self.getOperObj(op, 1) )
        self.setOperObj(op, 0, v2)

    def i_div(self, op):
        oper = op.opers[0]
        denom = self.getOperObj(op, 1)
        if denom == 0:
            # TODO: make effect
            raise Exception('#DE, divide by zero')

        if oper.tsize == 8:
            rax = Var('rax', self._psize)
            rdx = Var('rdx', self._psize)
            num = (rdx << Const(64, self._psize)) + rax
            temp = num / denom
            if temp > (2**64)-1:
                # TODO: make effect
                raise Exception('#DE, divide error')

            self.effSetVariable('rax', temp)
            self.effSetVariable('rdx', num % denom)

            return

        return vsym_i386.IntelSymbolikTranslator.i_div(self, op)

    def i_jecxz(self, op):
        return vsym_i386.i386SymbolikTranslator.i_jecxz(self, op)

    def i_jrcxz(self, op):
        return self._cond_jmp(op, eq(Var('rcx', self._psize), Const(0, self._psize)))

    def i_movsq(self, op):
        si = Var(self.__srcp__, self._psize)
        di = Var(self.__destp__, self._psize)
        mem = Mem(si, Const(8))
        self.effWriteMemory(di, Const(8, self._psize), mem)
        self.effSetVariable(self.__srcp__, si + Const(8, self._psize))
        self.effSetVariable(self.__destp__, di + Const(8, self._psize))

    def i_pushfd(self, op):
        sp = self.getRegObj(self._reg_ctx._rctx_spindex)
        sr = self.getRegObj(self._reg_ctx._rctx_srindex)
        self.effSetVariable(self.__sp__, sp - Const(8, self._psize))
        self.effWriteMemory(Var(self.__sp__, self._psize), Const(8, self._psize), sr)

class Amd64ArgDefSymEmu(vsym_i386.ArgDefSymEmu):
    __xlator__ = Amd64SymbolikTranslator

class MSx64CallSym(e_amd64.MSx64Call, vsym_callconv.SymbolikCallingConvention):
    __argdefemu__ = Amd64ArgDefSymEmu

class SysVAmd64CallSym(e_amd64.SysVAmd64Call, vsym_callconv.SymbolikCallingConvention):
    __argdefemu__ = Amd64ArgDefSymEmu

msx64callsym = MSx64CallSym()
sysvamd64callsym = SysVAmd64CallSym()

class Amd64SymFuncEmu(vsym_analysis.SymbolikFunctionEmulator):
    __width__ = 8

    def __init__(self, vw, initial_sp=0xbfbff000):
        vsym_analysis.SymbolikFunctionEmulator.__init__(self, vw)
        self.initial_sp = initial_sp
        self.setStackCounter(Const(initial_sp, self.__width__))
        self.addCallingConvention('sysvamd64call', SysVAmd64CallSym())
        self.addCallingConvention('msx64call', msx64callsym)

    def getStackCounter(self):
        return self.getSymVariable('rsp')

    def setStackCounter(self, symobj):
        self.setSymVariable('rsp', symobj)

    #def getRegister(self, val):
    #    return self.getSymVariable(val)

    def isLocalMemory(self, symaddr, solvedval=None):
        '''
        Determine if the given virtual address should be considered a "local"
        memory access...
        '''
        if solvedval == None:
            solvedval = symaddr.solve(emu=self)
        return (solvedval & 0xffffc000) == (self.initial_sp & 0xffffc000)

    def getLocalOffset(self, symaddr, solvedval=None):
        if solvedval == None:
            solvedval = symaddr.solve(emu=self)
        return solvedval - self.initial_sp

class Amd64SymbolikAnalysisContext(vsym_analysis.SymbolikAnalysisContext):
    __xlator__ = Amd64SymbolikTranslator
    __emu__ = Amd64SymFuncEmu
