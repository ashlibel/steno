"""
STENO Interpreter
Tree-walking interpreter: directly executes the AST without transpiling to Python.
This satisfies requirement (b): parse + interpret → output.
"""

import math
import time
import sys
from typing import Any, Dict, List, Optional

import ast_nodes as N


# Sentinel values 

class _ReturnSignal(Exception):
    def __init__(self, value): self.value = value

class _BreakSignal(Exception):
    pass

class _ContinueSignal(Exception):
    pass

class _YieldSignal(Exception):
    def __init__(self, value): self.value = value



class RuntimeError_(Exception):
    def __init__(self, msg: str, line: int = 0):
        super().__init__(f"RuntimeError at line {line}: {msg}")
        self.line = line




class Env:
    """Lexical scope chain."""

    def __init__(self, parent: Optional["Env"] = None):
        self._store: Dict[str, Any] = {}
        self.parent = parent

    def get(self, name: str, line: int = 0) -> Any:
        if name in self._store:
            return self._store[name]
        if self.parent:
            return self.parent.get(name, line)
        raise RuntimeError_(f"Undefined name '{name}'", line)

    def set(self, name: str, value: Any):
        self._store[name] = value

    def assign(self, name: str, value: Any, line: int = 0):
        """Walk up scopes to find existing binding."""
        if name in self._store:
            self._store[name] = value
            return
        if self.parent:
            self.parent.assign(name, value, line)
            return
        # If not found anywhere, create in current scope
        self._store[name] = value

    def declare_global(self, name: str):
        """Mark a name to resolve in global scope."""
        self._globals.add(name) if hasattr(self, '_globals') else None

    def __repr__(self):
        return f"Env({list(self._store.keys())})"


#STENO function wrapper 

class StenoFunction:
    def __init__(self, node: N.FuncDef, closure: Env):
        self.node    = node
        self.closure = closure
        self.__name__ = node.name

    def __repr__(self):
        return f"<fn {self.node.name}>"

    def call(self, interp: "Interpreter", args: list, kwargs: dict) -> Any:
        env = Env(parent=self.closure)
        params = self.node.params

        # Positional args
        for i, p in enumerate(params):
            if i < len(args):
                env.set(p, args[i])
            elif p in self.node.defaults:
                env.set(p, interp.eval_expr(self.node.defaults[p], self.closure))
            else:
                raise RuntimeError_(
                    f"{self.node.name}() missing argument '{p}'",
                    self.node.line)

        # Keyword args
        for k, v in kwargs.items():
            env.set(k, v)

        try:
            interp.exec_block(self.node.body, env)
            return None
        except _ReturnSignal as r:
            return r.value


class StenoClass:
    def __init__(self, node: N.ClassDef, closure: Env):
        self.node    = node
        self.closure = closure
        self.__name__ = node.name

    def __repr__(self):
        return f"<class {self.node.name}>"

    def instantiate(self, interp: "Interpreter", args: list, kwargs: dict):
        instance = StenoInstance(self)
        # Build class env so methods can be stored
        class_env = Env(parent=self.closure)
        interp.exec_block(self.node.body, class_env)
        instance._methods = dict(class_env._store)
        # Call __init__ if present
        if "__init__" in instance._methods:
            init = instance._methods["__init__"]
            if isinstance(init, StenoFunction):
                init.call(interp, [instance] + list(args), kwargs)
        return instance


class StenoInstance:
    def __init__(self, klass: StenoClass):
        self._klass  = klass
        self._attrs: Dict[str, Any] = {}
        self._methods: Dict[str, Any] = {}

    def get_attr(self, name: str, line: int = 0) -> Any:
        if name in self._attrs:
            return self._attrs[name]
        if name in self._methods:
            m = self._methods[name]
            if isinstance(m, StenoFunction):
                return BoundMethod(m, self)
            return m
        raise RuntimeError_(
            f"'{self._klass.node.name}' has no attribute '{name}'", line)

    def set_attr(self, name: str, value: Any):
        self._attrs[name] = value

    def __repr__(self):
        return f"<{self._klass.node.name} instance>"


class BoundMethod:
    def __init__(self, func: StenoFunction, instance: StenoInstance):
        self.func     = func
        self.instance = instance

    def __repr__(self):
        return f"<bound method {self.func.node.name}>"

    def call(self, interp: "Interpreter", args: list, kwargs: dict) -> Any:
        return self.func.call(interp, [self.instance] + list(args), kwargs)


# Built-in globals 

def _make_builtins() -> Dict[str, Any]:
    import os, random, json

    def _range(*a):
        if len(a) == 1:   return list(range(a[0]))
        if len(a) == 2:   return list(range(a[0], a[1]))
        return list(range(a[0], a[1], a[2]))

    return {
        # I/O
        "print": print,
        "input": input,
        "open":  open,
        # Type constructors
        "int": int, "float": float, "str": str,
        "bool": bool, "list": list, "dict": dict,
        "set": set, "tuple": tuple, "bytes": bytes,
        # Introspection
        "type": type, "isinstance": isinstance,
        "issubclass": issubclass,
        "hasattr": hasattr, "getattr": getattr, "setattr": setattr,
        "callable": callable, "id": id, "dir": dir,
        # Sequences
        "len": len, "range": _range,
        "enumerate": lambda it: list(enumerate(it)),
        "zip": lambda *a: list(zip(*a)),
        "map": lambda f, it: list(map(f, it)),
        "filter": lambda f, it: list(filter(f, it)),
        "sorted": sorted, "reversed": lambda it: list(reversed(it)),
        "list": list, "tuple": tuple,
        # Math helpers
        "abs": abs, "round": round, "min": min, "max": max,
        "sum": sum, "pow": pow, "divmod": divmod,
        "math": math,
        # Misc
        "repr": repr, "hash": hash,
        "any": any, "all": all,
        "chr": chr, "ord": ord, "hex": hex, "oct": oct, "bin": bin,
        "format": format,
        # Modules
        "os": os, "random": random, "json": json,
        "sys": sys,
        # Exceptions (so user can raise / catch them)
        "Exception": Exception, "ValueError": ValueError,
        "TypeError": TypeError, "KeyError": KeyError,
        "IndexError": IndexError, "AttributeError": AttributeError,
        "RuntimeError": RuntimeError, "StopIteration": StopIteration,
        "ZeroDivisionError": ZeroDivisionError,
        "NotImplementedError": NotImplementedError,
        "True": True, "False": False, "None": None,
    }


# Interpreter 

class Interpreter:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.globals = Env()
        for k, v in _make_builtins().items():
            self.globals.set(k, v)
        self._output: List[str] = []   # captured output for tests

    #Public API 

    def run(self, tree: N.Program):
        self.exec_block(tree.body, self.globals)

    def run_source(self, source: str, filename: str = "<steno>"):
        from lexer  import Lexer
        from parser import Parser
        tokens = Lexer(source).tokenize()
        tree   = Parser(tokens).parse()
        self.run(tree)

    # Block / statement execution

    def exec_block(self, stmts: List[N.Node], env: Env):
        for stmt in stmts:
            self.exec_stmt(stmt, env)

    def exec_stmt(self, node: N.Node, env: Env):
        t = type(node).__name__
        handler = getattr(self, f"_s_{t}", None)
        if handler is None:
            raise RuntimeError_(f"No handler for statement '{t}'",
                                  getattr(node, "line", 0))
        handler(node, env)



    def _s_ExprStmt(self, node: N.ExprStmt, env: Env):
        self.eval_expr(node.expr, env)

    def _s_VarDecl(self, node: N.VarDecl, env: Env):
        val = self.eval_expr(node.value, env) if node.value else None
        env.set(node.name, val)

    def _s_Assign(self, node: N.Assign, env: Env):
        val = self.eval_expr(node.value, env)
        self._do_assign(node.target, node.op, val, env, node.line)

    def _do_assign(self, target: N.Node, op: str, val: Any, env: Env, line: int):
        if isinstance(target, N.Name):
            if op == "=":
                env.assign(target.name, val)
            else:
                cur = env.get(target.name, line)
                env.assign(target.name, self._augment(cur, op, val, line))
        elif isinstance(target, N.Attr):
            obj = self.eval_expr(target.obj, env)
            if isinstance(obj, StenoInstance):
                if op != "=":
                    cur = obj.get_attr(target.attr, line)
                    val = self._augment(cur, op, val, line)
                obj.set_attr(target.attr, val)
            else:
                setattr(obj, target.attr, val)
        elif isinstance(target, N.Index):
            obj = self.eval_expr(target.obj, env)
            idx = self.eval_expr(target.index, env)
            if op != "=":
                val = self._augment(obj[idx], op, val, line)
            obj[idx] = val
        else:
            raise RuntimeError_("Invalid assignment target", line)

    def _augment(self, cur: Any, op: str, val: Any, line: int) -> Any:
        if op == "+=": return cur + val
        if op == "-=": return cur - val
        if op == "*=": return cur * val
        if op == "/=": return cur / val
        raise RuntimeError_(f"Unknown augmented operator '{op}'", line)

    def _s_PrintStmt(self, node: N.PrintStmt, env: Env):
        parts = [self._to_str(self.eval_expr(a, env)) for a in node.args]
        line  = " ".join(parts)
        print(line)
        self._output.append(line)

    def _to_str(self, val: Any) -> str:
        if isinstance(val, bool):   return str(val)
        if isinstance(val, float) and val == int(val): return str(int(val))
        return str(val)

    def _s_ReturnStmt(self, node: N.ReturnStmt, env: Env):
        val = self.eval_expr(node.value, env) if node.value else None
        raise _ReturnSignal(val)

    def _s_YieldStmt(self, node: N.YieldStmt, env: Env):
        val = self.eval_expr(node.value, env) if node.value else None
        raise _YieldSignal(val)

    def _s_BreakStmt(self, node: N.BreakStmt, env: Env):
        raise _BreakSignal()

    def _s_ContinueStmt(self, node: N.ContinueStmt, env: Env):
        raise _ContinueSignal()

    def _s_PassStmt(self, node: N.PassStmt, env: Env):
        pass

    def _s_DelStmt(self, node: N.DelStmt, env: Env):
        if isinstance(node.target, N.Name):
            del env._store[node.target.name]
        elif isinstance(node.target, N.Index):
            obj = self.eval_expr(node.target.obj, env)
            idx = self.eval_expr(node.target.index, env)
            del obj[idx]

    def _s_GlobalStmt(self, node: N.GlobalStmt, env: Env):
        pass   # handled implicitly — assign walks up to globals

    def _s_NonlocalStmt(self, node: N.NonlocalStmt, env: Env):
        pass

    def _s_AssertStmt(self, node: N.AssertStmt, env: Env):
        val = self.eval_expr(node.test, env)
        if not val:
            msg = self.eval_expr(node.msg, env) if node.msg else "Assertion failed"
            raise AssertionError(msg)

    def _s_ImportStmt(self, node: N.ImportStmt, env: Env):
        import importlib
        mod = importlib.import_module(node.module)
        if node.names:
            for name in node.names:
                env.set(name, getattr(mod, name))
        elif node.alias:
            env.set(node.alias, mod)
        else:
            env.set(node.module.split(".")[-1], mod)

    def _s_FuncDef(self, node: N.FuncDef, env: Env):
        fn = StenoFunction(node, env)
        env.set(node.name, fn)

    def _s_ClassDef(self, node: N.ClassDef, env: Env):
        klass = StenoClass(node, env)
        env.set(node.name, klass)

    def _s_IfStmt(self, node: N.IfStmt, env: Env):
        if self.eval_expr(node.condition, env):
            self.exec_block(node.then_body, Env(parent=env))
            return
        for cond, body in node.elif_clauses:
            if self.eval_expr(cond, env):
                self.exec_block(body, Env(parent=env))
                return
        if node.else_body:
            self.exec_block(node.else_body, Env(parent=env))

    def _s_ForLoop(self, node: N.ForLoop, env: Env):
        start = self.eval_expr(node.start, env)
        stop  = self.eval_expr(node.stop,  env)
        step  = self.eval_expr(node.step,  env) if node.step else 1
        for i in range(start, stop, step):
            inner = Env(parent=env); inner.set(node.var, i)
            try:
                self.exec_block(node.body, inner)
            except _BreakSignal:
                break
            except _ContinueSignal:
                continue

    def _s_ForInLoop(self, node: N.ForInLoop, env: Env):
        iterable = self.eval_expr(node.iterable, env)
        for item in iterable:
            inner = Env(parent=env); inner.set(node.var, item)
            try:
                self.exec_block(node.body, inner)
            except _BreakSignal:
                break
            except _ContinueSignal:
                continue

    def _s_WhileLoop(self, node: N.WhileLoop, env: Env):
        while self.eval_expr(node.condition, env):
            inner = Env(parent=env)
            try:
                self.exec_block(node.body, inner)
            except _BreakSignal:
                break
            except _ContinueSignal:
                continue

    def _s_TryStmt(self, node: N.TryStmt, env: Env):
        try:
            self.exec_block(node.body, Env(parent=env))
        except (_ReturnSignal, _BreakSignal, _ContinueSignal):
            raise
        except Exception as e:
            handled = False
            for exc_type_node, exc_name, h_body in node.handlers:
                exc_type = (self.eval_expr(exc_type_node, env)
                            if exc_type_node else Exception)
                if isinstance(e, exc_type):
                    inner = Env(parent=env)
                    if exc_name:
                        inner.set(exc_name, e)
                    self.exec_block(h_body, inner)
                    handled = True
                    break
            if not handled:
                raise
        finally:
            if node.finally_body:
                self.exec_block(node.finally_body, Env(parent=env))

    def _s_WithStmt(self, node: N.WithStmt, env: Env):
        ctx   = self.eval_expr(node.context, env)
        inner = Env(parent=env)
        with ctx as val:
            if node.alias:
                inner.set(node.alias, val)
            self.exec_block(node.body, inner)


    # Expression evaluator
   

    def eval_expr(self, node: N.Node, env: Env) -> Any:
        if node is None: return None
        t = type(node).__name__
        handler = getattr(self, f"_e_{t}", None)
        if handler is None:
            raise RuntimeError_(f"No handler for expression '{t}'",
                                  getattr(node, "line", 0))
        return handler(node, env)

    def _e_IntLit(self,   n, e): return n.value
    def _e_FloatLit(self, n, e): return n.value
    def _e_StrLit(self,   n, e): return n.value
    def _e_BoolLit(self,  n, e): return n.value
    def _e_NoneLit(self,  n, e): return None

    def _e_Name(self, node: N.Name, env: Env) -> Any:
        return env.get(node.name, node.line)

    def _e_BinOp(self, node: N.BinOp, env: Env) -> Any:
        l = self.eval_expr(node.left,  env)
        r = self.eval_expr(node.right, env)
        op = node.op
        if op == "+":  return l + r
        if op == "-":  return l - r
        if op == "*":  return l * r
        if op == "/":  return l / r
        if op == "//": return l // r
        if op == "%":  return l % r
        if op == "**": return l ** r
        raise RuntimeError_(f"Unknown operator '{op}'", node.line)

    def _e_UnaryOp(self, node: N.UnaryOp, env: Env) -> Any:
        v = self.eval_expr(node.operand, env)
        if node.op == "-":   return -v
        if node.op == "+":   return +v
        if node.op == "not": return not v
        raise RuntimeError_(f"Unknown unary '{node.op}'", node.line)

    def _e_Compare(self, node: N.Compare, env: Env) -> bool:
        left = self.eval_expr(node.left, env)
        for op, comp_node in zip(node.ops, node.comparators):
            right = self.eval_expr(comp_node, env)
            if   op == "==":     res = left == right
            elif op == "!=":     res = left != right
            elif op == "<":      res = left <  right
            elif op == ">":      res = left >  right
            elif op == "<=":     res = left <= right
            elif op == ">=":     res = left >= right
            elif op == "in":     res = left in right
            elif op == "not in": res = left not in right
            elif op == "is":     res = left is right
            elif op == "is not": res = left is not right
            else:
                raise RuntimeError_(f"Unknown comparison '{op}'", node.line)
            if not res:
                return False
            left = right
        return True

    def _e_BoolOp(self, node: N.BoolOp, env: Env) -> Any:
        if node.op == "and":
            result = True
            for v in node.values:
                result = self.eval_expr(v, env)
                if not result: return result
            return result
        # or
        result = False
        for v in node.values:
            result = self.eval_expr(v, env)
            if result: return result
        return result

    def _e_Call(self, node: N.Call, env: Env) -> Any:
        func = self.eval_expr(node.func, env)
        args = [self.eval_expr(a, env) for a in node.args]
        kwargs = {k: self.eval_expr(v, env) for k, v in node.kwargs}

        if isinstance(func, StenoFunction):
            return func.call(self, args, kwargs)
        if isinstance(func, BoundMethod):
            return func.call(self, args, kwargs)
        if isinstance(func, StenoClass):
            return func.instantiate(self, args, kwargs)
        if callable(func):
            return func(*args, **kwargs)
        raise RuntimeError_(f"'{func}' is not callable", node.line)

    def _e_Index(self, node: N.Index, env: Env) -> Any:
        obj = self.eval_expr(node.obj,   env)
        idx = self.eval_expr(node.index, env)
        return obj[idx]

    def _e_Slice(self, node: N.Slice, env: Env) -> Any:
        obj = self.eval_expr(node.obj, env)
        lo  = self.eval_expr(node.lower, env) if node.lower else None
        hi  = self.eval_expr(node.upper, env) if node.upper else None
        st  = self.eval_expr(node.step,  env) if node.step  else None
        return obj[lo:hi:st]

    def _e_Attr(self, node: N.Attr, env: Env) -> Any:
        obj = self.eval_expr(node.obj, env)
        if isinstance(obj, StenoInstance):
            return obj.get_attr(node.attr, node.line)
        return getattr(obj, node.attr)

    def _e_ListLit(self, node: N.ListLit, env: Env) -> list:
        return [self.eval_expr(e, env) for e in node.elements]

    def _e_DictLit(self, node: N.DictLit, env: Env) -> dict:
        return {self.eval_expr(k, env): self.eval_expr(v, env)
                for k, v in node.pairs}

    def _e_SetLit(self, node: N.SetLit, env: Env) -> set:
        return {self.eval_expr(e, env) for e in node.elements}

    def _e_TupleLit(self, node: N.TupleLit, env: Env) -> tuple:
        return tuple(self.eval_expr(e, env) for e in node.elements)

    def _e_ListComp(self, node: N.ListComp, env: Env) -> list:
        iterable = self.eval_expr(node.iterable, env)
        result   = []
        for item in iterable:
            inner = Env(parent=env); inner.set(node.var, item)
            if node.condition:
                if not self.eval_expr(node.condition, inner):
                    continue
            result.append(self.eval_expr(node.expr, inner))
        return result

    def _e_DictComp(self, node: N.DictComp, env: Env) -> dict:
        iterable = self.eval_expr(node.iterable, env)
        result   = {}
        for item in iterable:
            inner = Env(parent=env); inner.set(node.var, item)
            if node.condition and not self.eval_expr(node.condition, inner):
                continue
            k = self.eval_expr(node.key_expr, inner)
            v = self.eval_expr(node.val_expr, inner)
            result[k] = v
        return result

    def _e_Lambda(self, node: N.Lambda, env: Env) -> StenoFunction:
        # Wrap lambda body in a synthetic FuncDef
        body_stmt = N.ReturnStmt(value=node.body, line=node.line)
        fn_node   = N.FuncDef(name="<lambda>", params=node.params,
                              body=[body_stmt], line=node.line)
        return StenoFunction(fn_node, env)

    def _e_Ternary(self, node: N.Ternary, env: Env) -> Any:
        if self.eval_expr(node.condition, env):
            return self.eval_expr(node.then_expr, env)
        return self.eval_expr(node.else_expr, env)
