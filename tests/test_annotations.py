"""Guards against type names used in annotations but never imported.

Python 3.14 evaluates annotations lazily, so a missing `from typing import
Tuple` raises nothing on a developer machine running 3.14 while breaking
immediately on the 3.10 and 3.12 the application supports. This test closes
that gap by checking the source directly, on every version.
"""

import ast
import pathlib
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

SKIP_DIRS = {"__pycache__", "build", "dist", "release", ".git", ".venv", "venv"}

TYPING_NAMES = {
    "Optional", "Tuple", "List", "Dict", "Any", "Callable", "Set", "Union",
    "Iterable", "Sequence", "Mapping", "NamedTuple", "Type", "Generator",
    "Iterator", "Pattern", "Deque", "FrozenSet", "Awaitable", "Coroutine",
}


def _source_files():
    for path in sorted(PROJECT_ROOT.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def _names_bound_at_module_level(tree: ast.AST) -> set:
    """Collects every name an annotation could legally refer to."""
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            bound |= {alias.asname or alias.name for alias in node.names}
        elif isinstance(node, ast.Import):
            bound |= {(alias.asname or alias.name).split(".")[0] for alias in node.names}
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            bound |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return bound


def _names_used_in_annotations(tree: ast.AST) -> set:
    used = set()
    for node in ast.walk(tree):
        annotations = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for arg in list(args.args) + list(args.kwonlyargs) + list(args.posonlyargs):
                if arg.annotation:
                    annotations.append(arg.annotation)
            if node.returns:
                annotations.append(node.returns)
        elif isinstance(node, ast.AnnAssign) and node.annotation:
            annotations.append(node.annotation)

        for annotation in annotations:
            used |= {
                inner.id for inner in ast.walk(annotation) if isinstance(inner, ast.Name)
            }
    return used


class TestAnnotationImports(unittest.TestCase):

    def test_every_annotation_name_is_imported(self):
        offenders = []
        for path in _source_files():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            missing = (_names_used_in_annotations(tree) & TYPING_NAMES)
            missing -= _names_bound_at_module_level(tree)
            if missing:
                offenders.append(
                    f"{path.relative_to(PROJECT_ROOT)}: {', '.join(sorted(missing))}"
                )

        self.assertEqual(
            offenders, [],
            "Type names used in annotations but never imported. These raise "
            "NameError on Python 3.10 and 3.12, but not on 3.14:\n  "
            + "\n  ".join(offenders)
        )

    def test_the_scan_actually_finds_a_planted_problem(self):
        """A check that silently passes on everything is worth nothing."""
        tree = ast.parse(
            "from typing import Optional\n"
            "def f(x: Optional[int]) -> Tuple[int, int]: ...\n"
        )
        missing = (_names_used_in_annotations(tree) & TYPING_NAMES)
        missing -= _names_bound_at_module_level(tree)
        self.assertEqual(missing, {"Tuple"})


if __name__ == "__main__":
    unittest.main()
