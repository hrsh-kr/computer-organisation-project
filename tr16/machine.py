"""TR16 machine, as four small parts:

  Memory           256 x 16-bit words
  ProgramCounter   8-bit address of the next instruction
  RegisterFile     R0-R7 and FLAGS
  ExecutionEngine  fetches the word at PC, carries it out, says where PC goes next
"""
from isa import *


class IllegalInstruction(Exception):
    pass


class Memory:
    def __init__(self):
        self.words = [0] * MEM_WORDS

    def load(self, words):
        if len(words) > MEM_WORDS:
            raise ValueError(f"binary has {len(words)} words, memory holds {MEM_WORDS}")
        self.words[:len(words)] = words

    def read(self, addr):
        return self.words[addr & ADDR_MASK]        # addresses wrap around

    def write(self, addr, value):
        self.words[addr & ADDR_MASK] = value & WORD_MASK

    def dump(self):
        return [f"{w:016b}" for w in self.words]


class ProgramCounter:
    def __init__(self):
        self.value = 0

    def update(self, new):
        self.value = new & ADDR_MASK


class RegisterFile:
    def __init__(self):
        self.regs = [0] * NUM_REGS
        self.flags = 0

    def read(self, i):
        return self.regs[i]

    def write(self, i, value):
        if i != 0:                                  # R0 is hardwired to zero
            self.regs[i] = value & WORD_MASK

    def dump(self):
        """R0..R7 then FLAGS, as 16-bit binary strings."""
        return [f"{v:016b}" for v in self.regs + [self.flags]]


class ExecutionEngine:
    def __init__(self, mem, rf, pc):
        self.mem, self.rf, self.pc = mem, rf, pc

    # ---- flags ---------------------------------------------------------------
    def set_flags(self, result, carry=False, overflow=False):
        """Set N and Z from the 16-bit result plus the given C and V; return the result."""
        r = result & WORD_MASK
        self.rf.flags = ((FLAG_N if r >> 15 else 0) | (FLAG_Z if r == 0 else 0)
                         | (FLAG_C if carry else 0) | (FLAG_V if overflow else 0))
        return r

    # ---- integer arithmetic ----------------------------------------------------
    def add(self, a, b):
        full = a + b
        signed_overflow = (~(a ^ b) & (a ^ full)) & 0x8000   # operands agree in sign, result differs
        return self.set_flags(full, carry=full > WORD_MASK, overflow=signed_overflow)

    def sub(self, a, b):
        full = a - b
        signed_overflow = ((a ^ b) & (a ^ full)) & 0x8000    # operands differ in sign, result != a's sign
        return self.set_flags(full, carry=a >= b, overflow=signed_overflow)  # C = "no borrow"

    def shift(self, a, n, left):
        """Shift by n (0-15). C gets the last bit shifted out."""
        if n == 0:
            return self.set_flags(a)
        carry = (a >> (16 - n)) & 1 if left else (a >> (n - 1)) & 1
        return self.set_flags(a << n if left else a >> n, carry=carry)

    def alu(self, func, a, b):
        op = ALU_NAMES[func]
        if op == "add":
            return self.add(a, b)
        if op == "sub":
            return self.sub(a, b)
        if op == "and":
            return self.set_flags(a & b)
        if op == "or":
            return self.set_flags(a | b)
        if op == "xor":
            return self.set_flags(a ^ b)
        if op == "shl":
            return self.shift(a, b & 15, left=True)
        if op == "shr":
            return self.shift(a, b & 15, left=False)
        full = a * b                                         # mul: keep the low 16 bits
        return self.set_flags(full, carry=full > WORD_MASK, overflow=full > WORD_MASK)

    def divide(self, func, a, b):
        if b == 0:                                           # result 0, V flags the error
            return self.set_flags(0, overflow=True)
        return self.set_flags(a // b if DIV_NAMES[func] == "div" else a % b)

    # ---- FP8 arithmetic ----------------------------------------------------------
    def fp(self, func, a, b):
        """a, b are FP8 bytes. Compute exactly, then round to FP8.
        Z: result is zero.  C: result had to be rounded.
        V: result invalid (above 31.5, negative, or divide by zero) -> result 0."""
        x, y = FP_VALUES[a], FP_VALUES[b]
        op = FP_NAMES[func]
        if op == "addf":
            exact = x + y
        elif op == "subf":
            exact = x - y
        elif op == "mulf":
            exact = x * y
        else:
            exact = x / y if y != 0 else -1                  # -1 marks "invalid"
        if not 0 <= exact <= FP_MAX:
            return self.set_flags(0, overflow=True)
        byte, rounded = fp_round(exact)
        self.rf.flags = (FLAG_Z if byte == 0 else 0) | (FLAG_C if rounded else 0)
        return byte

    # ---- branches ----------------------------------------------------------------
    def condition_holds(self, cond):
        f = self.rf.flags
        n, z, c, v = (bool(f & bit) for bit in (FLAG_N, FLAG_Z, FLAG_C, FLAG_V))
        return {0: True,                 # b    always
                1: z,                    # beq  equal
                2: not z,                # bne  not equal
                3: n != v,               # blt  signed less
                4: n == v,               # bge  signed greater or equal
                5: not z and n == v,     # bgt  signed greater
                6: z or n != v,          # ble  signed less or equal
                7: not c}[cond]          # blo  unsigned less (borrow occurred)

    # ---- one instruction -----------------------------------------------------------
    def step(self):
        """Execute the instruction at PC. Returns (halted, next_pc)."""
        pc = self.pc.value
        word = self.mem.read(pc)
        op, rd, rs, rt, func = fields(word)
        rf = self.rf
        a, b = rf.read(rs), rf.read(rt)
        next_pc = pc + 1

        if op == OP_ALU:
            rf.write(rd, self.alu(func, a, b))
        elif op == OP_DIV and func in DIV_NAMES:
            rf.write(rd, self.divide(func, a, b))
        elif op == OP_FP and func in FP_NAMES:
            rf.write(rd, self.fp(func, a & 0xFF, b & 0xFF))
        elif op == OP_ADDI:
            rf.write(rd, self.add(a, sext(word, 6) & WORD_MASK))
        elif op == OP_LI:
            rf.write(rd, sext(word, 9))
        elif op == OP_LHI:
            rf.write(rd, (word & 0xFF) << 8 | (rf.read(rd) & 0xFF))   # set high byte, keep low
        elif op == OP_FLI:
            rf.write(rd, word & 0xFF)
        elif op == OP_LD:
            rf.write(rd, self.mem.read(a + sext(word, 6)))
        elif op == OP_ST:
            self.mem.write(a + sext(word, 6), rf.read(rd))
        elif op == OP_CMP:
            self.sub(a, b)                                            # flags only
        elif op == OP_BR:
            if self.condition_holds(rd):
                next_pc = pc + 1 + sext(word, 9)
        elif op == OP_JAL:
            rf.write(rd, pc + 1)                                      # return address
            next_pc = pc + 1 + sext(word, 9)
        elif op == OP_JR:
            next_pc = a
        elif op == OP_SHI:
            rf.write(rd, self.shift(a, word & 15, left=not word >> 5 & 1))
        elif op == OP_HLT:
            return True, pc
        else:
            raise IllegalInstruction(f"illegal instruction 0x{word:04x} at address {pc}")
        return False, next_pc & ADDR_MASK
