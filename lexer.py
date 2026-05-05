"""
STENO Lexer
Converts raw .sten source text into a flat stream of Token objects.
Handles indent/dedent detection for block-scoped parsing.
"""

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional


class TT(Enum):
    # ── Block keywords ────────────────────────────────────────────────────────
    LP   = auto()   # lp  / for    → for loop (range)
    WH   = auto()   # wh  / while  → while loop
    FN   = auto()   # fn  / def    → function definition
    CL   = auto()   # cl  / class  → class definition
    IF   = auto()   # if           → if
    EL   = auto()   # el  / else   → else / elif
    TR   = auto()   # tr  / try    → try
    EX   = auto()   # ex  / except → except
    WT   = auto()   # wt  / with   → with

    # ── Simple statement keywords ─────────────────────────────────────────────
    RT   = auto()   # rt  / return
    PR   = auto()   # pr  / print
    VR   = auto()   # vr  / var
    IM   = auto()   # im  / import
    FR   = auto()   # fr  / from   (also used in list comprehensions)
    YL   = auto()   # yl  / yield
    BR   = auto()   # br  / break
    CT   = auto()   # ct  / continue
    PS   = auto()   # ps  / pass
    DL   = auto()   # dl  / del
    GL   = auto()   # gl  / global
    NL   = auto()   # nl  / nonlocal
    AS_  = auto()   # as_ / assert  (AS_ avoids clash with Python 'as')

    # ── Literals ──────────────────────────────────────────────────────────────
    INT    = auto()
    FLOAT  = auto()
    STRING = auto()
    BOOL   = auto()
    NONE   = auto()

    # ── Identifier ────────────────────────────────────────────────────────────
    IDENT  = auto()

    # ── Operators ─────────────────────────────────────────────────────────────
    PLUS    = auto()
    MINUS   = auto()
    STAR    = auto()
    SLASH   = auto()
    DSLASH  = auto()   # //
    MOD     = auto()
    POW     = auto()   # **
    EQ      = auto()   # ==
    NEQ     = auto()   # !=
    LT      = auto()
    GT      = auto()
    LTE     = auto()
    GTE     = auto()
    AND     = auto()
    OR      = auto()
    NOT     = auto()
    IN      = auto()   # in
    IS      = auto()   # is
    ASSIGN  = auto()   # =
    PLUSEQ  = auto()   # +=
    MINUSEQ = auto()   # -=
    STAREQ  = auto()   # *=
    SLASHEQ = auto()   # /=
    DOT     = auto()
    DOTDOT  = auto()   # ..  range shorthand
    ARROW   = auto()   # ->

    # ── Delimiters ────────────────────────────────────────────────────────────
    LPAREN  = auto()
    RPAREN  = auto()
    LBRACK  = auto()
    RBRACK  = auto()
    LBRACE  = auto()
    RBRACE  = auto()
    COMMA   = auto()
    COLON   = auto()
    NEWLINE = auto()
    INDENT  = auto()
    DEDENT  = auto()
    EOF     = auto()
    COMMENT = auto()


# Maps both short tokens AND long-form aliases → TT
KEYWORDS: dict[str, TT] = {
    # ── short tokens ──────────────────────────
    "lp": TT.LP,   "wh": TT.WH,  "fn": TT.FN,  "cl": TT.CL,
    "if": TT.IF,   "el": TT.EL,  "tr": TT.TR,  "ex": TT.EX,
    "wt": TT.WT,   "rt": TT.RT,  "pr": TT.PR,  "vr": TT.VR,
    "im": TT.IM,   "fr": TT.FR,  "yl": TT.YL,  "br": TT.BR,
    "ct": TT.CT,   "ps": TT.PS,  "dl": TT.DL,  "gl": TT.GL,
    "nl": TT.NL,   "as": TT.AS_,
    # ── long-form aliases ──────────────────────
    "for":      TT.LP,   "while":    TT.WH,  "def":      TT.FN,
    "class":    TT.CL,   "else":     TT.EL,  "try":      TT.TR,
    "except":   TT.EX,   "with":     TT.WT,  "return":   TT.RT,
    "print":    TT.PR,   "var":      TT.VR,  "import":   TT.IM,
    "from":     TT.FR,   "yield":    TT.YL,  "break":    TT.BR,
    "continue": TT.CT,   "pass":     TT.PS,  "del":      TT.DL,
    "global":   TT.GL,   "nonlocal": TT.NL,  "assert":   TT.AS_,
    # ── built-in constants ────────────────────
    "True":  TT.BOOL,  "False": TT.BOOL,
    "None":  TT.NONE,
    # ── boolean operators ─────────────────────
    "and": TT.AND,  "or": TT.OR,  "not": TT.NOT,
    "in":  TT.IN,   "is": TT.IS,
}


@dataclass
class Token:
    type:  TT
    value: str
    line:  int
    col:   int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.col})"


class LexError(Exception):
    def __init__(self, msg: str, line: int, col: int):
        super().__init__(f"LexError at {line}:{col} — {msg}")
        self.line = line
        self.col  = col


# ─── Lexer ────────────────────────────────────────────────────────────────────

class Lexer:
    """
    Line-oriented lexer.  Processes one source line at a time so that
    INDENT/DEDENT tokens are emitted in the correct position before the
    first real token on each new indented line.
    """

    def __init__(self, source: str):
        self.source       = source
        self.indent_stack = [0]
        self.tokens: List[Token] = []

    # ── Public entry point ────────────────────────────────────────────────────

    def tokenize(self) -> List[Token]:
        lines = self.source.splitlines(keepends=False)
        for line_num, raw in enumerate(lines, start=1):
            # Blank line or comment-only line
            stripped = raw.lstrip()
            if not stripped or stripped.startswith("#"):
                if stripped.startswith("#"):
                    self.tokens.append(
                        Token(TT.COMMENT, stripped[1:].strip(), line_num, 1))
                continue

            indent = len(raw) - len(raw.lstrip(" \t"))
            self._handle_indent(indent, line_num)
            self._lex_line(raw.lstrip(), line_num, indent + 1)
            self.tokens.append(Token(TT.NEWLINE, "\n", line_num, len(raw) + 1))

        # Close all open indents
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            ln = len(lines)
            self.tokens.append(Token(TT.DEDENT, "", ln, 1))

        self.tokens.append(Token(TT.EOF, "", len(lines), 1))
        return self.tokens

    # ── Indent / Dedent ───────────────────────────────────────────────────────

    def _handle_indent(self, indent: int, line_num: int):
        current = self.indent_stack[-1]
        if indent > current:
            self.indent_stack.append(indent)
            self.tokens.append(Token(TT.INDENT, "", line_num, 1))
        elif indent < current:
            while self.indent_stack[-1] > indent:
                self.indent_stack.pop()
                self.tokens.append(Token(TT.DEDENT, "", line_num, 1))
            if self.indent_stack[-1] != indent:
                raise LexError("Inconsistent indentation", line_num, 1)

    # ── Line tokeniser ────────────────────────────────────────────────────────

    def _lex_line(self, line: str, line_num: int, base_col: int):
        pos = 0
        col = base_col

        def peek(o: int = 0) -> Optional[str]:
            i = pos + o
            return line[i] if i < len(line) else None

        def adv() -> str:
            nonlocal pos, col
            ch = line[pos]; pos += 1; col += 1
            return ch

        def match_ch(c: str) -> bool:
            nonlocal pos, col
            if pos < len(line) and line[pos] == c:
                pos += 1; col += 1; return True
            return False

        def emit(tt: TT, val: str, sc: int):
            self.tokens.append(Token(tt, val, line_num, sc))

        while pos < len(line):
            sc = col  # save start column

            ch = line[pos]

            # Whitespace
            if ch in " \t":
                adv(); continue

            # Comment
            if ch == "#":
                emit(TT.COMMENT, line[pos+1:].strip(), sc)
                break

            # String literals  ── single or double quoted, single-line only
            if ch in ('"', "'"):
                adv()
                buf, q = "", ch
                while pos < len(line) and line[pos] != q:
                    c2 = adv()
                    if c2 == "\\" and pos < len(line):
                        esc = adv()
                        buf += {"n":"\n","t":"\t","r":"\r",
                                "\\":"\\"," ":"'",'"':'"'}.get(esc, "\\"+esc)
                    else:
                        buf += c2
                if pos < len(line):
                    adv()   # closing quote
                else:
                    raise LexError("Unterminated string", line_num, sc)
                emit(TT.STRING, buf, sc)
                continue

            # Numbers (integer or float)
            if ch.isdigit():
                buf = ""
                while pos < len(line) and (line[pos].isdigit() or line[pos] == "."):
                    buf += adv()
                tt = TT.FLOAT if "." in buf else TT.INT
                emit(tt, buf, sc)
                continue

            # Identifiers / keywords
            if ch.isalpha() or ch == "_":
                buf = ""
                while pos < len(line) and (line[pos].isalnum() or line[pos] == "_"):
                    buf += adv()
                emit(KEYWORDS.get(buf, TT.IDENT), buf, sc)
                continue

            # Two-character operators (check before single-char)
            adv()   # consume first char
            if   ch == "." and match_ch("."): emit(TT.DOTDOT,  "..",  sc)
            elif ch == "=" and match_ch("="): emit(TT.EQ,      "==",  sc)
            elif ch == "!" and match_ch("="): emit(TT.NEQ,     "!=",  sc)
            elif ch == "<" and match_ch("="): emit(TT.LTE,     "<=",  sc)
            elif ch == ">" and match_ch("="): emit(TT.GTE,     ">=",  sc)
            elif ch == "+" and match_ch("="): emit(TT.PLUSEQ,  "+=",  sc)
            elif ch == "-":
                if match_ch("="): emit(TT.MINUSEQ, "-=", sc)
                elif match_ch(">"): emit(TT.ARROW,  "->", sc)
                else:             emit(TT.MINUS,   "-",  sc)
            elif ch == "*":
                if match_ch("*"):   emit(TT.POW,    "**", sc)
                elif match_ch("="): emit(TT.STAREQ, "*=", sc)
                else:               emit(TT.STAR,   "*",  sc)
            elif ch == "/":
                if match_ch("/"):   emit(TT.DSLASH,  "//", sc)
                elif match_ch("="): emit(TT.SLASHEQ, "/=", sc)
                else:               emit(TT.SLASH,   "/",  sc)
            # Single-char
            elif ch == "+": emit(TT.PLUS,   "+", sc)
            elif ch == "%": emit(TT.MOD,    "%", sc)
            elif ch == "<": emit(TT.LT,     "<", sc)
            elif ch == ">": emit(TT.GT,     ">", sc)
            elif ch == "=": emit(TT.ASSIGN, "=", sc)
            elif ch == "(": emit(TT.LPAREN, "(", sc)
            elif ch == ")": emit(TT.RPAREN, ")", sc)
            elif ch == "[": emit(TT.LBRACK, "[", sc)
            elif ch == "]": emit(TT.RBRACK, "]", sc)
            elif ch == "{": emit(TT.LBRACE, "{", sc)
            elif ch == "}": emit(TT.RBRACE, "}", sc)
            elif ch == ",": emit(TT.COMMA,  ",", sc)
            elif ch == ":": emit(TT.COLON,  ":", sc)
            elif ch == ".": emit(TT.DOT,    ".", sc)
            else:
                raise LexError(f"Unexpected character '{ch}'", line_num, sc)
