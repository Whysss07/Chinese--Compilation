from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class DSLError(Exception): ...


class DSLSyntaxError(DSLError): ...


class DSLRuntimeError(DSLError): ...


@dataclass
class Token:
    type: str
    value: Any
    line: int
    col: int


class Stmt: ...


class Expr: ...


@dataclass
class Program:
    statements: list[Stmt]


@dataclass
class Block:
    statements: list[Stmt]


@dataclass
class Assign(Stmt):
    target: Expr
    value: Expr


@dataclass
class ExprStmt(Stmt):
    expr: Expr


@dataclass
class IfBranch:
    cond: Expr
    block: Block


@dataclass
class IfStmt(Stmt):
    cond: Expr
    then_block: Block
    elifs: list[IfBranch] = field(default_factory=list)
    else_block: Block | None = None


@dataclass
class WhileStmt(Stmt):
    cond: Expr
    block: Block


@dataclass
class RepeatStmt(Stmt):
    times: Expr
    block: Block


@dataclass
class ForStmt(Stmt):
    name: str
    iterable: Expr
    block: Block


@dataclass
class FuncDef(Stmt):
    name: str
    params: list[str]
    block: Block


@dataclass
class ReturnStmt(Stmt):
    value: Expr | None


class ContinueStmt(Stmt): ...


class BreakStmt(Stmt): ...


@dataclass
class Name(Expr):
    value: str


@dataclass
class Literal(Expr):
    value: Any


@dataclass
class ListExpr(Expr):
    items: list[Expr]


@dataclass
class DictExpr(Expr):
    items: list[tuple[Expr, Expr]]


@dataclass
class Unary(Expr):
    op: str
    right: Expr


@dataclass
class Binary(Expr):
    left: Expr
    op: str
    right: Expr


@dataclass
class Arg:
    value: Expr
    name: str | None = None


@dataclass
class Call(Expr):
    callee: Expr
    args: list[Arg]


@dataclass
class Index(Expr):
    target: Expr
    key: Expr


@dataclass
class CompileResult:
    program: Program
    python_code: str


WORDS = {
    "如果": "IF", "否则如果": "ELIF", "否则": "ELSE", "当": "WHILE", "重复": "REPEAT", "对于": "FOR", "在": "IN",
    "定义": "DEF", "返回": "RETURN", "继续": "CONTINUE", "跳出": "BREAK", "令": "LET",
    "真": "TRUE", "假": "FALSE", "空": "NONE", "且": "AND", "并且": "AND", "或": "OR", "或者": "OR", "非": "NOT",
    "大于等于": "GE", "小于等于": "LE", "不等于": "NE", "大于": "GT", "小于": "LT", "等于": "EQ",
}


class Lexer:
    def __init__(self, src: str) -> None:
        self.src = self._norm(src)
        self.i = 0
        self.line = 1
        self.col = 1

    def tokenize(self) -> list[Token]:
        out: list[Token] = []
        single = {"{": "LBRACE", "}": "RBRACE", "(": "LPAREN", ")": "RPAREN", "[": "LBRACKET", "]": "RBRACKET",
                  ",": "COMMA", ":": "COLON", "+": "PLUS", "-": "MINUS", "*": "STAR", "/": "SLASH", "%": "PERCENT",
                  "=": "ASSIGN", "<": "LT", ">": "GT"}
        while not self._end():
            ch = self._peek()
            if ch in " \t\r":
                self._adv()
            elif ch == "\n":
                out.append(Token("NEWLINE", "\n", self.line, self.col))
                self._adv()
            elif ch == "#" or (ch == "/" and self._peek2() == "/"):
                while not self._end() and self._peek() != "\n":
                    self._adv()
            elif ch in "'\"":
                out.append(self._string())
            elif ch.isdigit():
                out.append(self._number())
            elif self._id_start(ch):
                out.append(self._word())
            else:
                line, col = self.line, self.col
                two = ch + self._peek2()
                if two in {"==": "EQ", "!=": "NE", "<=": "LE", ">=": "GE"}:
                    out.append(Token({"==": "EQ", "!=": "NE", "<=": "LE", ">=": "GE"}[two], two, line, col))
                    self._adv(); self._adv()
                elif ch in single:
                    out.append(Token(single[ch], ch, line, col))
                    self._adv()
                else:
                    raise DSLSyntaxError(f"无法识别字符 {ch}（第 {line} 行，第 {col} 列）")
        out.append(Token("EOF", None, self.line, self.col))
        return out

    def _norm(self, s: str) -> str:
        m = {"（": "(", "）": ")", "｛": "{", "｝": "}", "【": "[", "】": "]", "，": ",", "；": "\n", ";": "\n", "：": ":"}
        out, q, esc = [], None, False
        for ch in s:
            if q:
                out.append(ch)
                if esc: esc = False
                elif ch == "\\": esc = True
                elif ch == q: q = None
            else:
                if ch in "'\"": q = ch; out.append(ch)
                else: out.append(m.get(ch, ch))
        return "".join(out)

    def _string(self) -> Token:
        q, line, col = self._peek(), self.line, self.col
        self._adv(); out, esc = [], False
        while not self._end():
            ch = self._peek()
            if esc:
                out.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}.get(ch, ch)); esc = False; self._adv()
            elif ch == "\\":
                esc = True; self._adv()
            elif ch == q:
                self._adv(); return Token("STRING", "".join(out), line, col)
            else:
                out.append(ch); self._adv()
        raise DSLSyntaxError(f"字符串未结束（第 {line} 行，第 {col} 列）")

    def _number(self) -> Token:
        line, col, out, dot = self.line, self.col, [], False
        while not self._end():
            ch = self._peek()
            if ch.isdigit(): out.append(ch); self._adv()
            elif ch == "." and not dot and self._peek2().isdigit(): dot = True; out.append(ch); self._adv()
            else: break
        txt = "".join(out)
        return Token("NUMBER", float(txt) if dot else int(txt), line, col)

    def _word(self) -> Token:
        line, col, out = self.line, self.col, []
        while not self._end() and self._id_part(self._peek()):
            out.append(self._peek()); self._adv()
        txt = "".join(out)
        token_type = WORDS.get(txt, "IDENT")
        op_value = {
            "AND": "and",
            "OR": "or",
            "NOT": "not",
            "EQ": "==",
            "NE": "!=",
            "LT": "<",
            "LE": "<=",
            "GT": ">",
            "GE": ">=",
        }.get(token_type, txt)
        return Token(token_type, op_value, line, col)

    def _id_start(self, ch: str) -> bool:
        return ch == "_" or ch.isalpha() or "\u4e00" <= ch <= "\u9fff"

    def _id_part(self, ch: str) -> bool:
        return self._id_start(ch) or ch.isdigit()

    def _peek(self) -> str:
        return "\0" if self._end() else self.src[self.i]

    def _peek2(self) -> str:
        return "\0" if self.i + 1 >= len(self.src) else self.src[self.i + 1]

    def _adv(self) -> None:
        ch = self.src[self.i]; self.i += 1
        if ch == "\n": self.line += 1; self.col = 1
        else: self.col += 1

    def _end(self) -> bool:
        return self.i >= len(self.src)


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.t = tokens
        self.i = 0

    def parse(self) -> Program:
        stmts = []
        self._nl()
        while not self._is("EOF"):
            stmts.append(self.stmt())
            self._nl()
        return Program(stmts)

    def stmt(self) -> Stmt:
        if self._match("IF"): return self.if_stmt()
        if self._match("WHILE"): return self.while_stmt()
        if self._match("REPEAT"): return self.repeat_stmt()
        if self._match("FOR"): return self.for_stmt()
        if self._match("DEF"): return self.func_stmt()
        if self._match("RETURN"): return self.ret_stmt()
        if self._match("CONTINUE"): return ContinueStmt()
        if self._match("BREAK"): return BreakStmt()
        if self._match("LET"):
            if not self._is("IDENT"):
                tok = self._peek()
                raise DSLSyntaxError(f"令 后必须跟变量赋值（第 {tok.line} 行，第 {tok.col} 列）")
            name = Name(self._adv().value)
            self._expect("ASSIGN", "赋值缺少 =")
            return Assign(name, self.expr())

        target = self._assign_target()
        if target is not None:
            self._expect("ASSIGN", "赋值缺少 =")
            return Assign(target, self.expr())
        return ExprStmt(self.expr())

    def _assign_target(self) -> Expr | None:
        start = self.i
        if not self._is("IDENT"):
            return None

        expr: Expr = Name(self._adv().value)
        while self._match("LBRACKET"):
            key = self.expr()
            self._expect("RBRACKET", "索引缺少 ]")
            expr = Index(expr, key)

        if self._is("ASSIGN"):
            return expr

        self.i = start
        return None

    def if_stmt(self) -> IfStmt:
        cond = self._paren_expr("如果")
        then = self.block()
        self._nl()
        elifs = []
        while self._match("ELIF"):
            elifs.append(IfBranch(self._paren_expr("否则如果"), self.block()))
            self._nl()
        else_block = self.block() if self._match("ELSE") else None
        return IfStmt(cond, then, elifs, else_block)

    def while_stmt(self) -> WhileStmt:
        return WhileStmt(self._paren_expr("当"), self.block())

    def repeat_stmt(self) -> RepeatStmt:
        self._expect("LPAREN", "重复 后缺少 ("); times = self.expr(); self._expect("RPAREN", "重复 缺少 )")
        return RepeatStmt(times, self.block())

    def for_stmt(self) -> ForStmt:
        self._expect("LPAREN", "对于 后缺少 (")
        name = self._expect("IDENT", "对于 缺少变量").value
        self._expect("IN", "对于 需要 在")
        iterable = self.expr()
        self._expect("RPAREN", "对于 缺少 )")
        return ForStmt(name, iterable, self.block())

    def func_stmt(self) -> FuncDef:
        name = self._expect("IDENT", "定义 缺少函数名").value
        self._expect("LPAREN", "函数定义缺少 (")
        params = []
        if not self._is("RPAREN"):
            while True:
                params.append(self._expect("IDENT", "函数参数不合法").value)
                if not self._match("COMMA"): break
        self._expect("RPAREN", "函数定义缺少 )")
        return FuncDef(name, params, self.block())

    def ret_stmt(self) -> ReturnStmt:
        if self._is("NEWLINE", "RBRACE", "EOF"): return ReturnStmt(None)
        if self._match("LPAREN"):
            value = self.expr(); self._expect("RPAREN", "返回 缺少 )"); return ReturnStmt(value)
        return ReturnStmt(self.expr())

    def block(self) -> Block:
        self._nl(); self._expect("LBRACE", "代码块缺少 {"); self._nl()
        out = []
        while not self._is("RBRACE"):
            if self._is("EOF"):
                tok = self._peek()
                raise DSLSyntaxError(f"代码块未闭合（第 {tok.line} 行，第 {tok.col} 列）")
            out.append(self.stmt()); self._nl()
        self._expect("RBRACE", "代码块缺少 }")
        return Block(out)

    def _paren_expr(self, name: str) -> Expr:
        self._expect("LPAREN", f"{name} 后缺少 ("); e = self.expr(); self._expect("RPAREN", f"{name} 缺少 )"); return e

    def expr(self) -> Expr: return self._or()
    def _or(self) -> Expr:
        x = self._and()
        while self._match("OR"): x = Binary(x, "or", self._and())
        return x
    def _and(self) -> Expr:
        x = self._eq()
        while self._match("AND"): x = Binary(x, "and", self._eq())
        return x
    def _eq(self) -> Expr:
        x = self._cmp()
        while self._match("EQ", "NE"): x = Binary(x, self._prev().value, self._cmp())
        return x
    def _cmp(self) -> Expr:
        x = self._term()
        while self._match("LT", "LE", "GT", "GE"): x = Binary(x, self._prev().value, self._term())
        return x
    def _term(self) -> Expr:
        x = self._factor()
        while self._match("PLUS", "MINUS"): x = Binary(x, self._prev().value, self._factor())
        return x
    def _factor(self) -> Expr:
        x = self._unary()
        while self._match("STAR", "SLASH", "PERCENT"): x = Binary(x, self._prev().value, self._unary())
        return x
    def _unary(self) -> Expr:
        if self._match("NOT"): return Unary("not", self._unary())
        if self._match("MINUS"): return Unary("-", self._unary())
        if self._match("PLUS"): return Unary("+", self._unary())
        return self._postfix()

    def _postfix(self) -> Expr:
        x = self._primary()
        while True:
            if self._match("LPAREN"): x = self._call(x)
            elif self._match("LBRACKET"):
                key = self.expr(); self._expect("RBRACKET", "索引缺少 ]"); x = Index(x, key)
            else: break
        return x

    def _call(self, callee: Expr) -> Expr:
        args = []
        if not self._is("RPAREN"):
            while True:
                if self._is("IDENT") and self._next("ASSIGN"):
                    name = self._adv().value; self._expect("ASSIGN", "命名参数缺少 ="); args.append(Arg(self.expr(), name))
                else:
                    args.append(Arg(self.expr()))
                if not self._match("COMMA"): break
        self._expect("RPAREN", "调用缺少 )")
        return Call(callee, args)

    def _primary(self) -> Expr:
        if self._match("NUMBER", "STRING"): return Literal(self._prev().value)
        if self._match("TRUE"): return Literal(True)
        if self._match("FALSE"): return Literal(False)
        if self._match("NONE"): return Literal(None)
        if self._match("IDENT"): return Name(self._prev().value)
        if self._match("LPAREN"):
            x = self.expr(); self._expect("RPAREN", "表达式缺少 )"); return x
        if self._match("LBRACKET"):
            items = []
            if not self._is("RBRACKET"):
                while True:
                    items.append(self.expr())
                    if not self._match("COMMA"): break
            self._expect("RBRACKET", "列表缺少 ]")
            return ListExpr(items)
        if self._match("LBRACE"):
            items = []
            if not self._is("RBRACE"):
                while True:
                    k = self.expr(); self._expect("COLON", "字典缺少 :"); v = self.expr(); items.append((k, v))
                    if not self._match("COMMA"): break
            self._expect("RBRACE", "字典缺少 }")
            return DictExpr(items)
        tok = self._peek()
        raise DSLSyntaxError(f"无法解析表达式（第 {tok.line} 行，第 {tok.col} 列）")

    def _nl(self) -> None:
        while self._match("NEWLINE"): pass
    def _match(self, *types: str) -> bool:
        for t in types:
            if self._is(t): self._adv(); return True
        return False
    def _expect(self, t: str, msg: str) -> Token:
        if self._is(t): return self._adv()
        tok = self._peek(); raise DSLSyntaxError(f"{msg}（第 {tok.line} 行，第 {tok.col} 列）")
    def _is(self, *types: str) -> bool:
        return self._peek().type in types
    def _next(self, t: str) -> bool:
        return self.i + 1 < len(self.t) and self.t[self.i + 1].type == t
    def _adv(self) -> Token:
        tok = self.t[self.i]; self.i += 1; return tok
    def _peek(self) -> Token:
        return self.t[self.i]
    def _prev(self) -> Token:
        return self.t[self.i - 1]


class Env:
    def __init__(self, parent: "Env | None" = None) -> None:
        self.v: dict[str, Any] = {}
        self.parent = parent
    def get(self, name: str) -> Any:
        if name in self.v: return self.v[name]
        if self.parent: return self.parent.get(name)
        raise DSLRuntimeError(f"未定义变量：{name}")
    def set(self, name: str, value: Any) -> None:
        self.v[name] = value
    def define(self, name: str, value: Any) -> None:
        self.v[name] = value


class Ret(Exception):
    def __init__(self, value: Any) -> None: self.value = value


class Ctn(Exception): ...


class Brk(Exception): ...


class UserFunc:
    def __init__(self, stmt: FuncDef, closure: Env) -> None:
        self.stmt, self.closure = stmt, closure
    def call(self, it: "Interpreter", args: list[Any], kwargs: dict[str, Any]) -> Any:
        if kwargs: raise DSLRuntimeError("自定义函数暂不支持命名参数")
        if len(args) != len(self.stmt.params):
            raise DSLRuntimeError(f"函数 {self.stmt.name} 参数数量不匹配")
        env = Env(self.closure)
        for n, v in zip(self.stmt.params, args): env.define(n, v)
        try: it.block(self.stmt.block, env)
        except Ret as r: return r.value
        return None


class Interpreter:
    def __init__(self) -> None:
        self.globals = Env()
        for k, v in {
            "输出": lambda *a: print(*a), "输入": lambda prompt="": input(prompt), "长度": len, "整数": int, "小数": float,
            "文本": str, "布尔": bool, "列表": lambda *a: list(a), "数组": lambda *a: list(a), "字典": lambda **kw: dict(kw),
            "范围": range, "枚举": enumerate, "求和": sum, "最大值": max, "最小值": min, "绝对值": abs,
            "追加": lambda arr, value: arr.append(value), "弹出": lambda arr, index=-1: arr.pop(index)
        }.items():
            self.globals.define(k, v)

    def interpret(self, p: Program) -> None:
        for s in p.statements: self.exec(s, self.globals)

    def block(self, b: Block, env: Env) -> None:
        for s in b.statements: self.exec(s, env)

    def exec(self, s: Stmt, env: Env) -> None:
        if isinstance(s, Assign): self.assign_target(s.target, self.eval(s.value, env), env)
        elif isinstance(s, ExprStmt): self.eval(s.expr, env)
        elif isinstance(s, IfStmt):
            if self.truth(self.eval(s.cond, env)): self.block(s.then_block, env)
            else:
                done = False
                for br in s.elifs:
                    if self.truth(self.eval(br.cond, env)): self.block(br.block, env); done = True; break
                if not done and s.else_block: self.block(s.else_block, env)
        elif isinstance(s, WhileStmt):
            while self.truth(self.eval(s.cond, env)):
                try: self.block(s.block, env)
                except Ctn: continue
                except Brk: break
        elif isinstance(s, RepeatStmt):
            n = self.eval(s.times, env)
            if not isinstance(n, int): raise DSLRuntimeError("重复(...) 必须是整数")
            for _ in range(n):
                try: self.block(s.block, env)
                except Ctn: continue
                except Brk: break
        elif isinstance(s, ForStmt):
            try: items = iter(self.eval(s.iterable, env))
            except TypeError as e: raise DSLRuntimeError("对于(...) 目标不可迭代") from e
            for item in items:
                env.set(s.name, item)
                try: self.block(s.block, env)
                except Ctn: continue
                except Brk: break
        elif isinstance(s, FuncDef): env.define(s.name, UserFunc(s, env))
        elif isinstance(s, ReturnStmt): raise Ret(self.eval(s.value, env) if s.value is not None else None)
        elif isinstance(s, ContinueStmt): raise Ctn()
        elif isinstance(s, BreakStmt): raise Brk()
        else: raise DSLRuntimeError("未知语句")

    def assign_target(self, target: Expr, value: Any, env: Env) -> None:
        if isinstance(target, Name):
            env.set(target.value, value)
            return
        if isinstance(target, Index):
            container = self.eval(target.target, env)
            key = self.eval(target.key, env)
            try:
                container[key] = value
            except Exception as e:
                raise DSLRuntimeError("数组/字典下标赋值失败") from e
            return
        raise DSLRuntimeError("不支持的赋值目标")

    def eval(self, e: Expr, env: Env) -> Any:
        if isinstance(e, Literal): return e.value
        if isinstance(e, Name): return env.get(e.value)
        if isinstance(e, ListExpr): return [self.eval(x, env) for x in e.items]
        if isinstance(e, DictExpr): return {self.eval(k, env): self.eval(v, env) for k, v in e.items}
        if isinstance(e, Unary):
            r = self.eval(e.right, env)
            return {"not": lambda x: not self.truth(x), "-": lambda x: -x, "+": lambda x: +x}[e.op](r)
        if isinstance(e, Binary):
            if e.op == "and":
                l = self.eval(e.left, env); return self.eval(e.right, env) if self.truth(l) else l
            if e.op == "or":
                l = self.eval(e.left, env); return l if self.truth(l) else self.eval(e.right, env)
            l, r = self.eval(e.left, env), self.eval(e.right, env)
            if e.op == "+": return l + r
            if e.op == "-": return l - r
            if e.op == "*": return l * r
            if e.op == "/": return l / r
            if e.op == "%": return l % r
            if e.op == "==": return l == r
            if e.op == "!=": return l != r
            if e.op == "<": return l < r
            if e.op == "<=": return l <= r
            if e.op == ">": return l > r
            if e.op == ">=": return l >= r
            raise DSLRuntimeError(f"未知运算符：{e.op}")
        if isinstance(e, Call):
            f = self.eval(e.callee, env); args, kwargs = [], {}
            for a in e.args:
                if a.name is None: args.append(self.eval(a.value, env))
                else: kwargs[a.name] = self.eval(a.value, env)
            if isinstance(f, UserFunc): return f.call(self, args, kwargs)
            if callable(f): return f(*args, **kwargs)
            raise DSLRuntimeError("被调用对象不是函数")
        if isinstance(e, Index): return self.eval(e.target, env)[self.eval(e.key, env)]
        raise DSLRuntimeError("未知表达式")

    def truth(self, x: Any) -> bool:
        return bool(x)


class PythonTranspiler:
    def __init__(self) -> None: self.n = 0
    def transpile(self, p: Program) -> str:
        lines: list[str] = []
        for s in p.statements: self.s(s, lines, 0)
        return "\n".join(lines) + "\n"
    def s(self, s: Stmt, out: list[str], d: int) -> None:
        p = "    " * d
        if isinstance(s, Assign): out.append(f"{p}{self.e(s.target)} = {self.e(s.value)}")
        elif isinstance(s, ExprStmt): out.append(f"{p}{self.e(s.expr)}")
        elif isinstance(s, IfStmt):
            out.append(f"{p}if {self.e(s.cond)}:"); self.b(s.then_block, out, d + 1)
            for br in s.elifs: out.append(f"{p}elif {self.e(br.cond)}:"); self.b(br.block, out, d + 1)
            if s.else_block: out.append(f"{p}else:"); self.b(s.else_block, out, d + 1)
        elif isinstance(s, WhileStmt): out.append(f"{p}while {self.e(s.cond)}:"); self.b(s.block, out, d + 1)
        elif isinstance(s, RepeatStmt):
            self.n += 1; out.append(f"{p}for _repeat_{self.n} in range({self.e(s.times)}):"); self.b(s.block, out, d + 1)
        elif isinstance(s, ForStmt): out.append(f"{p}for {s.name} in {self.e(s.iterable)}:"); self.b(s.block, out, d + 1)
        elif isinstance(s, FuncDef): out.append(f"{p}def {s.name}({', '.join(s.params)}):"); self.b(s.block, out, d + 1)
        elif isinstance(s, ReturnStmt): out.append(f"{p}return" + ("" if s.value is None else f" {self.e(s.value)}"))
        elif isinstance(s, ContinueStmt): out.append(f"{p}continue")
        elif isinstance(s, BreakStmt): out.append(f"{p}break")
    def b(self, b: Block, out: list[str], d: int) -> None:
        if not b.statements: out.append("    " * d + "pass")
        for s in b.statements: self.s(s, out, d)
    def e(self, e: Expr) -> str:
        if isinstance(e, Literal): return repr(e.value)
        if isinstance(e, Name): return e.value
        if isinstance(e, ListExpr): return "[" + ", ".join(self.e(x) for x in e.items) + "]"
        if isinstance(e, DictExpr): return "{" + ", ".join(f"{self.e(k)}: {self.e(v)}" for k, v in e.items) + "}"
        if isinstance(e, Unary): return f"({e.op} {self.e(e.right)})" if e.op == "not" else f"({e.op}{self.e(e.right)})"
        if isinstance(e, Binary): return f"({self.e(e.left)} {e.op} {self.e(e.right)})"
        if isinstance(e, Call):
            args = [self.e(a.value) if a.name is None else f"{a.name}={self.e(a.value)}" for a in e.args]
            return f"{self.e(e.callee)}(" + ", ".join(args) + ")"
        if isinstance(e, Index): return f"{self.e(e.target)}[{self.e(e.key)}]"
        raise DSLError("未知表达式")


class ChineseDSL:
    def compile(self, source: str) -> CompileResult:
        program = Parser(Lexer(source).tokenize()).parse()
        return CompileResult(program, PythonTranspiler().transpile(program))
    def run(self, source: str) -> CompileResult:
        result = self.compile(source); Interpreter().interpret(result.program); return result


def main() -> None:
    ap = argparse.ArgumentParser(description="运行中文 DSL（词法分析 + 语法分析 + AST + 解释执行）")
    ap.add_argument("file", type=Path, help="DSL 文件路径")
    ap.add_argument("--show-python", action="store_true", help="显示转换后的 Python")
    ap.add_argument("--show-ast", action="store_true", help="显示 AST")
    args = ap.parse_args()
    src = args.file.read_text(encoding="utf-8")
    dsl = ChineseDSL()
    result = dsl.compile(src)
    if args.show_ast: print(result.program)
    if args.show_python:
        print("=== 转换后的 Python ===")
        print(result.python_code)
    Interpreter().interpret(result.program)


if __name__ == "__main__":
    main()
