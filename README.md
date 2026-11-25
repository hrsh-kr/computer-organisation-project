# Computer Organisation Project

Coursework for a computer organisation course, containing my own 16-bit ISA called **TR16**,
with an assembler, a simulator, and automated tests.

## Contents

| Path | What it is |
|---|---|
| `tr16/` | The TR16 assembler, simulator, ISA definition and tests. See [`tr16/README.md`](tr16/README.md) for the full instruction set and design. |
| `tr16/tests/` | Test runner, plus assembly programs with expected results and error cases with expected messages. |
| `CO_project _2023_final.pdf` | The 2023 course project specification. |
| `Assembler_Simulator-main.zip` | Archive of the assembler and simulator project. |

## Quick start

Requires Python 3. Run everything from the `tr16/` directory:

```
cd tr16
python3 assembler.py prog.asm > prog.bin     # assemble (or: cat prog.asm | python3 assembler.py)
python3 simulator.py prog.bin                # run, printing a binary trace and memory dump
python3 simulator.py --pretty prog.bin       # run, printing a readable trace with disassembly
python3 tests/run_tests.py                   # run the full test suite
```

## What TR16 includes

- A 16-bit, fixed-width RISC instruction set with load/store, condition flags and PC-relative branches.
- An 8-bit floating-point format (FP8) with add, subtract, multiply and divide.
- A two-pass assembler that reports all errors with line numbers.
- A simulator that traces each executed instruction and stops on infinite loops.

## Notes

The lecture slides are not included in this repository.
