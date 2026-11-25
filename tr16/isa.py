"""TR16 instruction set: the single source of truth shared by assembler and simulator.

Machine in one paragraph: 16-bit words, 256 words of memory holding both code and
data, 8 registers (R0 always reads 0), and four flags N Z C V that keep their value
until another instruction sets them. Every instruction is one 16-bit word:

    bits 15..12  opcode
    bits 11..9   rd   (destination, or the condition for branches)
    bits  8..6   rs
    bits  5..0   rt<<3 | func   (register forms)  or  a signed 6-bit immediate
"""
from bisect import bisect_left
from fractions import Fraction

# ---- machine size --------------------------------------------------------------
MEM_WORDS = 256
WORD_MASK = 0xFFFF       # registers and memory words are 16 bits
ADDR_MASK = 0xFF         # addresses and the PC are 8 bits
NUM_REGS = 8

# ---- flags: value of the FLAGS register (only the low 4 bits are used) ------------
FLAG_N, FLAG_Z, FLAG_C, FLAG_V = 8, 4, 2, 1   # negative, zero, carry, overflow

REG_ALIASES = {"zero": 0, "sp": 6, "lr": 7}

# ---- opcodes (bits 15..12) -------------------------------------------------------
OP_ALU, OP_ADDI, OP_LI, OP_LHI = 0, 1, 2, 3
OP_LD, OP_ST, OP_CMP, OP_BR = 4, 5, 6, 7
OP_JAL, OP_JR, OP_DIV, OP_SHI = 8, 9, 10, 11
OP_FP, OP_FLI = 12, 13           # 14 is reserved
OP_HLT = 15

# Operations that share an opcode are told apart by the 3-bit func field (bits 2..0).
ALU_FUNCS = {"add": 0, "sub": 1, "and": 2, "or": 3, "xor": 4, "shl": 5, "shr": 6, "mul": 7}
DIV_FUNCS = {"div": 0, "mod": 1}
FP_FUNCS = {"addf": 0, "subf": 1, "mulf": 2, "divf": 3}
# Branch condition, stored in the rd field.
CONDS = {"b": 0, "beq": 1, "bne": 2, "blt": 3, "bge": 4, "bgt": 5, "ble": 6, "blo": 7}


def names(table):
    """Reverse a {name: number} table into {number: name}."""
    return {v: k for k, v in table.items()}


ALU_NAMES, DIV_NAMES, FP_NAMES, COND_NAMES = map(names, (ALU_FUNCS, DIV_FUNCS, FP_FUNCS, CONDS))


# ---- small helpers ---------------------------------------------------------------
def parse_reg(tok):
    """'r3', 'R3', 'sp' ... -> register number, or None if tok is not a register."""
    t = tok.strip().lower()
    if t in REG_ALIASES:
        return REG_ALIASES[t]
    if len(t) == 2 and t[0] == "r" and t[1] in "01234567":
        return int(t[1])
    return None


def sext(value, bits):
    """Interpret the low `bits` bits of value as a signed number."""
    sign = 1 << (bits - 1)
    return (value & (sign - 1)) - (value & sign)


def fields(word):
    """Split an instruction word into (op, rd, rs, rt, func)."""
    return word >> 12, (word >> 9) & 7, (word >> 6) & 7, (word >> 3) & 7, word & 7


# ---- FP8: the 8-bit float used by fli / addf / subf / mulf / divf -----------------
# No sign bit, 3 exponent bits (bias 3), 5 mantissa bits, stored in a register's low byte.
#   exponent e > 0 : value = (1 + m/32) * 2^(e-3)
#   exponent e = 0 : value = (m/32) * 2^-2          (so the byte 0 is the number 0)
# The 256 values are exact fractions and increase with the byte, so "encode" is a search.
def fp_decode(byte):
    e, m = byte >> 5, byte & 31
    if e == 0:
        return Fraction(m, 128)
    return (1 + Fraction(m, 32)) * Fraction(2) ** (e - 3)


FP_VALUES = [fp_decode(b) for b in range(256)]
FP_MAX = FP_VALUES[255]   # 31.5


def fp_exact(value):
    """Byte whose value is exactly `value`, or None if there is none."""
    i = bisect_left(FP_VALUES, value)
    return i if i < 256 and FP_VALUES[i] == value else None


def fp_round(value):
    """Round 0 <= value <= FP_MAX to the nearest FP8 byte (tie -> even byte).
    Returns (byte, was_rounded)."""
    i = bisect_left(FP_VALUES, value)        # first byte whose value is >= value
    if FP_VALUES[i] == value:
        return i, False
    below, above = value - FP_VALUES[i - 1], FP_VALUES[i] - value
    pick_lower = below < above or (below == above and i % 2 == 1)
    return (i - 1 if pick_lower else i), True


# ---- disassembler (used by the simulator's --pretty trace) -----------------------
def disassemble(word, pc=None):
    """Text for one instruction word; branch targets are absolute when pc is given."""
    op, rd, rs, rt, func = fields(word)
    imm6, imm9 = sext(word, 6), sext(word, 9)
    target = f"@{(pc + 1 + imm9) & ADDR_MASK}" if pc is not None else f"{imm9:+d}"
    if op == OP_ALU:
        return f"{ALU_NAMES[func]} r{rd} r{rs} r{rt}"
    if op == OP_DIV and func in DIV_NAMES:
        return f"{DIV_NAMES[func]} r{rd} r{rs} r{rt}"
    if op == OP_FP and func in FP_NAMES:
        return f"{FP_NAMES[func]} r{rd} r{rs} r{rt}"
    if op == OP_ADDI:
        return f"addi r{rd} r{rs} {imm6}"
    if op == OP_LI:
        return f"li r{rd} {imm9}"
    if op == OP_LHI:
        return f"lhi r{rd} {word & 0xFF}"
    if op == OP_FLI:
        return f"fli r{rd} {float(fp_decode(word & 0xFF))}"
    if op in (OP_LD, OP_ST):
        return f"{'ld' if op == OP_LD else 'st'} r{rd} [r{rs}{imm6:+d}]"
    if op == OP_CMP:
        return f"cmp r{rs} r{rt}"
    if op == OP_BR:
        return f"{COND_NAMES[rd]} {target}"
    if op == OP_JAL:
        return f"jal r{rd} {target}"
    if op == OP_JR:
        return f"jr r{rs}"
    if op == OP_SHI:
        return f"{'shri' if word >> 5 & 1 else 'shli'} r{rd} r{rs} {word & 15}"
    if op == OP_HLT:
        return "hlt"
    return f".illegal 0x{word:04x}"
