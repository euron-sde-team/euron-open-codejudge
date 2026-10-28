"""Turn source code into normalised tokens, so renaming and reformatting change nothing.

Identifiers become ``ID``, numbers ``NUM``, string and character literals ``STR``;
keywords and operators stay as they are; comments, whitespace and preprocessor lines
(``#include`` boilerplate every C++ submission shares) are dropped. Each token keeps the
line it came from, so matches can be shown side by side.

Python uses the standard ``tokenize`` module; C++, Java and JavaScript share one small
lexer with a keyword set per language. Code that does not tokenize (a syntax error) falls
back to the generic lexer instead of being skipped.
"""

from __future__ import annotations

import io
import keyword
import re
import tokenize as pytokenize
from dataclasses import dataclass


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


C_KEYWORDS = _words(
    """
    if else for while do switch case default break continue return goto try catch throw
    class struct union enum namespace using template typename public private protected
    virtual override const static inline new delete this sizeof typedef auto void bool
    char short int long float double signed unsigned true false nullptr operator friend
    constexpr mutable volatile extern register explicit
    """
)
JAVA_KEYWORDS = _words(
    """
    if else for while do switch case default break continue return try catch finally throw
    throws class interface enum extends implements import package public private protected
    static final abstract synchronized volatile transient native new this super instanceof
    void boolean byte char short int long float double true false null var record
    """
)
JS_KEYWORDS = _words(
    """
    if else for while do switch case default break continue return try catch finally throw
    class extends new this super function const let var of in instanceof typeof void
    delete async await yield true false null undefined import export from require
    """
)
KEYWORDS = {"cpp17": C_KEYWORDS, "java21": JAVA_KEYWORDS, "javascript": JS_KEYWORDS}

_LEXER = re.compile(
    r"""
    (?P<comment>//[^\n]*|/\*.*?\*/)
  | (?P<preproc>^[ \t]*\#[^\n]*)
  | (?P<string>"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`)
  | (?P<number>0[xX][0-9a-fA-F']+|\d[\d']*(?:\.\d*)?(?:[eE][+-]?\d+)?[uUlLfF]*|\.\d+)
  | (?P<ident>[A-Za-z_$][A-Za-z0-9_$]*)
  | (?P<op>>>>=|<<=|>>=|===|!==|\+\+|--|->|::|&&|\|\||<=|>=|==|!=
         |\+=|-=|\*=|/=|%=|&=|\|=|\^=|<<|>>|=>|[{}()\[\];,.<>+\-*/%&|^!~?:=@])
  | (?P<space>\s+)
  | (?P<other>.)
    """,
    re.VERBOSE | re.DOTALL | re.MULTILINE,
)


@dataclass(frozen=True, slots=True)
class Token:
    text: str
    line: int


def _lex(source: str, keywords: frozenset[str]) -> list[Token]:
    out: list[Token] = []
    line = 1
    for m in _LEXER.finditer(source):
        kind, value = m.lastgroup, m.group()
        if kind == "ident":
            out.append(Token(value if value in keywords else "ID", line))
        elif kind == "number":
            out.append(Token("NUM", line))
        elif kind == "string":
            out.append(Token("STR", line))
        elif kind == "op":
            out.append(Token(value, line))
        line += value.count("\n")
    return out


def _python(source: str) -> list[Token]:
    out: list[Token] = []
    skip = {
        pytokenize.COMMENT,
        pytokenize.NL,
        pytokenize.NEWLINE,
        pytokenize.ENCODING,
        pytokenize.ENDMARKER,
    }
    for tok in pytokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type in skip:
            continue
        line = tok.start[0]
        if tok.type == pytokenize.NAME:
            out.append(Token(tok.string if keyword.iskeyword(tok.string) else "ID", line))
        elif tok.type == pytokenize.NUMBER:
            out.append(Token("NUM", line))
        elif tok.type == pytokenize.STRING or tok.type == getattr(pytokenize, "FSTRING_START", -1):
            out.append(Token("STR", line))
        elif tok.type in (
            getattr(pytokenize, "FSTRING_MIDDLE", -1),
            getattr(pytokenize, "FSTRING_END", -1),
        ):
            continue
        elif tok.type == pytokenize.INDENT:
            out.append(Token("INDENT", line))
        elif tok.type == pytokenize.DEDENT:
            out.append(Token("DEDENT", line))
        else:
            out.append(Token(tok.string, line))
    return out


def tokenize(source: str, language: str) -> list[Token]:
    if language.startswith("python"):
        try:
            return _python(source)
        except (pytokenize.TokenError, IndentationError, SyntaxError):
            return _lex(source, frozenset(keyword.kwlist))
    return _lex(source, KEYWORDS.get(language, C_KEYWORDS))
