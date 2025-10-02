from glom import Path
from lark import Lark, Visitor


class JQ2Glom:
    grammar = r"""
    ?start: path

    path: segment ( subpath )*

    subpath: "." segment
        | "[" segment "]"

    segment: atribute
        | index
        | key

    atribute: /[a-zA-Z_][a-zA-Z0-9_]*/
    index: INT
    key: /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/


    %import common.INT
    %import common.WS_INLINE
    %ignore WS_INLINE
    """

    def __init__(self):
        self.parser = Lark(self.grammar, start="path")

    class _PathVisitor(Visitor):
        def __init__(self):
            self.segments = []

        def atribute(self, tree):
            self.segments.append(str(tree.children[0]))

        def index(self, tree):
            self.segments.append(int(tree.children[0]))

        def key(self, tree):
            raw = tree.children[0]
            self.segments.append(raw[1:-1])

    def to_glom_path(self, expr: str) -> Path:
        """Convert a path expression to a glom.Path

        Parameters
        ----------
        expr : str
            The path expression to convert.

        Returns
        -------
            A glom.Path object.
        """

        tree = self.parser.parse(expr)
        visitor = self._PathVisitor()
        visitor.visit_topdown(tree)

        return Path(*visitor.segments)
