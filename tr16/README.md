# TR16: a tiny 16-bit RISC ISA with assembler and simulator

A from-scratch toolchain for an ISA I designed myself, structured like the CSE 112 project
(assembler, simulator with MEM / PC / RF / EE components, trace output, automated tests)
but with different design choices informed by the lectures on ISA design (RISC, fixed-width
encoding, load/store, condition flags, PC-relative branches).

```
python3 assembler.py prog.asm > prog.bin     # or: cat prog.asm | python3 assembler.py
python3 simulator.py prog.bin                # binary trace + 256-word memory dump
python3 simulator.py --pretty prog.bin       # readable trace with disassembly
python3 tests/run_tests.py                   # full test suite
```

## Machine model

| Item | Value |
|---|---|
| Word / instruction size | 16 bits, fixed width |
| Memory | 256 words, unified code + data (von Neumann), word addressed, PC is 8 bits |
| Registers | R0-R7, all 16 bits. **R0 always reads 0**, writes to it are ignored. Aliases: `zero`=R0, `sp`=R6, `lr`=R7 |
| FLAGS | N (bit 3), Z (bit 2), C (bit 1), V (bit 0). They keep their value until the next flag-setting instruction |
| Arithmetic | 16-bit two's complement, wraps on overflow and reports it through C and V |

Differences from the course ISA: signed immediates, wrap-around arithmetic with real carry/overflow
flags, persistent flags, a hardwired zero register, PC-relative branches, `jal`/`jr` for calls, and
`.word` data that may appear anywhere in the file (it is placed after the code).

## Instruction encodings (bits 15..0)

```
FP  : op(4) rd(3) rs(3) rt(3) func(3)          addf subf mulf divf (op 12, func 0-3)
FLI : op(4) rd(3) 0 enc8                       fli (op 13)
R   : op(4) rd(3) rs(3) rt(3) func(3)          add sub and or xor shl shr mul   (op 0), div mod (op 10)
RI  : op(4) rd(3) rs(3) imm6                   addi, ld, st  (imm6 signed -32..31)
LI  : op(4) rd(3) imm9                         li (signed -256..255), jal/b* use imm9 as PC-relative offset
LHI : op(4) rd(3) 0 imm8                       lhi
CMP : op(4) 000   rs(3) rt(3) 000              cmp
BR  : op(4) cond(3) off9                       b beq bne blt bge bgt ble blo
JR  : op(4) 000   rs(3) 000000                 jr
SHI : op(4) rd(3) rs(3) dir(1) 0 amt(4)        shli (dir 0), shri (dir 1)
HLT : 1111 000000000000
```

| Op | Mnemonic | Semantics | Flags |
|---|---|---|---|
| 0 | `add/sub/and/or/xor rd rs rt` | `rd = rs op rt` | N Z C V (logic ops clear C, V) |
| 0 | `shl/shr rd rs rt` | shift by `rt & 15`; C = last bit shifted out | N Z C |
| 0 | `mul rd rs rt` | low 16 bits of product; C = V = product truncated | N Z C V |
| 10 | `div/mod rd rs rt` | unsigned quotient / remainder; divide by zero gives 0 and sets V | N Z V |
| 1 | `addi rd rs imm` | `rd = rs + imm` | N Z C V |
| 2 | `li rd imm` | `rd = imm` (sign-extended); `imm` may also be a label or variable (its address) | none |
| 3 | `lhi rd imm8` | `rd = imm8 << 8 \| (rd & 0xFF)`; `li` + `lhi` builds any 16-bit constant | none |
| 4 | `ld rd [rs+imm]` | `rd = MEM[rs + imm]` (address wraps at 256) | none |
| 5 | `st rd [rs+imm]` | `MEM[rs + imm] = rd` | none |
| 6 | `cmp rs rt` | sets flags from `rs - rt`, writes nothing | N Z C V |
| 7 | `b/beq/bne/blt/bge/bgt/ble/blo label` | PC-relative branch if condition holds (signed, `blo` = unsigned <) | none |
| 8 | `jal rd label` | `rd = PC + 1`, jump to label | none |
| 9 | `jr rs` | `PC = rs` | none |
| 11 | `shli/shri rd rs amt` | shift by constant 0-15 | N Z C |
| 12 | `addf/subf/mulf/divf rd rs rt` | FP8 arithmetic on the low 8 bits (see below) | Z C V |
| 13 | `fli rd value` | load an FP8 constant, e.g. `fli r1 1.5` | none |
| 15 | `hlt` | stop | none |

`sub`/`cmp` set C when there is **no** borrow (`rs >= rt` unsigned), as on ARM.
Op 14 is reserved; executing one is a simulator error.

Pseudo-instructions (each expands to exactly one word): `mov rd rs` = `addi rd rs 0`,
`nop` = `add r0 r0 r0`, `call L` = `jal lr L`, `ret` = `jr lr`, `inc rd` / `dec rd` = `addi rd rd +-1`.

## Floating point (FP8)

Unsigned 8-bit minifloat held in the low 8 bits of a register (upper 8 bits written as zero):
3 exponent bits (bias 3), 5 mantissa bits, no sign.

- `e > 0`: value = (1 + m/32) x 2^(e-3); `e = 0`: value = (m/32) x 2^-2 (so 0x00 is 0)
- Range 0 to 31.5, e.g. 1.5 = `01110000`, 2.25 = `10000100`, 3.75 = `10011100`
- The assembler accepts only exactly representable constants (`fli r1 1.1` is an error)
- Results are computed exactly, then rounded to nearest (ties to even mantissa)
- Flags after an FP op: **Z** result is zero, **C** result was rounded (inexact), **V** invalid:
  result above 31.5, negative result (no sign bit), or divide by zero. On V the result is 0.

## Assembly syntax

```
        li   r1 arr          ; label/variable names can be used as addresses
loop:   ld   r2 [r1+0]       ; labels end with ':'; comments start with ';' or '//'
        ...
        hlt
.word arr 5 10 20 25         ; variable `arr` followed by initial words (default value 0)
```

Operands are separated by spaces or commas. Numbers can be decimal, `0x..` or `0b..`.

## Assembler errors

All errors are collected and printed as `error: line N: message` on stderr (exit status 1):
unknown mnemonic, invalid register, wrong operand count, immediate out of range, malformed
memory operand, undefined label/symbol, duplicate definition, reserved word used as a name,
branch to a variable, bad `.word`, unknown directive, missing `hlt`, program larger than memory.

## Simulator output

Per executed instruction (including `hlt`): `PC(8 bits) R0 ... R7 FLAGS` with registers in 16-bit
binary, then after halting the 256-word memory dump. `--max-steps` (default 100000) aborts
infinite loops with exit status 2.

## Layout

```
isa.py         opcodes, FP8 format, helpers, disassembler (single source of truth)
assembler.py   two-pass assembler: pass 1 assigns addresses, pass 2 encodes
machine.py     Memory, ProgramCounter, RegisterFile, ExecutionEngine
simulator.py   fetch / execute / trace loop and CLI
tests/         run_tests.py plus programs/ (expected final state) and errors/ (expected messages)

Design rule: each fact lives in one place. The assembler and simulator both read their opcode
tables from `isa.py`, every pseudo-instruction is one word (so addresses are a plain count), and
each instruction maps to one short branch of code in `assembler.encode` and `machine.step`.
```
