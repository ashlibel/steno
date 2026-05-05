#!/usr/bin/env python3
"""
steno — STENO language CLI & REPL

Usage:
    python steno.py                        # interactive REPL
    python steno.py run   <file.sten>      # interpret a file
    python steno.py compile <file.sten>    # transpile → .py
    python steno.py check   <file.sten>    # syntax check only
    python steno.py tokens  <file.sten>    # dump token stream
    python steno.py ast     <file.sten>    # dump AST
    python steno.py demo                   # run all example files
"""

import sys
import os
import argparse

from lexer       import Lexer,       LexError
from parser      import Parser,      ParseError
from interpreter import Interpreter, RuntimeError_
from transpiler  import Transpiler,  TranspileError


BANNER = r"""
  ╔══════════════════════════════════════════════════════╗
  ║   ███████╗████████╗███████╗███╗   ██╗ ██████╗       ║
  ║   ██╔════╝╚══██╔══╝██╔════╝████╗  ██║██╔═══██╗      ║
  ║   ███████╗   ██║   █████╗  ██╔██╗ ██║██║   ██║      ║
  ║   ╚════██║   ██║   ██╔══╝  ██║╚██╗██║██║   ██║      ║
  ║   ███████║   ██║   ███████╗██║ ╚████║╚██████╔╝      ║
  ║   ╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═══╝ ╚═════╝       ║
  ║                                                      ║
  ║   Stenography-inspired programming language v1.0     ║
  ║   Type  help  for commands,  quit  to exit           ║
  ╚══════════════════════════════════════════════════════╝
"""

REPL_HELP = """
┌─ REPL Commands ──────────────────────────────────────────┐
│  help          Show this message                         │
│  python        Show generated Python for last input      │
│  tokens        Show token stream for last input          │
│  ast           Show AST for last input                   │
│  clear         Reset session state                       │
│  quit / exit   Exit the REPL                             │
└──────────────────────────────────────────────────────────┘

┌─ STENO Quick Reference ──────────────────────────────────┐
│  lp i .. 0 10        for i in range(0, 10)               │
│  lp x items          for x in items                      │
│  wh x > 0            while x > 0:                        │
│  fn add a b          def add(a, b):                      │
│  rt x + y            return x + y                        │
│  if x > 0            if x > 0:                           │
│  el                  else:                               │
│  el if x == 0        elif x == 0:                        │
│  pr "hello"          print("hello")                      │
│  vr x = 5            x = 5                               │
│  im math             import math                         │
│  fr math im sqrt     from math import sqrt               │
│  cl Stack            class Stack:                        │
│  tr / ex Exception   try / except Exception:             │
│  [x fr items if c]   [x for x in items if c]            │
│                                                          │
│  Long-form aliases always work:                          │
│  for / while / def / class / return / print / etc.       │
└──────────────────────────────────────────────────────────┘
"""


# ── Pipeline helpers ──────────────────────────────────────────────────────────

def lex(source: str):
    return Lexer(source).tokenize()

def parse(source: str):
    tokens = lex(source)
    return Parser(tokens).parse()

def interpret(source: str, filename: str = "<steno>"):
    tree = parse(source)
    interp = Interpreter()
    interp.run(tree)
    return interp

def compile_to_python(source: str) -> str:
    tree = parse(source)
    return Transpiler().transpile(tree)


# ── Subcommand handlers ───────────────────────────────────────────────────────

def cmd_run(args):
    path = args.file
    if not os.path.exists(path):
        print(f"steno: file not found: {path}", file=sys.stderr); sys.exit(1)
    with open(path) as f:
        source = f.read()
    try:
        interpret(source, path)
    except (LexError, ParseError, TranspileError, RuntimeError_) as e:
        print(f"\nsteno error: {e}", file=sys.stderr); sys.exit(1)
    except Exception as e:
        print(f"\nruntime error: {e}", file=sys.stderr); sys.exit(1)


def cmd_compile(args):
    path = args.file
    with open(path) as f: source = f.read()
    out = path.replace(".sten", ".py")
    try:
        py = compile_to_python(source)
        with open(out, "w") as f: f.write(py)
        print(f"Compiled → {out}")
    except (LexError, ParseError, TranspileError) as e:
        print(f"steno error: {e}", file=sys.stderr); sys.exit(1)


def cmd_check(args):
    with open(args.file) as f: source = f.read()
    try:
        parse(source)
        print(f"✓ {args.file} is valid STENO")
    except (LexError, ParseError) as e:
        print(f"✗ {e}", file=sys.stderr); sys.exit(1)


def cmd_tokens(args):
    with open(args.file) as f: source = f.read()
    for t in lex(source):
        print(t)


def cmd_ast(args):
    with open(args.file) as f: source = f.read()
    _print_ast(parse(args.file and source), 0)


def cmd_demo(args):
    """Run all example .sten files in order."""
    examples_dir = os.path.join(os.path.dirname(__file__), "examples")
    order = [
        "hello_world.sten",
        "calculator.sten",
        "list_ops.sten",
        "fizzbuzz.sten",
        "data_structures.sten",
    ]
    for name in order:
        path = os.path.join(examples_dir, name)
        if not os.path.exists(path):
            print(f"  [skip] {name} not found")
            continue
        print(f"\n{'='*60}")
        print(f"  Running: {name}")
        print(f"{'='*60}")
        with open(path) as f: source = f.read()
        try:
            interpret(source, path)
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)


def _print_ast(node, depth: int):
    pad = "  " * depth
    if hasattr(node, "__dataclass_fields__"):
        print(f"{pad}{type(node).__name__}(")
        for field in node.__dataclass_fields__:
            if field == "line": continue
            val = getattr(node, field)
            if isinstance(val, list):
                print(f"{pad}  {field}=[")
                for item in val:
                    _print_ast(item, depth + 2)
                print(f"{pad}  ]")
            elif hasattr(val, "__dataclass_fields__"):
                print(f"{pad}  {field}=")
                _print_ast(val, depth + 2)
            else:
                print(f"{pad}  {field}={val!r}")
        print(f"{pad})")
    elif isinstance(node, (list, tuple)):
        for item in node:
            _print_ast(item, depth)
    else:
        print(f"{pad}{node!r}")


# ── REPL ──────────────────────────────────────────────────────────────────────

class REPL:
    def __init__(self):
        self.interp      = Interpreter()
        self.last_source = ""

    def run(self):
        print(BANNER)
        while True:
            try:
                line = input("steno> ").rstrip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!"); break

            if not line:
                continue

            stripped = line.strip()

            # ── Meta commands ─────────────────────────────────────────────────
            if stripped == "quit" or stripped == "exit":
                print("Goodbye!"); break
            if stripped == "help":
                print(REPL_HELP); continue
            if stripped == "clear":
                self.interp = Interpreter()
                print("Session cleared."); continue
            if stripped == "python" and self.last_source:
                try:
                    py = compile_to_python(self.last_source)
                    for l in py.splitlines()[2:]:
                        print(f"  {l}")
                except Exception as e:
                    print(f"  Error: {e}")
                continue
            if stripped == "tokens" and self.last_source:
                try:
                    for t in lex(self.last_source):
                        print(f"  {t}")
                except Exception as e:
                    print(f"  Error: {e}")
                continue
            if stripped == "ast" and self.last_source:
                try:
                    _print_ast(parse(self.last_source), 1)
                except Exception as e:
                    print(f"  Error: {e}")
                continue

            # ── Multiline block collection ────────────────────────────────────
            source = self._collect(line)
            if source is None:
                continue
            self.last_source = source

            # ── Execute ───────────────────────────────────────────────────────
            try:
                tree = parse(source)
                self.interp.run(tree)
            except (LexError, ParseError) as e:
                print(f"  {e}")
            except RuntimeError_ as e:
                print(f"  {e}")
            except Exception as e:
                print(f"  Error: {e}")

    def _is_block_header(self, line: str) -> bool:
        """Returns True if this line opens a block (fn, if, lp, wh, cl, tr, etc.)"""
        from lexer import TT
        BLOCK_STARTERS = {TT.FN, TT.IF, TT.EL, TT.LP, TT.WH, TT.CL, TT.TR, TT.EX, TT.WT}
        try:
            tokens = [t for t in Lexer(line).tokenize()
                      if t.type not in (TT.NEWLINE, TT.EOF, TT.COMMENT)]
            return bool(tokens) and tokens[0].type in BLOCK_STARTERS
        except Exception:
            return False

    def _collect(self, first_line: str) -> str:
        """For block-opening statements, collect indented body lines."""
        if not self._is_block_header(first_line):
            return first_line

        print("...  (indent body lines, blank line to finish)")
        lines = [first_line]
        while True:
            try:
                cont = input("...  ")
            except (EOFError, KeyboardInterrupt):
                return None
            if cont == "":
                break
            lines.append(cont)
        return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        prog="steno",
        description="The STENO programming language — stenography-speed coding."
    )
    sub = ap.add_subparsers(dest="command")

    p_run     = sub.add_parser("run",     help="Interpret a .sten file")
    p_run.add_argument("file")

    p_compile = sub.add_parser("compile", help="Transpile .sten → .py")
    p_compile.add_argument("file")

    p_check   = sub.add_parser("check",   help="Syntax-check a .sten file")
    p_check.add_argument("file")

    p_tokens  = sub.add_parser("tokens",  help="Dump token stream (debug)")
    p_tokens.add_argument("file")

    p_ast     = sub.add_parser("ast",     help="Dump AST (debug)")
    p_ast.add_argument("file")

    sub.add_parser("demo", help="Run all example programs")

    args = ap.parse_args()

    dispatch = {
        "run":     cmd_run,
        "compile": cmd_compile,
        "check":   cmd_check,
        "tokens":  cmd_tokens,
        "ast":     cmd_ast,
        "demo":    cmd_demo,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        REPL().run()


if __name__ == "__main__":
    main()
