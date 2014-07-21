import struct

import envi
import envi.bits as e_bits
import envi.archs.i386 as e_i386
import envi.archs.i386.disasm as ed_i386
import opcode64 as opcode86
all_tables = opcode86.tables86

from envi.archs.i386.disasm import iflag_lookup, operand_range, priv_lookup, \
        i386Opcode, i386ImmOper, i386RegOper, i386ImmMemOper, i386RegMemOper, \
        i386SibOper
from envi.archs.amd64.regs import *

# Pre generate these for fast lookup. Because our REX prefixes have the same relative
# bit relationship to eachother, we can cheat a little...
amd64_prefixes = list(e_i386.i386_prefixes)
amd64_prefixes[0x40] = (0x10 << 16)
amd64_prefixes[0x41] = (0x11 << 16)
amd64_prefixes[0x42] = (0x12 << 16)
amd64_prefixes[0x43] = (0x13 << 16)
amd64_prefixes[0x44] = (0x14 << 16)
amd64_prefixes[0x45] = (0x15 << 16)
amd64_prefixes[0x46] = (0x16 << 16)
amd64_prefixes[0x47] = (0x17 << 16)
amd64_prefixes[0x48] = (0x18 << 16)
amd64_prefixes[0x49] = (0x19 << 16)
amd64_prefixes[0x4a] = (0x1a << 16)
amd64_prefixes[0x4b] = (0x1b << 16)
amd64_prefixes[0x4c] = (0x1c << 16)
amd64_prefixes[0x4d] = (0x1d << 16)
amd64_prefixes[0x4e] = (0x1e << 16)
amd64_prefixes[0x4f] = (0x1f << 16)

# NOTE: some notes from the intel manual...
# REX.W overrides 66, but alternate registers (via REX.B etc..) can have 66 to be 16 bit..
# REX.R only modifies reg for GPR/SSE(SIMD)/ctrl/debug addressing modes.
# REX.X only modifies the SIB index value
# REX.B modifies modrm r/m field, or SIB base (if SIB present), or opcode reg.
# We inherit all the regular intel prefixes...
PREFIX_REX   = 0x100000 # Shows that the rex prefix is present
PREFIX_REX_B = 0x010000 # Bit 0 in REX prefix (0x41) means ModR/M r/m field, SIB base, or opcode reg
PREFIX_REX_X = 0x020000 # Bit 1 in REX prefix (0x42) means SIB index extension
PREFIX_REX_R = 0x040000 # Bit 2 in REX prefix (0x44) means ModR/M reg extention
PREFIX_REX_W = 0x080000 # Bit 3 in REX prefix (0x48) means 64 bit operand

REX_BUMP = 8
MODE_16 = 0
MODE_32 = 1
MODE_64 = 2

class Amd64RipRelOper(envi.DerefOper):
    def __init__(self, imm, tsize):
        self.imm = imm
        self.tsize = tsize
        self._is_deref = True

    def getOperValue(self, op, emu=None):
        if self._is_deref == False: # Special lea behavior
            return self.getOperAddr(op)
        if emu == None: return None
        return emu.readMemValue(self.getOperAddr(op, emu), self.tsize)

    def setOperValue(self, op, emu, val):
        emu.writeMemValue(self.getOperAddr(op, emu), val, self.tsize)

    def getOperAddr(self, op, emu=None):
        return op.va + op.size + self.imm

    def isDeref(self):
        # The disassembler may reach in and set this (if lea...)
        return self._is_deref

    def isDiscrete(self):
        return True

    def render(self, mcanv, op, idx):
        destva = op.va + op.size + self.imm
        sym = mcanv.syms.getSymByAddr(destva)

        mcanv.addNameText(e_i386.sizenames[self.tsize])
        mcanv.addText(" [")
        mcanv.addNameText("rip", typename="registers")

        if self.imm > 0:
            mcanv.addText(" + ")
            if sym != None:
                mcanv.addVaText("$%s" % repr(sym), destva)
            else:
                mcanv.addNameText(str(self.imm))
        elif self.imm < 0:
            mcanv.addText(" - ")
            if sym != None:
                mcanv.addVaText("$%s" % repr(sym), destva)
            else:
                mcanv.addNameText(str(abs(self.imm)))
        mcanv.addText("]")

    def repr(self, op):
        return "[rip + %d]" % self.imm

class Amd64Disasm(e_i386.i386Disasm):

    def __init__(self):
        e_i386.i386Disasm.__init__(self)
        self._dis_oparch = envi.ARCH_AMD64
        self._dis_prefixes = amd64_prefixes
        self._dis_regctx = Amd64RegisterContext()
        self.ptrsize = 8

        # Over-ride these which are in use by the i386 version of the ASM
        self.ROFFSETMMX   = e_i386.getRegOffset(amd64regs, "mm0")
        self.ROFFSETSIMD  = e_i386.getRegOffset(amd64regs, "xmm0")
        self.ROFFSETDEBUG = e_i386.getRegOffset(amd64regs, "debug0")
        self.ROFFSETCTRL  = e_i386.getRegOffset(amd64regs, "ctrl0")
        self.ROFFSETTEST  = e_i386.getRegOffset(amd64regs, "test0")
        self.ROFFSETSEG   = e_i386.getRegOffset(amd64regs, "es")
        self.ROFFSETFPU   = e_i386.getRegOffset(amd64regs, "st0")

    # NOTE: Technically, the REX must be the *last* prefix specified

    def _dis_calc_tsize(self, opertype, prefixes, operflags):
        """
        Use the oper type and prefixes to decide on the tsize for
        the operand.
        """

        mode = MODE_32

        sizelist = opcode86.OPERSIZE.get(opertype, None)
        if sizelist == None:
            raise "OPERSIZE FAIL"

        if operflags & opcode86.OP_64AUTO:
            mode = MODE_64

        # NOTE: REX takes precedence over 66
        # (see section 2.2.1.2 in Intel 2a)
        if prefixes & PREFIX_REX_W:

            mode = MODE_64

        elif prefixes & e_i386.PREFIX_OP_SIZE:

            mode = MODE_16

        return sizelist[mode]

    def disasm(self, bytez, offset, va):

        # Stuff for opcode parsing
        tabdesc = all_tables[0] # A tuple (optable, shiftbits, mask byte, sub, max)
        startoff = offset # Use startoff as a size knob if needed

        # Stuff we'll be putting in the opcode object
        optype = None # This gets set if we successfully decode below
        mnem = None 
        operands = []

        prefixes = 0

        while True:

            obyte = ord(bytez[offset])

            # This line changes in 64 bit mode
            p = self._dis_prefixes[obyte]
            if p == None:
                break
            if obyte == 0x66 and ord(bytez[offset+1]) == 0x0f:
                break
            prefixes |= p
            offset += 1
            continue

        #pdone = False
        while True:

            obyte = ord(bytez[offset])

            #print "OBYTE",hex(obyte)
            if (obyte > tabdesc[4]):
                #print "Jumping To Overflow Table:", tabdesc[5]
                tabdesc = all_tables[tabdesc[5]]

            tabidx = ((obyte - tabdesc[3]) >> tabdesc[1]) & tabdesc[2]
            #print "TABIDX: %d" % tabidx
            opdesc = tabdesc[0][tabidx]
            #print 'OPDESC: %s' % repr(opdesc)

            # Hunt down multi-byte opcodes
            nexttable = opdesc[0]
            #print "NEXT",nexttable,hex(obyte)
            if nexttable != 0: # If we have a sub-table specified, use it.
                #print "Multi-Byte Next Hop For",hex(obyte),opdesc[0]
                tabdesc = all_tables[nexttable]

                # In the case of 66 0f, the next table is *already* assuming we ate
                # the 66 *and* the 0f...  oblidge them.
                if obyte == 0x66 and ord(bytez[offset+1]) == 0x0f:
                    offset += 1

                # Account for the table jump we made
                offset += 1

                continue

            # We are now on the final table...
            #print repr(opdesc)
            mnem = opdesc[6]
            optype = opdesc[1]
            if tabdesc[2] == 0xff:
                offset += 1 # For our final opcode byte
            break

        if optype == 0:
            #print tabidx
            #print opdesc
            #print "OPTTYPE 0"
            raise envi.InvalidInstruction(bytez=bytez[startoff:startoff+16], va=va)

        operoffset = 0
        # Begin parsing operands based off address method
        for i in operand_range:

            oper = None # Set this if we end up with an operand
            osize = 0

            # Pull out the operand description from the table
            operflags = opdesc[i]
            opertype = operflags & opcode86.OPTYPE_MASK
            addrmeth = operflags & opcode86.ADDRMETH_MASK

            # If there are no more operands, break out of the loop!
            if operflags == 0:
                break

            #print "ADDRTYPE: %.8x OPERTYPE: %.8x" % (addrmeth, opertype)

            # handles tsize calculations including new REX prefixes
            tsize = self._dis_calc_tsize(opertype, prefixes, operflags)

            #print hex(opertype),hex(addrmeth),hex(tsize)


            # If addrmeth is zero, we have operands embedded in the opcode
            if addrmeth == 0:
                osize = 0
                oper = self.ameth_0(operflags, opdesc[5+i], tsize, prefixes)

            else:
                #print "ADDRTYPE",hex(addrmeth)
                ameth = self._dis_amethods[addrmeth >> 16]
                #print "AMETH",ameth
                if ameth == None:
                    raise Exception("Implement Addressing Method 0x%.8x" % addrmeth)

                # NOTE: Depending on your addrmethod you may get beginning of operands, or offset
                try:
                    if addrmeth == opcode86.ADDRMETH_I or addrmeth == opcode86.ADDRMETH_J:
                        osize, oper = ameth(bytez, offset+operoffset, tsize, prefixes, operflags)

                        # If we are a sign extended immediate and not the same as the other operand,
                        # do the sign extension during disassembly so nothing else has to worry about it..
                        if len(operands) and tsize != operands[-1].tsize:
                            # Check if we are an explicitly signed operand *or* REX.W
                            if operflags & opcode86.OP_SIGNED or prefixes & PREFIX_REX_W:
                                otsize = operands[-1].tsize
                                oper.imm = e_bits.sign_extend(oper.imm, oper.tsize, otsize)
                                oper.tsize = otsize

                    else:
                        osize, oper = ameth(bytez, offset, tsize, prefixes, operflags)

                except struct.error, e:
                    # Catch struct unpack errors due to insufficient data length
                    raise envi.InvalidInstruction(bytez=bytez[startoff:startoff+16])

            if oper != None:
                # This is a filty hack for now...
                oper._dis_regctx = self._dis_regctx
                operands.append(oper)

            operoffset += osize

        # Pull in the envi generic instruction flags
        iflags = iflag_lookup.get(optype, 0) | self._dis_oparch

        if priv_lookup.get(mnem, False):
            iflags |= envi.IF_PRIV

        # Lea will have a reg-mem/sib operand with _is_deref True, but should be false
        if optype == opcode86.INS_LEA:
            operands[1]._is_deref = False

        ret = i386Opcode(va, optype, mnem, prefixes, (offset-startoff)+operoffset, operands, iflags)

        return ret

    def parse_modrm(self, byte, prefixes=0):
        # Pass in a string with an offset for speed rather than a new string
        mod = (byte >> 6) & 0x3
        reg = (byte >> 3) & 0x7
        rm = byte & 0x7

        if prefixes & PREFIX_REX_R:
            reg |= 0b1000

        if prefixes & PREFIX_REX_B:
            if not (mod != 3 and rm == 4):  # if not SIB
                rm |= 0b1000

        #print "MOD/RM",hex(byte),mod,reg,rm
        return (mod,reg,rm)

    def parse_sib(self, bytez, offset, mod, prefixes=0):
        size, scale, index, base, imm = e_i386.i386Disasm.parse_sib(self, bytez, offset, mod)

        if prefixes & PREFIX_REX_B:
            base |= 0b1000

        if prefixes & PREFIX_REX_X:
            index |= 0b1000

        return (size, scale, index, base, imm)

    def byteRegOffset(self, val, prefixes=0):
        # NOTE: Override this because there is no AH etc in 64 bit mode
        if (prefixes & PREFIX_REX):     # the parse_modrm function deals with register index adds
            val |= e_i386.RMETA_LOW8

        else:  # not using REX, revert to old split-registers (low/high)
            if val < 4:
                val |= e_i386.RMETA_LOW8
            else:
                val |= e_i386.RMETA_HIGH8
                val -= 4

        return val

    def extended_parse_modrm(self, bytes, offset, opersize, regbase=0, prefixes=0):
        """
        Return a tuple of (size, Operand)
        """
        size = 1
        # FIXME this would be best to not parse_modrm twice.  tweak it.
        mod,reg,rm = self.parse_modrm(ord(bytes[offset]), prefixes)
        if mod == 0 and rm == 5:
            imm = e_bits.parsebytes(bytes, offset + size, 4, sign=True)
            size += 4
            return(size, Amd64RipRelOper(imm, opersize))

        return e_i386.i386Disasm.extended_parse_modrm(self, bytes, offset, opersize, regbase, prefixes)

    # NOTE: Override a bunch of the address modes to account for REX
    def ameth_0(self, operflags, operval, tsize, prefixes):
        o = e_i386.i386Disasm.ameth_0(self, operflags, operval, tsize, prefixes)
        # If it has a builtin register, we need to check for bump prefix
        if prefixes & PREFIX_REX_W and isinstance(o, e_i386.i386RegOper):
            o.reg &= 0xffff
        if prefixes & PREFIX_REX_B and isinstance(o, e_i386.i386RegOper):
            o.reg += REX_BUMP
        return o

    def ameth_g(self, bytes, offset, tsize, prefixes, operflags):
        osize, oper = e_i386.i386Disasm.ameth_g(self, bytes, offset, tsize, prefixes, operflags)
        if oper.tsize == 4 and oper.reg != REG_RIP:
            oper.reg += RMETA_LOW32
        if prefixes & PREFIX_REX_R:
            oper.reg += REX_BUMP
        return osize, oper

    def ameth_h(self, bytez, offset, tsize, prefixes, operflags):
        raise Exception("IMPLEMENT ADDRMETH_H please....")
        osize = 0
        oper = 0
        return osize, oper

    def ameth_c(self, bytes, offset, tsize, prefixes, operflags):
        osize, oper = e_i386.i386Disasm.ameth_c(self, bytes, offset, tsize, prefixes, operflags)
        if prefixes & PREFIX_REX_R:
            oper.reg += REX_BUMP
        return osize,oper

    def ameth_d(self, bytes, offset, tsize, prefixes, operflags):
        osize, oper = e_i386.i386Disasm.ameth_d(self, bytes, offset, tsize, prefixes, operflags)
        if prefixes & PREFIX_REX_R:
            oper.reg += REX_BUMP
        return osize,oper

    def ameth_v(self, bytes, offset, tsize, prefixes, operflags):
        osize, oper = e_i386.i386Disasm.ameth_v(self, bytes, offset, tsize, prefixes, operflags)
        if prefixes & PREFIX_REX_R:
            oper.reg += REX_BUMP
        return osize,oper

    # NOTE: The ones below are the only ones to which REX.X or REX.B can apply (besides ameth_0)
    #FIXME: we need to adhere to the ADDR_SIZE/OPER_SIZE rules better...  the REX_BUMP is an afterthought...
    # however, all the rules are based on ADDR_SIZE/OPER_SIZE and can be coalesced elegantly into amd64/i386
    # and even make 16-bit mode play nicely.
    def _dis_rex_exmodrm(self, oper, prefixes, operflags):
        # REMEMBER: all extended mod RM reg fields come from the r/m part.  If it
        #           were actually just the reg part, it'd be in one of the above
        #           addressing modes...
        if getattr(oper, "index", None) != None:
            # Adjust the size if needed
            if prefixes & PREFIX_REX_X:
                oper.index += REX_BUMP

        # oper.reg will be r/m or SIB base
        if getattr(oper, "reg", None) != None:
            # Adjust the size if needed
            if prefixes & PREFIX_REX_B:
                oper.reg += REX_BUMP

        if isinstance(oper, e_i386.i386RegOper):
            if oper.tsize == 4:
                oper.reg += RMETA_LOW32

    def ameth_e(self, bytes, offset, tsize, prefixes, operflags):
        osize, oper = e_i386.i386Disasm.ameth_e(self, bytes, offset, tsize, prefixes, operflags)
        self._dis_rex_exmodrm(oper, prefixes, operflags)
        return osize, oper

    def ameth_w(self, bytes, offset, tsize, prefixes, operflags):
        osize, oper = e_i386.i386Disasm.ameth_w(self, bytes, offset, tsize, prefixes, operflags)
        self._dis_rex_exmodrm(oper, prefixes, operflags)
        return osize,oper

if __name__ == '__main__':
    import envi.archs
    envi.archs.dismain( Amd64Disasm() )

