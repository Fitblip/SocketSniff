
import envi.bits as e_bits
import envi.bintree as e_btree

from envi.bits import binary

from envi.archs.arm.disasm import *

#thumb_32 = [
        #binary('11101'),
        #binary('11110'),
        #binary('11111'),
#]


O_REG = 0
O_IMM = 1
O_OFF = 2

OperType = (
    ArmRegOper,
    ArmImmOper,
    ArmPcOffsetOper,
    )
def shmaskval(value, shval, mask):  #FIXME: unnecessary to make this another fn call.  will be called a bajillion times.
    return (value >> shval) & mask

class simpleops:
    def __init__(self, *operdef):
        self.operdef = operdef

    def __call__(self, va, value):
        ret = []
        for otype, shval, mask in self.operdef:
            oval = shmaskval(value, shval, mask)
            oper = OperType[otype]((value >> shval) & mask, va=va)
            ret.append( oper )
        return ret

#imm5_rm_rd  = simpleops((O_REG, 0, 0x7), (O_REG, 3, 0x7), (O_IMM, 6, 0x1f))
rm_rn_rd    = simpleops((O_REG, 0, 0x7), (O_REG, 3, 0x7), (O_REG, 6, 0x7))
imm3_rn_rd  = simpleops((O_REG, 0, 0x7), (O_REG, 3, 0x7), (O_IMM, 6, 0x7))
imm8_rd     = simpleops((O_REG, 8, 0x7), (O_IMM, 0, 0xff))
rm_rd       = simpleops((O_REG, 0, 0x7), (O_REG, 3, 0x7))
rn_rdm      = simpleops((O_REG, 0, 0x7), (O_REG, 3, 0x7))
rm_rdn      = simpleops((O_REG, 0, 0x7), (O_REG, 3, 0x7))
rm_rd_imm0  = simpleops((O_REG, 0, 0x7), (O_REG, 3, 0x7), (O_IMM, 0, 0))
rm4_shift3  = simpleops((O_REG, 3, 0xf))
rm_rn_rt    = simpleops((O_REG, 0, 0x7), (O_REG, 3, 0x7), (O_REG, 6, 0x7))
imm8        = simpleops((O_IMM, 8, 0xff))
#imm11       = simpleops((O_IMM, 11, 0x7ff))

sh4_imm1    = simpleops((O_IMM, 3, 0x1))

def d1_rm4_rd3(va, value):
    # 0 1 0 0 0 1 0 0 DN(1) Rm(4) Rdn(3)
    rdbit = shmaskval(value, 4, 0x8)
    rd = shmaskval(value, 0, 0x7) + rdbit
    rm = shmaskval(value, 3, 0xf)
    return ArmRegOper(rd, va=va),ArmRegOper(rm, va=va)

def rm_rn_rt(va, value):
    rt = shmaskval(value, 0, 0x7) # target
    rn = shmaskval(value, 3, 0x7) # base
    rm = shmaskval(value, 6, 0x7) # offset
    oper0 = ArmRegOper(rt, va=va)
    oper1 = ArmRegOffsetOper(rn, rm, va, pubwl=0x18)
    return oper0,oper1

def imm54_rn_rt(va, value):
    imm = shmaskval(value, 4, 0x7c)
    rn = shmaskval(value, 3, 0x7)
    rt = shmaskval(value, 0, 0x7)
    oper0 = ArmRegOper(rt, va=va)
    oper1 = ArmImmOffsetOper(rn, imm, (va&0xfffffffc)+4, pubwl=0x18)
    return oper0,oper1

def imm55_rn_rt(va, value):
    imm = shmaskval(value, 5, 0x3e)
    rn = shmaskval(value, 3, 0x7)
    rt = shmaskval(value, 0, 0x7)
    oper0 = ArmRegOper(rt, va=va)
    oper1 = ArmImmOffsetOper(rn, imm, (va&0xfffffffc)+4, pubwl=0x18)
    return oper0,oper1

def imm56_rn_rt(va, value):
    imm = shmaskval(value, 6, 0x1f)
    rn = shmaskval(value, 3, 0x7)
    rt = shmaskval(value, 0, 0x7)
    oper0 = ArmRegOper(rt, va=va)
    oper1 = ArmImmOffsetOper(rn, imm, (va&0xfffffffc)+4, pubwl=0x18)
    return oper0,oper1

def rd_sp_imm8(va, value): # add
    rd = shmaskval(value, 8, 0x7)
    imm = shmaskval(value, 0, 0xff) * 4
    oper0 = ArmRegOper(rd, va=va)
    # pre-compute PC relative addr
    oper1 = ArmImmOffsetOper(REG_SP, imm, (va&0xfffffffc)+4, pubwl=0x18)
    return oper0,oper1

def rd_pc_imm8(va, value):  # add
    rd = shmaskval(value, 8, 0x7)
    imm = e_bits.signed(shmaskval(value, 0, 0xff), 1) * 4
    oper0 = ArmRegOper(rd, va=va)
    # pre-compute PC relative addr
    oper1 = ArmImmOper((va&0xfffffffc) + 4 + imm)
    return oper0,oper1

def rt_pc_imm8(va, value): # ldr
    rt = shmaskval(value, 8, 0x7)
    imm = e_bits.signed(shmaskval(value, 0, 0xff), 1) * 4
    oper0 = ArmRegOper(rt, va=va)
    oper1 = ArmImmOffsetOper(REG_PC, imm, (va&0xfffffffc)+4)
    return oper0,oper1

def bl_imm23(va, val, val2): # bl
    flags = 0
    # need next two bytes
    imm = (val&0x7ff) << 12
    imm |= ((val2&0x7ff) << 1)

    # break down the components
    S = (val>>10)&1
    j1 = (val2>>13)&1
    j2 = (val2>>11)&1
    i1 = ~ (j1 ^ S) & 0x1
    i2 = ~ (j2 ^ S) & 0x1
    X = (val2>>12)&1
    mnem = ('blx','bl')[X]

    imm = (S<<24) | (i1<<23) | (i2<<22) | ((val&0x3ff) << 12) | ((val2&0x7ff) << 1)

    #sign extend a 23-bit number
    if S:
        imm |= 0xff000000

    oper0 = ArmPcOffsetOper(e_bits.signed(imm,4), va=va)
    return ((oper0, ) , mnem, flags)

def pc_imm11(va, value): # b
    imm = e_bits.signed(shmaskval(value, 0, 0x7ff), 1) * 2
    oper0 = ArmPcOffsetOper(imm, va=va)
    return oper0,

def pc_imm8(va, value): # b
    imm = e_bits.signed(shmaskval(value, 0, 0xff), 1) * 2
    oper0 = ArmPcOffsetOper(imm, va=va)
    return oper0,

def ldmia(va, value): 
    rd = shmaskval(value, 8, 0x7)
    reg_list = value & 0xff
    oper0 = ArmRegOper(rd, va=va)
    oper1 = ArmRegListOper(reg_list)
    oper0.oflags |= OF_W
    return oper0,oper1

def sp_sp_imm7(va, value):
    imm = shmaskval(value, 0, 0x7f)
    o0 = ArmRegOper(REG_SP)
    o1 = ArmRegOper(REG_SP)
    o2 = ArmImmOper(imm*4)
    return o0,o1,o2

def rm_reglist(va, value):
    rm = shmaskval(value, 8, 0x7)
    reglist = value & 0xff
    oper0 = ArmRegOper(rm, va=va)
    oper1 = ArmRegListOper(reglist)
    oper0.oflags |= OF_W
    return oper0,oper1

def reglist(va, value):
    reglist = (value & 0xff) | ((value & 0x100)<<5)
    oper0 = ArmRegListOper(reglist)
    return (oper0,)

def imm5_rm_rd(va, value):
    rd = value & 0x7
    rm = (value >> 3) & 0x7
    imm5 = (value >> 6) & 0x1f

    stype = value >> 11

    oper0 = ArmRegOper(rd, va)
    oper1 = ArmRegShiftImmOper(rm, stype, imm5, va)
    return (oper0, oper1,)


def i_imm5_rn(va, value):
    imm5 = shmaskval(value, 3, 0x40) | shmaskval(value, 2, 0x3e)
    rn = value & 0x7
    oper0 = ArmRegOper(rn, va)
    oper1 = ArmImmOffsetOper(REG_PC, imm5, va)
    return (oper0, oper1,)

def ldm16(va, value):
    raise Exception("32bit wrapping of 16bit instruction... and it's not implemented")

def thumb32(va, val, val2):
    op =  (val2>>15)&1
    op2 = (val>>4) & 0x7f
    op1 = (val>>11) & 0x3
    flags = 0
    
    if op1 == 1:
        if (op2 & 0x64) == 0:
            raise Exception('# Load/Store Multiples')
            op3 = (val>>7) & 3
            W = (val>>5)&1
            L = (val>>4)&1
            mode = (val&0xf)

            mnem = ('srs', 'rfe')[L]
            iadb = (val>>7)&3
            flags |= ( IF_DB, 0, 0, IF_IA ) [ iadb ]
            olist = ( ArmRegOper(REG_SP), ArmImmOper(mode) )

        elif (op2 & 0x64) == 4:
            raise Exception('# Load/Store Dual, Load/Store Exclusive, table branch')

        elif (op2 & 0x60) == 0x20:
            raise Exception('# Data Processing (shifted register)')

        elif (op2 & 0x40) == 0x40:
            raise Exception('# Coprocessor, Advanced SIMD, Floating point instrs')
        else:
            raise InvalidInstruction(
                    mesg="Thumb32 failure",
                    bytez=struct.pack("<H", val)+struct.pack("<H", val2), va=va)


    elif op1 == 2:
        if (op2 & 0x20) == 0 and op == 0:
            raise Exception('# Data Processing (modified immediate)')

        elif (op2 & 0x20) == 1 and op == 0:
            raise Exception('# Data Processing (plain binary immediate)')

        elif op == 1:
            raise Exception('# Branches and miscellaneous control')

        else:
            raise InvalidInstruction(
                    mesg="Thumb32 failure",
                    bytez=struct.pack("<H", val)+struct.pack("<H", val2), va=va)

    elif op1 == 3:
        if (op2 & 0x71) == 0:
            raise Exception('# Store single data item')

        if (op2 & 0x67) == 1:
            raise Exception('# Load byte, memory hints')

        if (op2 & 0x67) == 3:
            raise Exception('# Load half-word, memory hints')

        if (op2 & 0x71) == 0x10:
            raise Exception('# Advanced SIMD element or structure load/store instructions')

        if (op2 & 0x70) == 0x20:
            raise Exception('# Data Processing (register)')

        if (op2 & 0x78) == 0x30:
            raise Exception('# Multiply, multiply accumulate, and absolute difference')

        if (op2 & 0x78) == 0x38:
            raise Exception('# Long multiply, long multiply accumulate, and divide')

        if (op2 & 0x40) == 0x40:
            raise Exception('# Coprocessor, Advanced SIMD, Floating Point instrs')

    return ( olist, mnem, flags )

# opinfo is:
# ( <mnem>, <operdef>, <flags> )
# operdef is:
# ( (otype, oshift, omask), ...)
# FIXME: thumb and arm opcode numbers don't line up.
thumb_base = [
    ('00000',       ( 0,'lsl',     imm5_rm_rd, 0)), # LSL<c> <Rd>,<Rm>,#<imm5>
    ('00001',       ( 1,'lsr',     imm5_rm_rd, 0)), # LSR<c> <Rd>,<Rm>,#<imm>
    ('00010',       ( 2,'asr',     imm5_rm_rd, 0)), # ASR<c> <Rd>,<Rm>,#<imm>
    ('0001100',     ( INS_ADD,'add',     rm_rn_rd,   0)), # ADD<c> <Rd>,<Rn>,<Rm>
    ('0001101',     ( INS_SUB,'sub',     rm_rn_rd,   0)), # SUB<c> <Rd>,<Rn>,<Rm>
    ('0001110',     ( INS_ADD,'add',     imm3_rn_rd, 0)), # ADD<c> <Rd>,<Rn>,#<imm3>
    ('0001111',     ( INS_SUB,'sub',     imm3_rn_rd, 0)), # SUB<c> <Rd>,<Rn>,#<imm3>
    ('00100',       ( 7,'mov',     imm8_rd,    0)), # MOV<c> <Rd>,#<imm8>
    ('00101',       ( 8,'cmp',     imm8_rd,    0)), # CMP<c> <Rn>,#<imm8>
    ('00110',       ( INS_ADD,'add',     imm8_rd,    0)), # ADD<c> <Rdn>,#<imm8>
    ('00111',       (INS_SUB,'sub',     imm8_rd,    0)), # SUB<c> <Rdn>,#<imm8>
    # Data processing instructions
    ('0100000000',  (11,'and',     rm_rdn,     0)), # AND<c> <Rdn>,<Rm>
    ('0100000001',  (12,'eor',     rm_rdn,     0)), # EOR<c> <Rdn>,<Rm>
    ('0100000010',  (13,'lsl',     rm_rdn,     0)), # LSL<c> <Rdn>,<Rm>
    ('0100000011',  (14,'lsr',     rm_rdn,     0)), # LSR<c> <Rdn>,<Rm>
    ('0100000100',  (15,'asr',     rm_rdn,     0)), # ASR<c> <Rdn>,<Rm>
    ('0100000101',  (16,'adc',     rm_rdn,     0)), # ADC<c> <Rdn>,<Rm>
    ('0100000110',  (17,'sbc',     rm_rdn,     0)), # SBC<c> <Rdn>,<Rm>
    ('0100000111',  (18,'ror',     rm_rdn,     0)), # ROR<c> <Rdn>,<Rm>
    ('0100001000',  (19,'tst',     rm_rd,      0)), # TST<c> <Rn>,<Rm>
    ('0100001001',  (20,'rsb',     rm_rd_imm0, 0)), # RSB<c> <Rd>,<Rn>,#0
    ('0100001010',  (21,'cmp',     rm_rd,      0)), # CMP<c> <Rn>,<Rm>
    ('0100001011',  (22,'cmn',     rm_rd,      0)), # CMN<c> <Rn>,<Rm>
    ('0100001100',  (23,'orr',     rm_rdn,     0)), # ORR<c> <Rdn>,<Rm>
    ('0100001101',  (24,'mul',     rn_rdm,     0)), # MUL<c> <Rdm>,<Rn>,<Rdm>
    ('0100001110',  (25,'bic',     rm_rdn,     0)), # BIC<c> <Rdn>,<Rm>
    ('0100001111',  (26,'mvn',     rm_rd,      0)), # MVN<c> <Rd>,<Rm>
    # Special data in2tructions and branch and exchange
    ('0100010000',  (INS_ADD,'add',     d1_rm4_rd3, 0)), # ADD<c> <Rdn>,<Rm>
    ('0100010001',  (INS_ADD,'add',     d1_rm4_rd3, 0)), # ADD<c> <Rdn>,<Rm>
    ('010001001',   (INS_ADD,'add',     d1_rm4_rd3, 0)), # ADD<c> <Rdn>,<Rm>
    ('010001010',   (30,'cmp',     d1_rm4_rd3, 0)), # CMP<c> <Rn>,<Rm>
    ('010001011',   (31,'cmp',     d1_rm4_rd3, 0)), # CMP<c> <Rn>,<Rm>
    ('01000110',    (34,'mov',     d1_rm4_rd3, 0)), # MOV<c> <Rd>,<Rm>
    ('010001110',   (35,'bx',      rm4_shift3, envi.IF_NOFALL)), # BX<c> <Rm>
    ('010001111',   (36,'blx',     rm4_shift3, 0)), # BLX<c> <Rm>
    # Load from Litera7 Pool
    ('01001',       (37,'ldr',     rt_pc_imm8, 0)), # LDR<c> <Rt>,<label>
    # Load/Stor single data item
    ('0101000',     (38,'str',     rm_rn_rt,   0)), # STR<c> <Rt>,[<Rn>,<Rm>]
    ('0101001',     (39,'strh',    rm_rn_rt,   0)), # STRH<c> <Rt>,[<Rn>,<Rm>]
    ('0101010',     (40,'strb',    rm_rn_rt,   0)), # STRB<c> <Rt>,[<Rn>,<Rm>]
    ('0101011',     (41,'ldrsb',   rm_rn_rt,   0)), # LDRSB<c> <Rt>,[<Rn>,<Rm>]
    ('0101100',     (42,'ldr',     rm_rn_rt,   0)), # LDR<c> <Rt>,[<Rn>,<Rm>]
    ('0101101',     (43,'ldrh',    rm_rn_rt,   0)), # LDRH<c> <Rt>,[<Rn>,<Rm>]
    ('0101110',     (44,'ldrb',    rm_rn_rt,   0)), # LDRB<c> <Rt>,[<Rn>,<Rm>]
    ('0101111',     (45,'ldrsh',   rm_rn_rt,   0)), # LDRSH<c> <Rt>,[<Rn>,<Rm>]
    ('01100',       (46,'str',     imm54_rn_rt, 0)), # STR<c> <Rt>, [<Rn>{,#<imm5>}]
    ('01101',       (47,'ldr',     imm54_rn_rt, 0)), # LDR<c> <Rt>, [<Rn>{,#<imm5>}]
    ('01110',       (48,'strb',    imm56_rn_rt, 0)), # STRB<c> <Rt>,[<Rn>,#<imm5>]
    ('01111',       (49,'ldrb',    imm56_rn_rt, 0)), # LDRB<c> <Rt>,[<Rn>{,#<imm5>}]
    ('10000',       (50,'strh',    imm55_rn_rt, 0)), # STRH<c> <Rt>,[<Rn>{,#<imm>}]
    ('10001',       (51,'ldrh',    imm55_rn_rt, 0)), # LDRH<c> <Rt>,[<Rn>{,#<imm>}]
    ('10010',       (52,'str',     rd_sp_imm8, 0)), # STR<c> <Rt>, [<Rn>{,#<imm>}]
    ('10011',       (53,'ldr',     rd_sp_imm8, 0)), # LDR<c> <Rt>, [<Rn>{,#<imm>}]
    # Generate PC relative address
    ('10100',       (INS_ADD,'add',     rd_pc_imm8, 0)), # ADD<c> <Rd>,<label>
    # Generate SP rel5tive address
    ('10101',       (INS_ADD,'add',     rd_sp_imm8, 0)), # ADD<c> <Rd>,SP,#<imm>
    # Miscellaneous in6tructions
    ('1011001000',  (561,'sxth',    rm_rd,      0)), # SXTH<c> <Rd>, <Rm>
    ('1011001001',  (561,'sxtb',    rm_rd,      0)), # SXTB<c> <Rd>, <Rm>
    ('1011001000',  (561,'uxth',    rm_rd,      0)), # UXTH<c> <Rd>, <Rm>
    ('1011001001',  (561,'uxtb',    rm_rd,      0)), # UXTB<c> <Rd>, <Rm>
    ('1011010',     (56,'push',    reglist,    0)), # PUSH <reglist>
    ('10110110010', (57,'setend',  sh4_imm1,   0)), # SETEND <endian_specifier>
    ('10110110011', (58,'cps',     simpleops(),0)), # CPS<effect> <iflags> FIXME
    ('10110001',    (59,'cbz',     i_imm5_rn,  0)), # CBZ{<q>} <Rn>, <label>    # label must be positive, even offset from PC
    ('10111001',    (60,'cbnz',    i_imm5_rn,  0)), # CBNZ{<q>} <Rn>, <label>   # label must be positive, even offset from PC
    ('10110011',    (59,'cbz',     i_imm5_rn,  0)), # CBZ{<q>} <Rn>, <label>    # label must be positive, even offset from PC
    ('10111011',    (60,'cbnz',    i_imm5_rn,  0)), # CBNZ{<q>} <Rn>, <label>   # label must be positive, even offset from PC
    ('1011101000',  (61,'rev',     rn_rdm,     0)), # REV Rd, Rn
    ('1011101001',  (62,'rev16',   rn_rdm,     0)), # REV16 Rd, Rn
    ('1011101011',  (63,'revsh',   rn_rdm,     0)), # REVSH Rd, Rn
    ('101100000',   (INS_ADD,'add',     sp_sp_imm7, 0)), # ADD<c> SP,SP,#<imm>
    ('101100001',   (INS_SUB,'sub',     sp_sp_imm7, 0)), # SUB<c> SP,SP,#<imm>
    ('1011110',     (66,'pop',     reglist,    0)), # POP<c> <registers>
    ('10111110',    (67,'bkpt',    imm8,       0)), # BKPT <blahblah>
    # Load / Store Mu64iple
    ('11000',       (68,'stm',   rm_reglist, IF_IA|IF_W)), # LDMIA Rd!, reg_list
    ('11001',       (69,'ldm',   rm_reglist, IF_IA|IF_W)), # STMIA Rd!, reg_list
    # Conditional Bran6hes
    ('11010000',    (INS_BCC,'beq',     pc_imm8,       0)),
    ('11010001',    (INS_BCC,'bn',      pc_imm8,       0)),
    ('11010010',    (INS_BCC,'bhs',     pc_imm8,       0)),
    ('11010011',    (INS_BCC,'blo',     pc_imm8,       0)),
    ('11010100',    (INS_BCC,'bmi',     pc_imm8,       0)),
    ('11010101',    (INS_BCC,'bpl',     pc_imm8,       0)),
    ('11010110',    (INS_BCC,'bvs',     pc_imm8,       0)),
    ('11010111',    (INS_BCC,'bvc',     pc_imm8,       0)),
    ('11011000',    (INS_BCC,'bhi',     pc_imm8,       0)),
    ('11011001',    (INS_BCC,'bls',     pc_imm8,       0)),
    ('11011010',    (INS_BCC,'bge',     pc_imm8,       0)),
    ('11011011',    (INS_BCC,'blt',     pc_imm8,       0)),
    ('11011100',    (INS_BCC,'bgt',     pc_imm8,       0)),
    ('11011101',    (INS_BCC,'ble',     pc_imm8,       0)),
    ('11011110',    (INS_B,'b',       pc_imm8,       envi.IF_NOFALL)),
    ('11011111',    (INS_BCC,'bfukt',   pc_imm8,       0)),
    # Software Interru2t
    ('11011111',    (INS_SWI,'swi',     imm8,       0)), # SWI <blahblah>
    ('1011111100000000',    (89,'nopHint',    imm8,       0)), #unnecessary instruction
    ('1011111100010000',    (90,'yieldHint',  imm8,       0)), #unnecessary instruction
    ('1011111100100000',    (91,'wfrHint',    imm8,       0)), #unnecessary instruction
    ('1011111100110000',    (92,'wfiHint',    imm8,       0)), #unnecessary instruction
    ('1011111101000000',    (93,'sevHint',    imm8,       0)), #unnecessary instruction
    ('101111110000',       (94,'if-then-Hint',    imm8,       0)), #unnecessary instruction
    ('101111110001',       (94,'if-then-Hint',    imm8,       0)), #unnecessary instruction
    ('101111110010',       (94,'if-then-Hint',    imm8,       0)), #unnecessary instruction
    ('101111110011',       (94,'if-then-Hint',    imm8,       0)), #unnecessary instruction
    ('101111110100',       (94,'if-then-Hint',    imm8,       0)), #unnecessary instruction
    ('101111110101',       (94,'if-then-Hint',    imm8,       0)), #unnecessary instruction
    ('101111110110',       (94,'if-then-Hint',    imm8,       0)), #unnecessary instruction
    ('101111110111',       (94,'if-then-Hint',    imm8,       0)), #unnecessary instruction
    ('101111111000',       (94,'if-then-Hint',    imm8,       0)), #unnecessary instruction
    ('101111111001',       (94,'if-then-Hint',    imm8,       0)), #unnecessary instruction
    ('101111111010',       (94,'if-then-Hint',    imm8,       0)), #unnecessary instruction
    ('101111111011',       (94,'if-then-Hint',    imm8,       0)), #unnecessary instruction
    ('101111111100',       (94,'if-then-Hint',    imm8,       0)), #unnecessary instruction
    ('101111111101',       (94,'if-then-Hint',    imm8,       0)), #unnecessary instruction
    ('101111111110',       (94,'if-then-Hint',    imm8,       0)), #unnecessary instruction
    ('101111111111',       (94,'if-then-Hint',    imm8,       0)), #unnecessary instruction
    ]

thumb1_extension = [
    ('11100',       (INS_B,  'b',       pc_imm11,           0)),        # B <imm11>
    ('1111',        (INS_BL, 'bl',      bl_imm23,       IF_THUMB32)),   # BL/BLX <addr25> 
]

###  holy crap, this is so wrong and imcomplete....
thumb2_extension = [
    ('11100',       (85,'ldm',      ldm16,     0)),     # 16-bit instructions
    ('11101',       (86,'blah32',   thumb32,   0)),
    ('1111',        (86,'blah32',   thumb32,   0)),
    ]
'''
    ('111010000000',    (85,'srs',      srs_32,     0)),
    ('111010000001',    (85,'rfe',      rfe_32,     0)),
    ('111010000010',    (85,'srs',      srs_32,     0)),
    ('111010000011',    (85,'rfe',      rfe_32,     0)),

    ('111010001000',    (85,'stm',      ldm32,     0)),
    ('111010001001',    (85,'ldm',      ldm32,     0)),
    ('111010001010',    (85,'stm',      ldm32,     0)),
    ('111010001011',    (85,'ldm',      ldm32,     0)),

    ('111010010000',    (85,'srs',      srs_32,     0)),
    ('111010010001',    (85,'rfe',      rfe_32,     0)),
    ('111010010010',    (85,'srs',      srs_32,     0)),
    ('111010010011',    (85,'rfe',      rfe_32,     0)),

    ('111010011000',    (85,'stm',      ldm16,     0)),
    ('111010011001',    (85,'ldm',      ldm16,     0)),
    ('111010011010',    (85,'stm',      ldm16,     0)),
    ('111010011011',    (85,'ldm',      ldm16,     0)),

    ]
'''
thumb_table = list(thumb_base)
thumb_table.extend(thumb1_extension)

thumb2_table = list(thumb_base)
thumb2_table.extend(thumb2_extension)

ttree = e_btree.BinaryTree()
for binstr, opinfo in thumb_table:
    ttree.addBinstr(binstr, opinfo)

thumb32mask = binary('11111')
thumb32min  = binary('11100')

def is_thumb32(val):
    '''
    Take a 16 bit integer (opcode) value and determine
    if it is really the first 16 bits of a 32 bit
    instruction.
    '''
    bval = val >> 11
    return (bval & thumb32mask) > thumb32min


class ThumbOpcode(ArmOpcode):
    _def_arch = envi.ARCH_THUMB16
    pass

class Thumb16Disasm:

    def disasm(self, bytez, offset, va, trackMode=True):
        val, = struct.unpack("<H", bytez[offset:offset+2])
        try:
            opcode, mnem, opermkr, flags = ttree.getInt(val, 16)
        except TypeError:
            raise envi.InvalidInstruction(
                    mesg="disasm parser cannot find instruction",
                    bytez=bytez[offset:offset+2], va=va)

        if flags & IF_THUMB32:
            val2, = struct.unpack("<H", bytez[offset+2:offset+4])
            olist, mnem, flags = opermkr(va+4, val, val2)
            oplen = 4
        else:
            olist = opermkr(va+4, val)
            oplen = 2

        # since our flags determine how the instruction is decoded later....  
        # performance-wise this should be set as the default value instead of 0, but this is cleaner
        flags |= envi.ARCH_THUMB16

        if (  len(olist) and 
                isinstance(olist[0], ArmRegOper) and
                olist[0].involvesPC() and 
                opcode not in no_update_Rd ):
            
            showop = True
            flags |= envi.IF_NOFALL

        op = ThumbOpcode(va, opcode, mnem, 0xe, oplen, olist, flags)
        return op

if __name__ == '__main__':
    import envi.archs
    envi.archs.dismain( Thumb16Disasm() )
