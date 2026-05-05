# STENO — Final Project Submission
**CS420 | Laila Brown & Ashley Gutierrez Carreto**

---

## Running the interpreter

```bash
# Run any .sten file
python steno.py run examples/hello_world.sten

# Run all 5 examples at once
python steno.py demo

# Interactive REPL
python steno.py

# Transpile to Python (backup/export)
python steno.py compile examples/fizzbuzz.sten

# Debug tools
python steno.py tokens examples/fizzbuzz.sten   # token stream
python steno.py ast    examples/fizzbuzz.sten   # AST dump
python steno.py check  examples/fizzbuzz.sten   # syntax check only
```

---

## The Five Programs

| File | Type | What it demonstrates |
|------|------|----------------------|
| `hello_world.sten` | Simple (1) | `pr`, `vr`, string literals, arithmetic operators |
| `calculator.sten` | Simple (2) | `fn`, `rt`, `if`/`el if`/`el`, function calls, error handling |
| `list_ops.sten` | Simple (3) | `vr`, `lp`, `wh`, list comprehensions, augmented assignment |
| `fizzbuzz.sten` | FizzBuzz (d) | `lp .. `, `if`/`el if`/`el`, `pr`, modulo |
| `data_structures.sten` | Complex (c) | `cl`, recursion, `Stack` class, binary search, Caesar cipher, word frequency |

---

## STENO Token Reference

| Short token | Long-form alias | Python equivalent |
|-------------|----------------|-------------------|
| `lp i .. 0 10` | `for i .. 0 10` | `for i in range(0, 10):` |
| `lp x items` | `for x items` | `for x in items:` |
| `wh x > 0` | `while x > 0` | `while x > 0:` |
| `fn add a b` | `def add a b` | `def add(a, b):` |
| `cl Stack` | `class Stack` | `class Stack:` |
| `rt x + y` | `return x + y` | `return x + y` |
| `if x > 0` | `if x > 0` | `if x > 0:` |
| `el` | `else` | `else:` |
| `el if x == 0` | `else if x == 0` | `elif x == 0:` |
| `pr "hello"` | `print "hello"` | `print("hello")` |
| `vr x = 5` | `var x = 5` | `x = 5` |
| `im math` | `import math` | `import math` |
| `fr math im sqrt` | `from math im sqrt` | `from math import sqrt` |
| `tr` | `try` | `try:` |
| `ex Exception` | `except Exception` | `except Exception:` |
| `br` / `ct` / `ps` | `break` / `continue` / `pass` | same |
| `[x fr items if c]` | — | `[x for x in items if c]` |

---

## Architecture

```
your_file.sten
      │
      ▼  lexer.py
   Token stream   (TT enum, Token dataclass)
      │
      ▼  parser.py
   AST             (ast_nodes.py dataclasses)
      │
      ├──▶  interpreter.py   (tree-walk, direct execution)
      │
      └──▶  transpiler.py    (AST → Python source string)
```

`steno.py` wires everything together and provides the CLI + REPL.

---

## Keyboard Setup (Plover)

**Your actual key map** (as configured on your steno keyboard):

```
Top row:    Q=S  W=T  E=P  R=H  T=*  Y=*  U=-F  I=-P  O=-L  P=-T  [=-D
Home row:   A=S  S=K  D=W  F=R  G=*  H=*  J=-R  K=-B  L=-G  ;=-S  '=-Z
Bottom row: C=a  V=o  N=e  M=u
Number bar: 1-0 all produce #
```

**Standard steno order:** `# S T K P W H R * A O - E U F R P B L G T S D Z`

Load `plover/steno_lang_dict.json` in Plover **above** your main dictionary.
NKRO (N-Key Rollover) is required — verify at keyboardtester.com.
