MODE_ARM        = 0
MODE_THUMB      = 1
MODE_JAZELLE    = 2

#IFLAGS - keep bottom 8-bits for cross-platform flags like envi.IF_NOFALL and envi.IF_BRFALL
IF_PSR_S     = 1<<32     # This DP instruciton can update CPSR
IF_B         = 1<<33     # Byte
IF_H         = 1<<35    # HalfWord
IF_S         = 1<<36    # Signed
IF_D         = 1<<37    # Signed
IF_L         = 1<<38    # Long-store (eg. Dblword Precision) for STC
IF_T         = 1<<39    # Translate for strCCbt
IF_W         = 1<<40    # Write Back for STM/LDM (!)
IF_UM        = 1<<41    # User Mode Registers for STM/LDM (^) (obviously no R15)

IF_DAIB_SHFT = 56       # shift-bits to get DAIB bits down to 0.  this chops off the "is DAIB present" bit that the following store.
IF_DAIB_MASK = 7<<(IF_DAIB_SHFT-1)
IF_DA        = 1<<(IF_DAIB_SHFT-1)  # Decrement After
IF_IA        = 3<<(IF_DAIB_SHFT-1)  # Increment After
IF_DB        = 5<<(IF_DAIB_SHFT-1)  # Decrement Before
IF_IB        = 7<<(IF_DAIB_SHFT-1)  # Increment Before
IF_DAIB_B    = 5<<(IF_DAIB_SHFT-1)  # Before mask 
IF_DAIB_I    = 3<<(IF_DAIB_SHFT-1)  # Before mask 
IF_THUMB32   = 1<<50    # thumb32

OF_W         = 1<<8     # Write back to 
OF_UM        = 1<<9     # Usermode, or if r15 included set current SPSR -> CPSR


OSZFMT_BYTE = "B"
OSZFMT_HWORD = "<H"  # Introduced in ARMv4
OSZFMT_WORD = "<L"
OSZ_BYTE = 1
OSZ_HWORD = 2
OSZ_WORD = 4

fmts = [None, OSZ_BYTE, OSZ_HWORD, None, OSZ_WORD]

COND_EQ     = 0x0        # z==1  (equal)
COND_NE     = 0x1        # z==0  (not equal)
COND_CS     = 0x2        # c==1  (carry set/unsigned higher or same)
COND_CC     = 0x3        # c==0  (carry clear/unsigned lower)
COND_MI     = 0x4        # n==1  (minus/negative)
COND_PL     = 0x5        # n==0  (plus/positive or zero)
COND_VS     = 0x6        # v==1  (overflow)
COND_VC     = 0x7        # v==0  (no overflow)
COND_HI     = 0x8        # c==1 and z==0  (unsigned higher)
COND_LO     = 0x9        # c==0  or z==1  (unsigned lower or same)
COND_GE     = 0xA        # n==v  (signed greater than or equal)  (n==1 and v==1) or (n==0 and v==0)
COND_LT     = 0xB        # n!=v  (signed less than)  (n==1 and v==0) or (n==0 and v==1)
COND_GT     = 0xC        # z==0 and n==v (signed greater than)
COND_LE     = 0xD        # z==1 and n!=v (signed less than or equal)
COND_AL     = 0xE        # always
COND_EXTENDED = 0xF        # special case - see conditional 0b1111

cond_codes = {
COND_EQ:"eq", # Equal Z set 
COND_NE:"ne", # Not equal Z clear 
COND_CS:"cs", #/HS Carry set/unsigned higher or same C set 
COND_CC:"cc", #/LO Carry clear/unsigned lower C clear 
COND_MI:"mi", # Minus/negative N set 
COND_PL:"pl", # Plus/positive or zero N clear 
COND_VS:"vs", # Overflow V set 
COND_VC:"vc", # No overflow V clear 
COND_HI:"hi", # Unsigned higher C set and Z clear 
COND_LO:"lo", # Unsigned lower or same C clear or Z set 
COND_GE:"ge", # Signed greater than or equal N set and V set, or N clear and V clear (N == V) 
COND_LT:"lt", # Signed less than N set and V clear, or N clear and V set (N!= V) 
COND_GT:"gt", # Signed greater than Z clear, and either N set and V set, or N clear and V clear (Z == 0,N == V) 
COND_LE:"le", # Signed less than or equal Z set, or N set and V clear, or N clear and V set (Z == 1 or N!= V) 
COND_AL:"", # Always (unconditional) - could be "al" but "" seems better...
COND_EXTENDED:"2", # See extended opcode table
}

PM_usr = 0b10000
PM_fiq = 0b10001
PM_irq = 0b10010
PM_svc = 0b10011
PM_abt = 0b10111
PM_und = 0b11011
PM_sys = 0b11111

# reg stuff stolen from regs.py to support proc_modes
REG_OFFSET_USR = 17 * (PM_usr&0xf)
REG_OFFSET_FIQ = 17 * (PM_fiq&0xf)
REG_OFFSET_IRQ = 17 * (PM_irq&0xf)
REG_OFFSET_SVC = 17 * (PM_svc&0xf)
REG_OFFSET_ABT = 17 * (PM_abt&0xf)
REG_OFFSET_UND = 17 * (PM_und&0xf)
REG_OFFSET_SYS = 17 * (PM_sys&0xf)
#REG_OFFSET_CPSR = 17 * 16
REG_OFFSET_CPSR = 16                    # CPSR is available in every mode, and PM_usr and PM_sys don't have an SPSR.

REG_SPSR_usr = REG_OFFSET_USR + 16
REG_SPSR_fiq = REG_OFFSET_FIQ + 16
REG_SPSR_irq = REG_OFFSET_IRQ + 16
REG_SPSR_svc = REG_OFFSET_SVC + 16
REG_SPSR_abt = REG_OFFSET_ABT + 16
REG_SPSR_und = REG_OFFSET_UND + 16
REG_SPSR_sys = REG_OFFSET_SYS + 16

REG_PC = 0xf
REG_SP = 0xd
REG_BP = None
REG_CPSR = REG_OFFSET_CPSR
REG_FLAGS = REG_OFFSET_CPSR    #same location, backward-compat name

proc_modes = { # mode_name, short_name, description, offset, mode_reg_count, PSR_offset
    PM_usr: ("User Processor Mode", "usr", "Normal program execution mode", REG_OFFSET_USR, 15, REG_SPSR_usr),
    PM_fiq: ("FIQ Processor Mode", "fiq", "Supports a high-speed data transfer or channel process", REG_OFFSET_FIQ, 8, REG_SPSR_fiq),
    PM_irq: ("IRQ Processor Mode", "irq", "Used for general-purpose interrupt handling", REG_OFFSET_IRQ, 13, REG_SPSR_irq),
    PM_svc: ("Supervisor Processor Mode", "svc", "A protected mode for the operating system", REG_OFFSET_SVC, 13, REG_SPSR_svc),
    PM_abt: ("Abort Processor Mode", "abt", "Implements virtual memory and/or memory protection", REG_OFFSET_ABT, 13, REG_SPSR_abt),
    PM_und: ("Undefined Processor Mode", "und", "Supports software emulation of hardware coprocessor", REG_OFFSET_UND, 13, REG_SPSR_und),
    PM_sys: ("System Processor Mode", "sys", "Runs privileged operating system tasks (ARMv4 and above)", REG_OFFSET_SYS, 15, REG_SPSR_sys),
}
PM_LNAME =  0
PM_SNAME =  1
PM_DESC =   2
PM_REGOFF = 3
PM_BANKED = 4
PM_SPSR =   5

INST_ENC_DP_IMM = 0 # Data Processing Immediate Shift
INST_ENC_MISC   = 1 # Misc Instructions

# Instruction encodings in arm v5
IENC_DP_IMM_SHIFT = 0 # Data processing immediate shift
IENC_MISC         = 1 # Miscellaneous instructions
IENC_MISC1        = 2 # Miscellaneous instructions again
IENC_DP_REG_SHIFT = 3 # Data processing register shift
IENC_MULT         = 4 # Multiplies & Extra load/stores
IENC_UNDEF        = 5 # Undefined instruction
IENC_MOV_IMM_STAT = 6 # Move immediate to status register
IENC_DP_IMM       = 7 # Data processing immediate
IENC_LOAD_IMM_OFF = 8 # Load/Store immediate offset
IENC_LOAD_REG_OFF = 9 # Load/Store register offset
IENC_ARCH_UNDEF   = 10 # Architecturally undefined
IENC_MEDIA        = 11 # Media instructions
IENC_LOAD_MULT    = 12 # Load/Store Multiple
IENC_BRANCH       = 13 # Branch
IENC_COPROC_RREG_XFER = 14  # mrrc/mcrr
IENC_COPROC_LOAD  = 15 # Coprocessor load/store and double reg xfers
IENC_COPROC_DP    = 16 # Coprocessor data processing
IENC_COPROC_REG_XFER = 17 # Coprocessor register transfers
IENC_SWINT        = 18 # Sofware interrupts
IENC_UNCOND       = 19 # unconditional wacko instructions
IENC_EXTRA_LOAD   = 20 # extra load/store (swp)

# offchutes
IENC_MEDIA_PARALLEL = ((IENC_MEDIA << 8) + 1) << 8
IENC_MEDIA_SAT      = ((IENC_MEDIA << 8) + 2) << 8
IENC_MEDIA_REV      = ((IENC_MEDIA << 8) + 3) << 8
IENC_MEDIA_SEL      = ((IENC_MEDIA << 8) + 4) << 8
IENC_MEDIA_USAD8    = ((IENC_MEDIA << 8) + 5) << 8
IENC_MEDIA_USADA8   = ((IENC_MEDIA << 8) + 6) << 8
IENC_MEDIA_EXTEND   = ((IENC_MEDIA << 8) + 7) << 8
IENC_MEDIA_PACK     = ((IENC_MEDIA << 8) + 8) << 8
IENC_UNCOND_CPS     = ((IENC_UNCOND << 8) + 1) << 8
IENC_UNCOND_SETEND  = ((IENC_UNCOND << 8) + 2) << 8
IENC_UNCOND_PLD     = ((IENC_UNCOND << 8) + 3) << 8
IENC_UNCOND_BLX     = ((IENC_UNCOND << 8) + 4) << 8
IENC_UNCOND_RFE     = ((IENC_UNCOND << 8) + 5) << 8


# The supported types of operand shifts (by the 2 bit field)
S_LSL = 0
S_LSR = 1
S_ASR = 2
S_ROR = 3
S_RRX = 4 # FIXME HACK XXX add this

shift_names = ("lsl", "lsr", "asr", "ror", "rrx")

SOT_REG = 0
SOT_IMM = 1

daib = ("da", "ia", "db", "ib")


def instrenc(encoding, index):
    return (encoding << 16) + index

INS_ADD = IENC_DP_IMM_SHIFT << 16
INS_EOR = (IENC_DP_IMM_SHIFT << 16) + 1
INS_SUB = (IENC_DP_IMM_SHIFT << 16) + 2
INS_RSB = (IENC_DP_IMM_SHIFT << 16) + 3
INS_ADD = (IENC_DP_IMM_SHIFT << 16) + 4
INS_ADC = (IENC_DP_IMM_SHIFT << 16) + 5
INS_SBC = (IENC_DP_IMM_SHIFT << 16) + 6
INS_RSC = (IENC_DP_IMM_SHIFT << 16) + 7
INS_TST = (IENC_DP_IMM_SHIFT << 16) + 8
INS_TEQ = (IENC_DP_IMM_SHIFT << 16) + 9
INS_CMP = (IENC_DP_IMM_SHIFT << 16) + 10
INS_CMN = (IENC_DP_IMM_SHIFT << 16) + 11
INS_ORR = (IENC_DP_IMM_SHIFT << 16) + 12
INS_MOV = (IENC_DP_IMM_SHIFT << 16) + 13
INS_BIC = (IENC_DP_IMM_SHIFT << 16) + 14
INS_MVN = (IENC_DP_IMM_SHIFT << 16) + 15


INS_B       = instrenc(IENC_BRANCH, 0)
INS_BL      = instrenc(IENC_BRANCH, 1)
INS_BCC     = instrenc(IENC_BRANCH, 2)
INS_BX      = instrenc(IENC_MISC, 3)
INS_BXJ     = instrenc(IENC_MISC, 5)
INS_BLX     = IENC_UNCOND_BLX


INS_SWI     = IENC_SWINT

no_update_Rd = (INS_TST, INS_TEQ, INS_CMP, INS_CMN, )

