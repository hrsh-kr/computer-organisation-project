#!/usr/bin/env python3
"""TR16 simulator.

    python3 simulator.py prog.bin            (or read the binary from stdin)

After every executed instruction (including hlt) one trace line is printed:
    <PC 8 bits> <R0> <R1> ... <R7> <FLAGS>      (registers as 16-bit binary)
When the machine halts the whole 256-word memory is dumped, one word per line.
Use --pretty for a readable trace with disassembly instead.
"""
import argparse
import sys

from isa import *
from machine import ExecutionEngine, IllegalInstruction, Memory, ProgramCounter, RegisterFile


def read_binary(text):
    words = []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if len(line) != 16 or set(line) - {"0", "1"}:
            raise ValueError(f"line {n}: expected 16 binary digits, got '{line}'")
        words.append(int(line, 2))
    return words


def flag_str(f):
    return "".join(ch if f & bit else "-" for ch, bit in zip("NZCV", (FLAG_N, FLAG_Z, FLAG_C, FLAG_V)))


def run(words, pretty=False, max_steps=100000, out=sys.stdout):
    mem, rf, pc = Memory(), RegisterFile(), ProgramCounter()
    mem.load(words)
    ee = ExecutionEngine(mem, rf, pc)
    steps = 0
    while True:
        if steps >= max_steps:
            raise RuntimeError(f"no hlt after {max_steps} steps (infinite loop?)")
        here = pc.value
        text = disassemble(mem.read(here), here)
        halted, new_pc = ee.step()
        steps += 1
        if pretty:
            regs = " ".join(f"r{i}={rf.read(i):<5d}" for i in range(NUM_REGS))
            out.write(f"{here:3d}: {text:<18} {regs} {flag_str(rf.flags)}\n")
        else:
            out.write(f"{here:08b} {' '.join(rf.dump())}\n")
        if halted:
            break
        pc.update(new_pc)
    if not pretty:
        out.write("\n".join(mem.dump()) + "\n")
    return steps


def main():
    ap = argparse.ArgumentParser(description="TR16 simulator")
    ap.add_argument("file", nargs="?", help="binary file (default: stdin)")
    ap.add_argument("--pretty", action="store_true", help="readable trace with disassembly, no memory dump")
    ap.add_argument("--max-steps", type=int, default=100000, help="abort after this many instructions")
    args = ap.parse_args()
    try:
        words = read_binary(open(args.file).read() if args.file else sys.stdin.read())
        run(words, args.pretty, args.max_steps)
    except (ValueError, IllegalInstruction, RuntimeError) as e:
        print(f"simulator error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
