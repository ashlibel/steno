"""
STENO Parser — recursive descent, produces an AST from a token stream.
"""

from typing import List, Optional
from lexer import TT, Token
import ast_nodes as N


class ParseError(Exception):
    def __init__(self, msg: str, line: int, col: int):
        super().__init__(f"ParseError at {line}:{col} — {msg}")
        self.line = line
        self.col  = col


class Parser:
    def __init__(self, tokens: List[Token]):
        # Strip comments--> they have NO semantic menaning 
        self.tokens = [t for t in tokens if t.type != TT.COMMENT]
        self.pos    = 0

    # helpers 

    def peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else self.tokens[-1]

    def check(self, *types: TT) -> bool:
        return self.peek().type in types

    def advance(self) -> Token:
        t = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return t

    def consume(self, tt: TT, msg: str) -> Token:
        t = self.peek()
        if t.type != tt:
            raise ParseError(
                f"Expected {tt.name}, got {t.type.name} ({t.value!r}). {msg}",
                t.line, t.col)
        return self.advance()

    def match(self, *types: TT) -> Optional[Token]:
        if self.check(*types):
            return self.advance()
        return None

    def skip_newlines(self):
        while self.check(TT.NEWLINE):
            self.advance()

    def ln(self) -> int:
        return self.peek().line

    def parse(self) -> N.Program:
        self.skip_newlines()
        body = []
        while not self.check(TT.EOF):
            s = self.parse_stmt()
            if s is not None:
                body.append(s)
            self.skip_newlines()
        return N.Program(body=body, line=1)

    def parse_block(self) -> List[N.Node]:
        """Expect an INDENT, parse statements, expect DEDENT."""
        has_indent = bool(self.match(TT.INDENT))
        stmts = []
        self.skip_newlines()
        while not self.check(TT.DEDENT, TT.EOF):
            s = self.parse_stmt()
            if s is not None:
                stmts.append(s)
            self.skip_newlines()
        if has_indent:
            self.match(TT.DEDENT)
        if not stmts:
            stmts.append(N.PassStmt(line=self.ln()))
        return stmts

    # ── Statements ────────────────────────────────────────────────────────────

    def parse_stmt(self) -> Optional[N.Node]:
        t = self.peek()

        if t.type == TT.NEWLINE:            self.advance(); return None
        if t.type == TT.VR:                 return self._var_decl()
        if t.type == TT.FN:                 return self._func_def()
        if t.type == TT.CL:                 return self._class_def()
        if t.type == TT.IF:                 return self._if_stmt()
        if t.type == TT.LP:                 return self._for_loop()
        if t.type == TT.WH:                 return self._while_loop()
        if t.type == TT.TR:                 return self._try_stmt()
        if t.type == TT.WT:                 return self._with_stmt()
        if t.type == TT.PR:                 return self._print_stmt()
        if t.type == TT.IM:                 return self._import_stmt()
        if t.type == TT.RT:                 return self._return_stmt()
        if t.type == TT.YL:                 return self._yield_stmt()
        if t.type == TT.BR:                 self.advance(); self._end(); return N.BreakStmt(line=t.line)
        if t.type == TT.CT:                 self.advance(); self._end(); return N.ContinueStmt(line=t.line)
        if t.type == TT.PS:                 self.advance(); self._end(); return N.PassStmt(line=t.line)
        if t.type == TT.DL:                 return self._del_stmt()
        if t.type == TT.GL:                 return self._global_stmt()
        if t.type == TT.NL:                 return self._nonlocal_stmt()
        if t.type == TT.AS_:                return self._assert_stmt()
        if t.type == TT.FR:                 return self._from_import()
        return self._expr_or_assign()

    def _end(self):
        """Consume optional newline at end of statement."""
        self.match(TT.NEWLINE)

    def _end_required(self):
        if not self.check(TT.NEWLINE, TT.EOF, TT.DEDENT):
            raise ParseError("Expected end of statement",
                             self.peek().line, self.peek().col)
        self.match(TT.NEWLINE)

    # ── Individual statement parsers ──────────────────────────────────────────

    def _var_decl(self) -> N.VarDecl:
        line = self.ln(); self.advance()
        name = self.consume(TT.IDENT, "Expected variable name after 'vr'").value
        val  = None
        if self.match(TT.ASSIGN):
            val = self.parse_expr()
        self._end_required()
        return N.VarDecl(name=name, value=val, line=line)

    def _func_def(self) -> N.FuncDef:
        line = self.ln(); self.advance()
        name = self.consume(TT.IDENT, "Expected function name after 'fn'").value
        params, defaults = [], {}
        if self.match(TT.LPAREN):
            while not self.check(TT.RPAREN, TT.EOF):
                p = self.consume(TT.IDENT, "Expected param name").value
                params.append(p)
                if self.match(TT.ASSIGN):
                    defaults[p] = self.parse_expr()
                self.match(TT.COMMA)
            self.consume(TT.RPAREN, "Expected ')'")
        else:
            # Space-separated params until newline
            while self.check(TT.IDENT) and not self.check(TT.NEWLINE):
                params.append(self.advance().value)
        self._end_required()
        body = self.parse_block()
        return N.FuncDef(name=name, params=params, defaults=defaults,
                         body=body, line=line)

    def _class_def(self) -> N.ClassDef:
        line = self.ln(); self.advance()
        name = self.consume(TT.IDENT, "Expected class name after 'cl'").value
        bases = []
        if self.match(TT.LPAREN):
            while not self.check(TT.RPAREN, TT.EOF):
                bases.append(self.parse_expr()); self.match(TT.COMMA)
            self.consume(TT.RPAREN, "Expected ')'")
        self._end_required()
        body = self.parse_block()
        return N.ClassDef(name=name, bases=bases, body=body, line=line)

    def _if_stmt(self) -> N.IfStmt:
        line = self.ln(); self.advance()
        cond = self.parse_expr()
        self._end_required()
        then_body    = self.parse_block()
        elif_clauses = []
        else_body    = None

        while self.match(TT.EL):
            if self.check(TT.IF):
                self.advance()
                ec = self.parse_expr(); self._end_required()
                elif_clauses.append((ec, self.parse_block()))
            else:
                self._end_required()
                else_body = self.parse_block()
                break

        return N.IfStmt(condition=cond, then_body=then_body,
                        elif_clauses=elif_clauses, else_body=else_body,
                        line=line)

    def _for_loop(self) -> N.Node:
        line = self.ln(); self.advance()
        var  = self.consume(TT.IDENT, "Expected loop variable after 'lp'").value

        if self.match(TT.DOTDOT):
            # lp i .. start stop [step]
            start = self._primary()
            stop  = self._primary()
            step  = None
            if not self.check(TT.NEWLINE, TT.EOF, TT.DEDENT):
                step = self._primary()
            self._end_required()
            body = self.parse_block()
            return N.ForLoop(var=var, start=start, stop=stop, step=step,
                             body=body, line=line)
        else:
            # lp x iterable   or   lp x in iterable
            if self.check(TT.IN):
                self.advance()
            iterable = self.parse_expr()
            self._end_required()
            body = self.parse_block()
            return N.ForInLoop(var=var, iterable=iterable, body=body, line=line)

    def _while_loop(self) -> N.WhileLoop:
        line = self.ln(); self.advance()
        cond = self.parse_expr(); self._end_required()
        body = self.parse_block()
        return N.WhileLoop(condition=cond, body=body, line=line)

    def _try_stmt(self) -> N.TryStmt:
        line = self.ln(); self.advance(); self._end_required()
        body     = self.parse_block()
        handlers = []
        finally_body = None
        while self.check(TT.EX):
            self.advance()
            exc_type = exc_name = None
            if not self.check(TT.NEWLINE, TT.EOF):
                exc_type = self.parse_expr()
                if self.peek().type == TT.IDENT and self.peek().value == "as":
                    self.advance()
                    exc_name = self.consume(TT.IDENT, "Expected exception var").value
            self._end_required()
            handlers.append((exc_type, exc_name, self.parse_block()))
        if self.peek().type == TT.IDENT and self.peek().value == "finally":
            self.advance(); self._end_required()
            finally_body = self.parse_block()
        return N.TryStmt(body=body, handlers=handlers,
                         finally_body=finally_body, line=line)

    def _with_stmt(self) -> N.WithStmt:
        line = self.ln(); self.advance()
        ctx   = self.parse_expr()
        alias = None
        if self.peek().type == TT.IDENT and self.peek().value == "as":
            self.advance()
            alias = self.consume(TT.IDENT, "Expected alias").value
        self._end_required()
        body = self.parse_block()
        return N.WithStmt(context=ctx, alias=alias, body=body, line=line)

    def _print_stmt(self) -> N.PrintStmt:
        line = self.ln(); self.advance()
        args = []
        while not self.check(TT.NEWLINE, TT.EOF, TT.DEDENT):
            args.append(self.parse_expr()); self.match(TT.COMMA)
        self._end()
        return N.PrintStmt(args=args, line=line)

    def _import_stmt(self) -> N.ImportStmt:
        line = self.ln(); self.advance()
        parts = [self.consume(TT.IDENT, "Expected module name").value]
        while self.match(TT.DOT):
            parts.append(self.consume(TT.IDENT, "Expected module name").value)
        module = ".".join(parts)
        alias  = None
        if self.peek().type == TT.IDENT and self.peek().value == "as":
            self.advance()
            alias = self.consume(TT.IDENT, "Expected alias").value
        self._end_required()
        return N.ImportStmt(module=module, alias=alias, line=line)

    def _from_import(self) -> N.ImportStmt:
        """fr math im sqrt, cos"""
        line = self.ln(); self.advance()
        parts = [self.consume(TT.IDENT, "Expected module name").value]
        while self.match(TT.DOT):
            parts.append(self.consume(TT.IDENT, "Expected module name").value)
        module = ".".join(parts)
        self.consume(TT.IM, "Expected 'im' after module name in from-import")
        names = [self.consume(TT.IDENT, "Expected name").value]
        while self.match(TT.COMMA):
            names.append(self.consume(TT.IDENT, "Expected name").value)
        self._end_required()
        return N.ImportStmt(module=module, names=names, line=line)

    def _return_stmt(self) -> N.ReturnStmt:
        line = self.ln(); self.advance()
        val  = None
        if not self.check(TT.NEWLINE, TT.EOF, TT.DEDENT):
            val = self.parse_expr()
        self._end()
        return N.ReturnStmt(value=val, line=line)

    def _yield_stmt(self) -> N.YieldStmt:
        line = self.ln(); self.advance()
        val  = None
        if not self.check(TT.NEWLINE, TT.EOF, TT.DEDENT):
            val = self.parse_expr()
        self._end()
        return N.YieldStmt(value=val, line=line)

    def _del_stmt(self) -> N.DelStmt:
        line = self.ln(); self.advance()
        t = self.parse_expr(); self._end_required()
        return N.DelStmt(target=t, line=line)

    def _global_stmt(self) -> N.GlobalStmt:
        line = self.ln(); self.advance()
        names = [self.consume(TT.IDENT, "Expected name").value]
        while self.match(TT.COMMA):
            names.append(self.consume(TT.IDENT, "Expected name").value)
        self._end_required()
        return N.GlobalStmt(names=names, line=line)

    def _nonlocal_stmt(self) -> N.NonlocalStmt:
        line = self.ln(); self.advance()
        names = [self.consume(TT.IDENT, "Expected name").value]
        while self.match(TT.COMMA):
            names.append(self.consume(TT.IDENT, "Expected name").value)
        self._end_required()
        return N.NonlocalStmt(names=names, line=line)

    def _assert_stmt(self) -> N.AssertStmt:
        line = self.ln(); self.advance()
        test = self.parse_expr()
        msg  = self.parse_expr() if self.match(TT.COMMA) else None
        self._end_required()
        return N.AssertStmt(test=test, msg=msg, line=line)

    def _expr_or_assign(self) -> N.Node:
        line = self.ln()
        expr = self.parse_expr()
        ASSIGN_OPS = {
            TT.ASSIGN: "=", TT.PLUSEQ: "+=",
            TT.MINUSEQ: "-=", TT.STAREQ: "*=", TT.SLASHEQ: "/=",
        }
        for tt, op in ASSIGN_OPS.items():
            if self.match(tt):
                val = self.parse_expr(); self._end()
                return N.Assign(target=expr, op=op, value=val, line=line)
        self._end()
        return N.ExprStmt(expr=expr, line=line)

    # ── Expression hierarchy (lowest → highest precedence) ────────────────────

    def parse_expr(self):
        return self._ternary()

    def _ternary(self):
        line = self.ln()
        expr = self._bool_op()
        # expr if cond el alt
        if self.check(TT.IF):
            self.advance()
            cond = self._bool_op()
            self.consume(TT.EL, "Expected 'el' in ternary expression")
            alt  = self._ternary()
            return N.Ternary(condition=cond, then_expr=expr,
                             else_expr=alt, line=line)
        return expr

    def _bool_op(self):
        line = self.ln()
        left = self._not()
        while self.check(TT.AND, TT.OR):
            op    = self.advance().value
            right = self._not()
            if isinstance(left, N.BoolOp) and left.op == op:
                left.values.append(right)
            else:
                left = N.BoolOp(op=op, values=[left, right], line=line)
        return left

    def _not(self):
        line = self.ln()
        if self.check(TT.NOT):
            self.advance()
            return N.UnaryOp(op="not", operand=self._not(), line=line)
        return self._compare()

    def _compare(self):
        line = self.ln()
        left = self._add()
        ops, comps = [], []
        CMP = {TT.EQ:"==", TT.NEQ:"!=", TT.LT:"<",
               TT.GT:">",  TT.LTE:"<=", TT.GTE:">="}
        while self.check(*CMP.keys()):
            ops.append(CMP[self.advance().type])
            comps.append(self._add())
        if ops:
            return N.Compare(left=left, ops=ops, comparators=comps, line=line)
        if self.check(TT.IN):
            self.advance()
            return N.Compare(left=left, ops=["in"],
                             comparators=[self._add()], line=line)
        if self.check(TT.IS):
            self.advance()
            op = "is not" if self.check(TT.NOT) and self.advance() else "is"
            return N.Compare(left=left, ops=[op],
                             comparators=[self._add()], line=line)
        if self.check(TT.NOT):
            saved = self.pos; self.advance()
            if self.check(TT.IN):
                self.advance()
                return N.Compare(left=left, ops=["not in"],
                                 comparators=[self._add()], line=line)
            self.pos = saved
        return left

    def _add(self):
        line = self.ln(); left = self._mul()
        while self.check(TT.PLUS, TT.MINUS):
            op = self.advance().value; right = self._mul()
            left = N.BinOp(op=op, left=left, right=right, line=line)
        return left

    def _mul(self):
        line = self.ln(); left = self._unary()
        while self.check(TT.STAR, TT.SLASH, TT.DSLASH, TT.MOD):
            op = self.advance().value; right = self._unary()
            left = N.BinOp(op=op, left=left, right=right, line=line)
        return left

    def _unary(self):
        line = self.ln()
        if self.check(TT.MINUS):
            self.advance()
            return N.UnaryOp(op="-", operand=self._power(), line=line)
        if self.check(TT.PLUS):
            self.advance(); return self._power()
        return self._power()

    def _power(self):
        line = self.ln(); base = self._postfix()
        if self.check(TT.POW):
            self.advance()
            return N.BinOp(op="**", left=base, right=self._unary(), line=line)
        return base

    def _postfix(self):
        """Handles call(), indexing[], and attribute.access chains."""
        line = self.ln(); expr = self._primary()
        while True:
            if self.check(TT.LPAREN):
                self.advance()
                args, kwargs = [], []
                while not self.check(TT.RPAREN, TT.EOF):
                    if self.check(TT.IDENT) and self.peek(1).type == TT.ASSIGN:
                        kw = self.advance().value; self.advance()
                        kwargs.append((kw, self.parse_expr()))
                    else:
                        args.append(self.parse_expr())
                    self.match(TT.COMMA)
                self.consume(TT.RPAREN, "Expected ')'")
                expr = N.Call(func=expr, args=args, kwargs=kwargs, line=line)
            elif self.check(TT.LBRACK):
                self.advance(); idx = self.parse_expr()
                if self.match(TT.COLON):
                    upper = step = None
                    if not self.check(TT.RBRACK, TT.COLON):
                        upper = self.parse_expr()
                    if self.match(TT.COLON):
                        if not self.check(TT.RBRACK):
                            step = self.parse_expr()
                    self.consume(TT.RBRACK, "Expected ']'")
                    expr = N.Slice(obj=expr, lower=idx, upper=upper,
                                   step=step, line=line)
                else:
                    self.consume(TT.RBRACK, "Expected ']'")
                    expr = N.Index(obj=expr, index=idx, line=line)
            elif self.check(TT.DOT):
                self.advance()
                attr = self.consume(TT.IDENT, "Expected attribute name").value
                expr = N.Attr(obj=expr, attr=attr, line=line)
            else:
                break
        return expr

    def _primary(self):
        line = self.ln(); t = self.peek()

        if t.type == TT.INT:    self.advance(); return N.IntLit(value=int(t.value), line=line)
        if t.type == TT.FLOAT:  self.advance(); return N.FloatLit(value=float(t.value), line=line)
        if t.type == TT.STRING: self.advance(); return N.StrLit(value=t.value, line=line)
        if t.type == TT.BOOL:   self.advance(); return N.BoolLit(value=(t.value=="True"), line=line)
        if t.type == TT.NONE:   self.advance(); return N.NoneLit(line=line)
        if t.type == TT.IDENT:  self.advance(); return N.Name(name=t.value, line=line)

        if t.type == TT.LPAREN:
            self.advance()
            if self.check(TT.RPAREN):
                self.advance(); return N.TupleLit(elements=[], line=line)
            expr = self.parse_expr()
            if self.match(TT.COMMA):
                elems = [expr]
                while not self.check(TT.RPAREN, TT.EOF):
                    elems.append(self.parse_expr())
                    if not self.match(TT.COMMA): break
                self.consume(TT.RPAREN, "Expected ')'")
                return N.TupleLit(elements=elems, line=line)
            self.consume(TT.RPAREN, "Expected ')'")
            return expr

        if t.type == TT.LBRACK:
            self.advance(); elems = []
            if not self.check(TT.RBRACK):
                # elem_expr is parsed at bool-op level to avoid ternary eating 'if'
                first = self._bool_op()
                if self.check(TT.FR):
                    # List comprehension:  [x fr items if cond]
                    self.advance()
                    var = first.name if isinstance(first, N.Name) else "_item"
                    if self.check(TT.IN): self.advance()
                    iterable = self._postfix()   # stop before IF
                    cond = None
                    if self.check(TT.IF):
                        self.advance(); cond = self._compare()
                    self.consume(TT.RBRACK, "Expected ']'")
                    return N.ListComp(expr=first, var=var,
                                      iterable=iterable, condition=cond, line=line)
                elems.append(first)
                while self.match(TT.COMMA):
                    if self.check(TT.RBRACK): break
                    elems.append(self.parse_expr())
            self.consume(TT.RBRACK, "Expected ']'")
            return N.ListLit(elements=elems, line=line)

        if t.type == TT.LBRACE:
            self.advance()
            if self.check(TT.RBRACE):
                self.advance(); return N.DictLit(pairs=[], line=line)
            first = self.parse_expr()
            if self.match(TT.COLON):
                val = self.parse_expr(); pairs = [(first, val)]
                while self.match(TT.COMMA):
                    if self.check(TT.RBRACE): break
                    k = self.parse_expr()
                    self.consume(TT.COLON, "Expected ':'")
                    pairs.append((k, self.parse_expr()))
                self.consume(TT.RBRACE, "Expected '}'")
                return N.DictLit(pairs=pairs, line=line)
            elems = [first]
            while self.match(TT.COMMA):
                if self.check(TT.RBRACE): break
                elems.append(self.parse_expr())
            self.consume(TT.RBRACE, "Expected '}'")
            return N.SetLit(elements=elems, line=line)

        raise ParseError(
            f"Unexpected token {t.type.name} ({t.value!r})",
            t.line, t.col)
