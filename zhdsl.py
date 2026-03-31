from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


class DSL语法错误(Exception):
    """中文 DSL 的语法错误。"""


@dataclass
class 编译结果:
    python_code: str


class 中文DSL编译器:
    def __init__(self) -> None:
        self._loop_counter = 0

    def 编译(self, source: str) -> 编译结果:
        tokens = self._分词(source)
        python_lines: list[str] = []
        indent = 0
        waiting_block = False

        for token in tokens:
            if token == "{":
                if not waiting_block:
                    raise DSL语法错误("出现了多余的 {")
                indent += 1
                waiting_block = False
                continue

            if token == "}":
                if waiting_block:
                    raise DSL语法错误("{ 后面缺少代码块内容")
                indent -= 1
                if indent < 0:
                    raise DSL语法错误("出现了多余的 }")
                continue

            translated, is_block_header = self._翻译语句(token)
            python_lines.append("    " * indent + translated)
            waiting_block = is_block_header

        if waiting_block:
            raise DSL语法错误("代码块头后缺少 {")
        if indent != 0:
            raise DSL语法错误("代码块没有正确闭合")

        return 编译结果(python_code="\n".join(python_lines) + "\n")

    def 执行(self, source: str) -> 编译结果:
        compiled = self.编译(source)
        env = {
            "__builtins__": {
                "print": print,
                "range": range,
                "len": len,
                "int": int,
                "float": float,
                "str": str,
                "bool": bool,
            }
        }
        exec(compiled.python_code, env, env)
        return compiled

    def _分词(self, source: str) -> list[str]:
        normalized = self._规范化(source)
        tokens: list[str] = []
        buffer: list[str] = []
        in_string: str | None = None
        escaped = False

        def flush_buffer() -> None:
            if not buffer:
                return
            chunk = "".join(buffer)
            buffer.clear()
            for line in chunk.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("#") or stripped.startswith("//"):
                    continue
                tokens.append(stripped)

        for ch in normalized:
            if in_string is not None:
                buffer.append(ch)
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == in_string:
                    in_string = None
                continue

            if ch in ("'", '"'):
                in_string = ch
                buffer.append(ch)
                continue

            if ch in "{}":
                flush_buffer()
                tokens.append(ch)
                continue

            buffer.append(ch)

        flush_buffer()
        return tokens

    def _规范化(self, source: str) -> str:
        mapping = {
            "（": "(",
            "）": ")",
            "｛": "{",
            "｝": "}",
            "【": "[",
            "】": "]",
            "，": ",",
            "；": "\n",
            ";": "\n",
            "：": ":",
        }

        chars: list[str] = []
        in_string: str | None = None
        escaped = False

        for ch in source:
            if in_string is not None:
                chars.append(ch)
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == in_string:
                    in_string = None
                continue

            if ch in ("'", '"'):
                in_string = ch
                chars.append(ch)
                continue

            chars.append(mapping.get(ch, ch))

        return "".join(chars)

    def _翻译语句(self, statement: str) -> tuple[str, bool]:
        statement = statement.strip()

        if statement.startswith("如果(") and statement.endswith(")"):
            cond = self._提取括号内容(statement, "如果")
            return f"if {cond}:", True

        if statement.startswith("否则如果(") and statement.endswith(")"):
            cond = self._提取括号内容(statement, "否则如果")
            return f"elif {cond}:", True

        if statement == "否则":
            return "else:", True

        if statement.startswith("当(") and statement.endswith(")"):
            cond = self._提取括号内容(statement, "当")
            return f"while {cond}:", True

        if statement.startswith("重复(") and statement.endswith(")"):
            times = self._提取括号内容(statement, "重复")
            self._loop_counter += 1
            loop_var = f"_重复计数_{self._loop_counter}"
            return f"for {loop_var} in range({times}):", True

        if statement.startswith("输出(") and statement.endswith(")"):
            args = self._提取括号内容(statement, "输出")
            return f"print({args})", False

        if statement.startswith("令 "):
            return statement[2:].strip(), False

        return statement, False

    @staticmethod
    def _提取括号内容(statement: str, keyword: str) -> str:
        prefix = f"{keyword}("
        if not statement.startswith(prefix) or not statement.endswith(")"):
            raise DSL语法错误(f"{keyword} 语句格式错误：{statement}")
        return statement[len(prefix) : -1].strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="运行中文开发 DSL")
    parser.add_argument("file", type=Path, help="DSL 源文件路径，例如 示例.zh")
    parser.add_argument("--show-python", action="store_true", help="显示转换后的 Python 代码")
    args = parser.parse_args()

    source = args.file.read_text(encoding="utf-8")
    compiler = 中文DSL编译器()
    compiled = compiler.编译(source)

    if args.show_python:
        print("=== 转换后的 Python ===")
        print(compiled.python_code)

    compiler.执行(source)


if __name__ == "__main__":
    main()
