#!/usr/bin/env python3
"""TR16 assembler.

    python3 assembler.py prog.asm > prog.bin        (or read stdin)

Output: one 16-bit word per line in ASCII binary, code first and then the data
declared with `.word`. Errors are all collected and printed as
`error: line N: message` on stderr, with exit status 1.

How it works, in two passes over the source:
  1. Split every line into labels, instructions and .word data, and give each
     label / variable an address. Every instruction (pseudo-instructions
     included) is exactly one word, so an address is just a count.
  2. Encode each instruction. Labels are now known, so forward references work.
"""
import argparse
import re
import sys
from fractions import Fraction

from isa import *

NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LABEL = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")


class AsmError(Exception):
    """A problem on one line; the message is shown to the user."""


# Operand shape of every real instruction -> how many operands it takes.
#   rrr  rd rs rt          rri   rd rs imm6        li   rd imm9-or-symbol
#   lhi  rd imm8           fli   rd float          mem  rd [rs+imm]
#   cmp  rs rt             jal   rd label          jr   rs
#   shi  rd rs imm4        br    label             none (hlt)
SHAPES = {"rrr": 3, "rri": 3, "li": 2, "lhi": 2, "fli": 2, "mem": 2,
          "cmp": 2, "jal": 2, "jr": 1, "shi": 3, "br": 1, "none": 0}
SHAPE_OF = {"addi": "rri", "li": "li", "lhi": "lhi", "fli": "fli", "ld": "mem", "st": "mem",
            "cmp": "cmp", "jal": "jal", "jr": "jr", "shli": "shi", "shri": "shi", "hlt": "none"}
for _m in [*ALU_FUNCS, *DIV_FUNCS, *FP_FUNCS]:
    SHAPE_OF[_m] = "rrr"
for _m in CONDS:
    SHAPE_OF[_m] = "br"

# Pseudo-instructions: name -> (operand count, rewrite into a real instruction).
PSEUDO = {
    "nop":  (0, lambda t: ("add", ["r0", "r0", "r0"])),
    "mov":  (2, lambda t: ("addi", [t[0], t[1], "0"])),
    "inc":  (1, lambda t: ("addi", [t[0], t[0], "1"])),
    "dec":  (1, lambda t: ("addi", [t[0], t[0], "-1"])),
    "call": (1, lambda t: ("jal", ["lr", t[0]])),
    "ret":  (0, lambda t: ("jr", ["lr"])),
}
RESERVED = set(SHAPE_OF) | set(PSEUDO)   # cannot be used as label / variable names


def parse_int(tok):
    """Decimal, 0x.., 0b.. (optionally negative)."""
    try:
        return int(tok, 0)
    except ValueError:
        try:
            return int(tok, 10)          # also accepts "007"
        except ValueError:
            raise AsmError(f"invalid number '{tok}'")


def reg(tok):
    r = parse_reg(tok)
    if r is None:
        raise AsmError(f"invalid register '{tok}' (use r0-r7, zero, sp, lr)")
    return r


def imm(tok, lo, hi, mnem):
    v = parse_int(tok)
    if not lo <= v <= hi:
        raise AsmError(f"immediate {v} out of range [{lo}, {hi}] for '{mnem}'")
    return v


def pack(op, rd=0, rs=0, low6=0):
    """Assemble the standard layout: op(4) rd(3) rs(3) low6(6)."""
    return op << 12 | rd << 9 | rs << 6 | (low6 & 0x3F)


def pack9(op, rd, imm9):
    """Layout with a 9-bit immediate in place of rs and low6."""
    return op << 12 | rd << 9 | (imm9 & 0x1FF)


def split_operands(text):
    """'r1, [r2 + 3]' -> (['r1', '[]'], 'r2 + 3'). At most one [..] operand."""
    mem = None
    if "[" in text or "]" in text:
        m = re.search(r"\[([^\[\]]*)\]", text)
        if not m or text.count("[") != 1 or text.count("]") != 1:
            raise AsmError("malformed memory operand, expected [reg] or [reg+offset]")
        mem = m.group(1)
        text = text[:m.start()] + " [] " + text[m.end():]
    return [t for t in re.split(r"[,\s]+", text.strip()) if t], mem


class Assembler:
    def __init__(self, source):
        self.lines = source.splitlines()
        self.errors = []      # (line number, message)
        self.insts = []       # (line number, mnemonic, operand text)
        self.data = []        # (line number, name, [values])
        self.symbols = {}     # name -> (kind 'label'|'var', index, line number)
        self.ndata = 0

    def error(self, line, msg):
        self.errors.append((line, msg))

    # ---- pass 1 -------------------------------------------------------------
    def first_pass(self):
        for n, raw in enumerate(self.lines, 1):
            text = re.split(r";|//", raw, maxsplit=1)[0].strip()   # drop comment
            while (m := LABEL.match(text)):                         # leading "name:"
                self.define(m.group(1), "label", len(self.insts), n)
                text = m.group(2).strip()
            if not text:
                continue
            head, _, rest = text.partition(" ")
            if head.lower() == ".word":
                self.declare_word(n, rest)
            elif head.startswith("."):
                self.error(n, f"unknown directive '{head}'")
            else:
                self.insts.append((n, head.lower(), rest.strip()))
        self.ncode = len(self.insts)

    def declare_word(self, n, rest):
        """.word name [value ...]  reserves one word per value (default one 0)."""
        toks = [t for t in re.split(r"[,\s]+", rest.strip()) if t]
        if not toks or not NAME.match(toks[0]):
            return self.error(n, ".word needs a variable name: '.word name [value ...]'")
        try:
            values = [parse_int(t) for t in toks[1:]] or [0]
            for v in values:
                if not -32768 <= v <= 65535:
                    raise AsmError(f"value {v} does not fit in 16 bits")
        except AsmError as e:
            return self.error(n, str(e))
        self.define(toks[0], "var", self.ndata, n)
        self.data.append((n, toks[0], [v & WORD_MASK for v in values]))
        self.ndata += len(values)

    def define(self, name, kind, index, line):
        if parse_reg(name) is not None or name.lower() in RESERVED:
            self.error(line, f"'{name}' is a reserved word and cannot be a {kind} name")
        elif name in self.symbols:
            self.error(line, f"duplicate definition of '{name}' "
                             f"(first defined on line {self.symbols[name][2]})")
        else:
            self.symbols[name] = (kind, index, line)

    def address_of(self, name):
        """Labels point into the code; variables live right after the code."""
        kind, index, _ = self.symbols[name]
        return index if kind == "label" else self.ncode + index

    # ---- pass 2 -------------------------------------------------------------
    def second_pass(self):
        words = []
        for addr, (n, mnem, ops) in enumerate(self.insts):
            try:
                words.append(self.encode(addr, mnem, ops))
            except AsmError as e:
                self.error(n, str(e))
                words.append(0)
        last = len(self.lines) or 1
        if not any(mnem == "hlt" for _, mnem, _ in self.insts):
            self.error(last, "program has no 'hlt' instruction")
        if self.ncode + self.ndata > MEM_WORDS:
            self.error(last, f"program needs {self.ncode + self.ndata} words, memory has {MEM_WORDS}")
        for _, _, values in self.data:
            words += values
        return words

    def code_label(self, name, mnem):
        if name not in self.symbols:
            raise AsmError(f"undefined label '{name}'")
        if self.symbols[name][0] != "label":
            raise AsmError(f"'{name}' is a data variable, but '{mnem}' needs a code label")
        return self.address_of(name)

    def encode(self, addr, mnem, ops):
        """Turn one instruction into its 16-bit word."""
        toks, mem = split_operands(ops)
        if mnem in PSEUDO:
            count, rewrite = PSEUDO[mnem]
            self.check_count(mnem, toks, count)
            mnem, toks = rewrite(toks)
        elif mnem not in SHAPE_OF:
            raise AsmError(f"unknown mnemonic '{mnem}'")
        shape = SHAPE_OF[mnem]
        self.check_count(mnem, toks, SHAPES[shape])
        if (mem is not None) != (shape == "mem"):
            raise AsmError(f"'{mnem}' " + ("needs a memory operand like [r1] or [r1+4]"
                                           if shape == "mem" else "does not take a memory operand"))

        if shape == "rrr":
            rd, rs, rt = map(reg, toks)
            for op, funcs in ((OP_ALU, ALU_FUNCS), (OP_DIV, DIV_FUNCS), (OP_FP, FP_FUNCS)):
                if mnem in funcs:
                    return pack(op, rd, rs, rt << 3 | funcs[mnem])
        if shape == "rri":                                   # addi
            return pack(OP_ADDI, reg(toks[0]), reg(toks[1]), imm(toks[2], -32, 31, mnem))
        if shape == "li":                                    # constant, or the address of a symbol
            if NAME.match(toks[1]) and parse_reg(toks[1]) is None:
                if toks[1] not in self.symbols:
                    raise AsmError(f"undefined symbol '{toks[1]}'")
                value = self.address_of(toks[1])
            else:
                value = imm(toks[1], -256, 255, mnem)
            return pack9(OP_LI, reg(toks[0]), value)
        if shape == "lhi":
            return pack9(OP_LHI, reg(toks[0]), imm(toks[1], 0, 255, mnem))
        if shape == "fli":
            return pack9(OP_FLI, reg(toks[0]), self.float_byte(toks[1]))
        if shape == "mem":                                   # ld / st rd [rs+offset]
            rs, offset = self.memory_operand(mem, mnem)
            return pack(OP_LD if mnem == "ld" else OP_ST, reg(toks[0]), rs, offset)
        if shape == "cmp":
            return pack(OP_CMP, 0, reg(toks[0]), reg(toks[1]) << 3)
        if shape in ("br", "jal"):                           # PC-relative: target - (addr + 1)
            offset = self.code_label(toks[-1], mnem) - (addr + 1)
            if shape == "br":
                return pack9(OP_BR, CONDS[mnem], offset)
            return pack9(OP_JAL, reg(toks[0]), offset)
        if shape == "jr":
            return pack(OP_JR, 0, reg(toks[0]))
        if shape == "shi":                                   # direction bit 5, amount bits 3..0
            rd, rs, amount = reg(toks[0]), reg(toks[1]), imm(toks[2], 0, 15, mnem)
            return pack(OP_SHI, rd, rs, (32 if mnem == "shri" else 0) | amount)
        return pack(OP_HLT)                                  # shape "none"

    @staticmethod
    def check_count(mnem, toks, expected):
        if len(toks) != expected:
            raise AsmError(f"'{mnem}' expects {expected} operand(s), got {len(toks)}")

    @staticmethod
    def memory_operand(text, mnem):
        """'r2', 'r2+4' or 'r2 - 4' -> (base register, offset in -32..31)."""
        m = re.match(r"^\s*(\w+)\s*(?:([+-])\s*(\w+))?\s*$", text)
        if not m:
            raise AsmError(f"'{mnem}' needs a memory operand like [r1] or [r1+4]")
        offset = 0
        if m.group(2):
            offset = parse_int(m.group(3)) * (-1 if m.group(2) == "-" else 1)
            if not -32 <= offset <= 31:
                raise AsmError(f"offset {offset} out of range [-32, 31] for '{mnem}'")
        return reg(m.group(1)), offset

    @staticmethod
    def float_byte(tok):
        """'1.5' -> its FP8 byte. Only exactly representable values are allowed."""
        try:
            value = Fraction(tok)
        except (ValueError, ZeroDivisionError):
            raise AsmError(f"invalid floating-point value '{tok}'")
        byte = fp_exact(value)
        if byte is None:
            raise AsmError(f"{tok} is not exactly representable in the 8-bit float format "
                           f"(range 0..{float(FP_MAX)}, 3 exponent / 5 mantissa bits)")
        return byte


def assemble(source):
    a = Assembler(source)
    a.first_pass()
    return a, a.second_pass()


def main():
    ap = argparse.ArgumentParser(description="TR16 assembler")
    ap.add_argument("file", nargs="?", help="assembly file (default: stdin)")
    ap.add_argument("--symbols", action="store_true", help="print 'name=address' lines to stderr")
    args = ap.parse_args()
    a, words = assemble(open(args.file).read() if args.file else sys.stdin.read())
    if args.symbols:
        for name in sorted(a.symbols, key=a.address_of):
            print(f"{name}={a.address_of(name)}", file=sys.stderr)
    if a.errors:
        for line, msg in sorted(a.errors):
            print(f"error: line {line}: {msg}", file=sys.stderr)
        return 1
    sys.stdout.write("".join(f"{w:016b}\n" for w in words))
    return 0


if __name__ == "__main__":
    sys.exit(main())
