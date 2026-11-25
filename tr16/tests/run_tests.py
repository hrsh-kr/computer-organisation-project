#!/usr/bin/env python3
"""End-to-end tests: assembler -> simulator, checked against `; expect:` lines.

programs/*.asm   must assemble and halt; `; expect: r1=55 mem[10]=3 mem[total]=7 flags=6`
errors/*.asm     must fail to assemble;  `; expect-error: line 3: unknown mnemonic`
"""
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def tool(script, *args, stdin=""):
    return subprocess.run([sys.executable, os.path.join(ROOT, script), *args],
                          input=stdin, capture_output=True, text=True)


def header(path, key):
    for line in open(path):
        m = re.match(rf"\s*;\s*{key}:\s*(.*)", line)
        if m:
            return m.group(1).strip()
    return None


def run_program(path):
    asm = tool("assembler.py", path, "--symbols")
    if asm.returncode:
        return f"assembly failed: {asm.stderr.strip()}"
    symbols = dict(l.split("=") for l in asm.stderr.split())
    sim = tool("simulator.py", stdin=asm.stdout)
    if sim.returncode:
        return f"simulation failed: {sim.stderr.strip()}"
    lines = sim.stdout.splitlines()
    if len(lines) < 257:
        return "trace + memory dump too short"
    mem = [int(l, 2) for l in lines[-256:]]
    fields = lines[-257].split()
    regs = [int(x, 2) for x in fields[1:9]]
    flags = int(fields[9], 2)
    problems = []
    for item in (header(path, "expect") or "").split():
        key, want = item.split("=")
        want = int(want, 0)
        if key == "flags":
            got = flags
        elif key.startswith("mem["):
            addr = key[4:-1]
            got = mem[int(symbols[addr]) if addr in symbols else int(addr, 0)]
        else:
            got = regs[int(key[1:])]
        if got != want:
            problems.append(f"{key}: expected {want}, got {got}")
    return "; ".join(problems)


def run_error(path):
    want = header(path, "expect-error")
    asm = tool("assembler.py", path)
    if asm.returncode == 0:
        return "assembled without errors"
    if want not in asm.stderr:
        return f"expected '{want}' in: {asm.stderr.strip()}"
    return ""


def main():
    failures = total = 0
    for kind, runner in (("programs", run_program), ("errors", run_error)):
        for path in sorted(glob.glob(os.path.join(HERE, kind, "*.asm"))):
            total += 1
            problem = runner(path)
            name = f"{kind}/{os.path.basename(path)}"
            print(("PASS " if not problem else "FAIL ") + name + (f"  -> {problem}" if problem else ""))
            failures += bool(problem)
    print(f"\n{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
