"""
STENO AST Nodes
Plain dataclass containers — no logic.
The parser writes these; the interpreter and transpiler read them.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional


# ── Base ──────────────────────────────────────────────────────────────────────

@dataclass
class Node:
    line: int = field(default=0, repr=False)


# ── Statements ────────────────────────────────────────────────────────────────

@dataclass
class Program(Node):
    body: List[Any] = field(default_factory=list)

@dataclass
class ExprStmt(Node):
    expr: Any = None

@dataclass
class VarDecl(Node):
    name:  str = ""
    value: Any = None          # Optional initialiser expression

@dataclass
class Assign(Node):
    target: Any = None
    op:     str = "="          # =  +=  -=  *=  /=
    value:  Any = None

@dataclass
class PrintStmt(Node):
    args: List[Any] = field(default_factory=list)

@dataclass
class ReturnStmt(Node):
    value: Any = None

@dataclass
class YieldStmt(Node):
    value: Any = None

@dataclass
class BreakStmt(Node):
    pass

@dataclass
class ContinueStmt(Node):
    pass

@dataclass
class PassStmt(Node):
    pass

@dataclass
class DelStmt(Node):
    target: Any = None

@dataclass
class GlobalStmt(Node):
    names: List[str] = field(default_factory=list)

@dataclass
class NonlocalStmt(Node):
    names: List[str] = field(default_factory=list)

@dataclass
class AssertStmt(Node):
    test: Any = None
    msg:  Any = None

@dataclass
class ImportStmt(Node):
    module:  str            = ""
    alias:   Optional[str]  = None
    names:   Optional[List[str]] = None   # from X import a, b

@dataclass
class FuncDef(Node):
    name:       str            = ""
    params:     List[str]      = field(default_factory=list)
    defaults:   dict           = field(default_factory=dict)
    body:       List[Any]      = field(default_factory=list)
    decorators: List[Any]      = field(default_factory=list)

@dataclass
class ClassDef(Node):
    name:  str       = ""
    bases: List[Any] = field(default_factory=list)
    body:  List[Any] = field(default_factory=list)

@dataclass
class IfStmt(Node):
    condition:    Any      = None
    then_body:    List[Any] = field(default_factory=list)
    elif_clauses: List[Any] = field(default_factory=list)  # [(cond, body), ...]
    else_body:    Optional[List[Any]] = None

@dataclass
class ForLoop(Node):
    """lp var .. start stop [step]  →  for var in range(start, stop[, step])"""
    var:   str = ""
    start: Any = None
    stop:  Any = None
    step:  Any = None
    body:  List[Any] = field(default_factory=list)

@dataclass
class ForInLoop(Node):
    """lp var iterable  →  for var in iterable"""
    var:      str = ""
    iterable: Any = None
    body:     List[Any] = field(default_factory=list)

@dataclass
class WhileLoop(Node):
    condition: Any      = None
    body:      List[Any] = field(default_factory=list)

@dataclass
class TryStmt(Node):
    body:         List[Any]           = field(default_factory=list)
    handlers:     List[Any]           = field(default_factory=list)  # [(type, name, body)]
    else_body:    Optional[List[Any]] = None
    finally_body: Optional[List[Any]] = None

@dataclass
class WithStmt(Node):
    context: Any           = None
    alias:   Optional[str] = None
    body:    List[Any]     = field(default_factory=list)


# ── Expressions ───────────────────────────────────────────────────────────────

@dataclass
class IntLit(Node):
    value: int = 0

@dataclass
class FloatLit(Node):
    value: float = 0.0

@dataclass
class StrLit(Node):
    value: str = ""

@dataclass
class BoolLit(Node):
    value: bool = True

@dataclass
class NoneLit(Node):
    pass

@dataclass
class Name(Node):
    name: str = ""

@dataclass
class BinOp(Node):
    op:    str = ""
    left:  Any = None
    right: Any = None

@dataclass
class UnaryOp(Node):
    op:      str = ""
    operand: Any = None

@dataclass
class Compare(Node):
    left:        Any       = None
    ops:         List[str] = field(default_factory=list)
    comparators: List[Any] = field(default_factory=list)

@dataclass
class BoolOp(Node):
    op:     str      = "and"   # "and" | "or"
    values: List[Any] = field(default_factory=list)

@dataclass
class Call(Node):
    func:   Any      = None
    args:   List[Any] = field(default_factory=list)
    kwargs: List[Any] = field(default_factory=list)  # [(name, value), ...]

@dataclass
class Index(Node):
    obj:   Any = None
    index: Any = None

@dataclass
class Slice(Node):
    obj:   Any = None
    lower: Any = None
    upper: Any = None
    step:  Any = None

@dataclass
class Attr(Node):
    obj:  Any = None
    attr: str = ""

@dataclass
class ListLit(Node):
    elements: List[Any] = field(default_factory=list)

@dataclass
class DictLit(Node):
    pairs: List[Any] = field(default_factory=list)   # [(key, val), ...]

@dataclass
class SetLit(Node):
    elements: List[Any] = field(default_factory=list)

@dataclass
class TupleLit(Node):
    elements: List[Any] = field(default_factory=list)

@dataclass
class ListComp(Node):
    expr:      Any = None
    var:       str = ""
    iterable:  Any = None
    condition: Any = None

@dataclass
class DictComp(Node):
    key_expr:  Any = None
    val_expr:  Any = None
    var:       str = ""
    iterable:  Any = None
    condition: Any = None

@dataclass
class Lambda(Node):
    params: List[str] = field(default_factory=list)
    body:   Any       = None

@dataclass
class Ternary(Node):
    condition: Any = None
    then_expr: Any = None
    else_expr: Any = None
