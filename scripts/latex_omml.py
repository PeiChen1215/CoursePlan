"""把文档里用到的 LaTeX 子集转成 Word 原生公式（OMML）。

覆盖：上下标、\\frac、\\sum、\\left…\\right 定界符、\\hat、\\begin{cases}、常见符号与 \\text。
解析失败时抛 LatexError，调用方回退为纯文本，不丢内容。
"""
import re

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

SYMBOLS = {
    "ge": "≥", "le": "≤", "ne": "≠", "in": "∈", "notin": "∉", "cup": "∪",
    "setminus": "∖", "land": "∧", "lor": "∨", "neg": "¬", "exists": "∃",
    "nexists": "∄", "varnothing": "∅", "times": "×", "leftarrow": "←",
    "to": "→", "dots": "…", "mid": "|", "iff": "⇔", "quad": "\u2003",
    "qquad": "\u2003\u2003", "{": "{", "}": "}", "#": "#", "%": "%",
    "_": "_", "&": "&", "big": "", " ": " ", ",": "\u2009", ";": "\u2009",
    "Rightarrow": "⇒", "cdot": "·", "pm": "±", "ll": "≪", "gg": "≫",
    "approx": "≈", "equiv": "≡", "quad ": "\u2003",
}
FUNCS = {"log", "max", "min", "exp", "ln", "sin", "cos", "arg"}
DELIMS = {"lfloor": "⌊", "rfloor": "⌋", "lceil": "⌈", "rceil": "⌉",
          "langle": "⟨", "rangle": "⟩", "lbrace": "{", "rbrace": "}", "|": "|"}


class LatexError(Exception):
    pass


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def run(text, upright=False):
    if not text:
        return ""
    pr = '<m:rPr><m:sty m:val="p"/></m:rPr>' if upright else ""
    return "<m:r>%s<m:t xml:space=\"preserve\">%s</m:t></m:r>" % (pr, esc(text))


def tokenize(src):
    toks, i = [], 0
    while i < len(src):
        c = src[i]
        if c == "\\":
            m = re.match(r"\\([a-zA-Z]+)", src[i:])
            if m:
                toks.append("\\" + m.group(1))
                i += len(m.group(0))
            else:
                toks.append("\\" + src[i + 1])
                i += 2
        elif c in "{}^_":
            toks.append(c)
            i += 1
        elif c.isspace():
            i += 1
        else:
            toks.append(c)
            i += 1
    return toks


class Parser:
    def __init__(self, src):
        self.toks = tokenize(src)
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def next(self):
        t = self.peek()
        self.i += 1
        return t

    def group(self):
        """读一个参数：{...} 或单个原子。"""
        if self.peek() == "{":
            self.next()
            inner = self.seq(stop="}")
            if self.peek() == "}":
                self.next()
            return inner
        return self.atom()

    def atom(self):
        t = self.next()
        if t is None:
            raise LatexError("unexpected end")
        if t == "\\frac":
            return '<m:f><m:num>%s</m:num><m:den>%s</m:den></m:f>' % (self.group(), self.group())
        if t == "\\hat":
            return ('<m:acc><m:accPr><m:chr m:val="\u0302"/></m:accPr><m:e>%s</m:e></m:acc>'
                    % self.group())
        if t == "\\text":
            if self.peek() != "{":
                raise LatexError("\\text needs braces")
            self.next()
            buf = []
            while self.peek() not in (None, "}"):
                tok = self.next()
                if tok.startswith("\\"):
                    buf.append(SYMBOLS.get(tok[1:], tok))
                else:
                    buf.append(tok)
            self.next()
            return run("".join(buf), upright=True)
        if t == "\\left":
            beg = self.delim()
            body = self.seq(stop="\\right")
            if self.peek() != "\\right":
                raise LatexError("\\left without \\right")
            self.next()
            end = self.delim()
            return ('<m:d><m:dPr><m:begChr m:val="%s"/><m:endChr m:val="%s"/></m:dPr>'
                    '<m:e>%s</m:e></m:d>' % (esc(beg), esc(end), body))
        if t == "\\sum":
            sub = sup = ""
            if self.peek() == "_":
                self.next()
                sub = self.group()
            if self.peek() == "^":
                self.next()
                sup = self.group()
            body = self.seq(stop=None)
            return ('<m:nary><m:naryPr><m:chr m:val="∑"/><m:limLoc m:val="undOvr"/>'
                    '</m:naryPr><m:sub>%s</m:sub><m:sup>%s</m:sup><m:e>%s</m:e></m:nary>'
                    % (sub, sup, body))
        if t == "\\begin":
            env = self.raw_group()
            if env != "cases":
                raise LatexError("unsupported env %s" % env)
            rows = self.cases()
            arr = "".join("<m:e>%s</m:e>" % r for r in rows)
            return ('<m:d><m:dPr><m:begChr m:val="{"/><m:endChr m:val=""/></m:dPr>'
                    '<m:e><m:eqArr>%s</m:eqArr></m:e></m:d>' % arr)
        if isinstance(t, str) and t.startswith("\\"):
            name = t[1:]
            if name in FUNCS:
                return run(name, upright=True)
            if name in SYMBOLS:
                return run(SYMBOLS[name], upright=True)
            if name in DELIMS:
                return run(DELIMS[name], upright=True)
            raise LatexError("unsupported command %s" % t)
        return run(t)

    def raw_group(self):
        if self.peek() != "{":
            raise LatexError("expected {")
        self.next()
        buf = []
        while self.peek() not in (None, "}"):
            buf.append(self.next())
        self.next()
        return "".join(buf)

    def cases(self):
        rows, cur = [], []

        def flush():
            if cur:
                rows.append("".join(cur))
                cur.clear()

        while self.peek() not in (None, "\\end"):
            t = self.peek()
            if t == "\\\\":
                self.next()
                flush()
                continue
            if t == "&":
                self.next()
                cur.append(run("\u2003", upright=True))
                continue
            cur.append(self.term())
        self.next()                       # \end
        self.raw_group()                  # {cases}
        flush()
        return rows

    def delim(self):
        t = self.next()
        if t is None:
            raise LatexError("missing delimiter")
        if t.startswith("\\"):
            name = t[1:]
            if name in DELIMS:
                return DELIMS[name]
            if name in (".", ""):
                return ""
            raise LatexError("bad delimiter %s" % t)
        return t

    def term(self):
        """一个原子 + 可选上下标。"""
        base = self.atom()
        sub = sup = None
        while self.peek() in ("_", "^"):
            if self.peek() == "_":
                self.next()
                sub = self.group()
            else:
                self.next()
                sup = self.group()
        if sub is not None and sup is not None:
            return ("<m:sSubSup><m:e>%s</m:e><m:sub>%s</m:sub><m:sup>%s</m:sup></m:sSubSup>"
                    % (base, sub, sup))
        if sub is not None:
            return "<m:sSub><m:e>%s</m:e><m:sub>%s</m:sub></m:sSub>" % (base, sub)
        if sup is not None:
            return "<m:sSup><m:e>%s</m:e><m:sup>%s</m:sup></m:sSup>" % (base, sup)
        return base

    def seq(self, stop=None):
        out = []
        while True:
            t = self.peek()
            if t is None:
                break
            if stop and t == stop:
                break
            if t in ("}", "\\right", "\\end"):
                break
            out.append(self.term())
        return "".join(out)


RUN_RE = r'<m:r><m:t xml:space="preserve">[^<]*</m:t></m:r>'


def merge_runs(xml):
    """把相邻的纯文本 run 合并，避免一个字母一个 run。"""
    def _join(m):
        return m.group(0).replace('</m:t></m:r><m:r><m:t xml:space="preserve">', "")
    return re.sub(r'(?:%s){2,}' % RUN_RE, _join, xml)


def latex_to_omml(src):
    """返回 <m:oMath> 元素字符串。"""
    p = Parser(src)
    body = p.seq()
    if p.peek() is not None:
        raise LatexError("trailing tokens: %s" % p.peek())
    body = merge_runs(body)
    return "<m:oMath xmlns:m=\"%s\">%s</m:oMath>" % (M_NS, body)
