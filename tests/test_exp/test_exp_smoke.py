import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXP_DIR = ROOT / "exp"
EXP_REQUIREMENTS = ROOT / "requirements-exp.txt"


def _exp_scripts() -> list[Path]:
    return sorted(EXP_DIR.glob("*.py"))


def test_exp_scripts_are_discovered():
    scripts = _exp_scripts()

    assert scripts, "expected at least one exp/*.py script"


def test_exp_scripts_parse_with_utf8_sig():
    failures: list[str] = []

    for script in _exp_scripts():
        try:
            ast.parse(script.read_text(encoding="utf-8-sig"), filename=str(script))
        except SyntaxError as exc:
            failures.append(f"{script.relative_to(ROOT)}: {exc}")

    assert failures == []


def test_exp_scripts_have_main_entrypoints():
    missing: list[str] = []

    for script in _exp_scripts():
        tree = ast.parse(script.read_text(encoding="utf-8-sig"), filename=str(script))
        has_entrypoint = any(
            isinstance(node, ast.If) and _is_main_guard(node.test)
            for node in ast.walk(tree)
        )
        if not has_entrypoint:
            missing.append(str(script.relative_to(ROOT)))

    assert missing == []


def test_exp_requirements_declares_research_only_dependencies():
    assert EXP_REQUIREMENTS.exists(), "requirements-exp.txt must exist"

    requirements = EXP_REQUIREMENTS.read_text(encoding="utf-8").splitlines()

    assert "pandas>=2.2.0" in requirements
    assert "matplotlib>=3.8.0" in requirements


def _is_main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.Compare):
        return False
    if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
        return False
    if len(node.comparators) != 1:
        return False

    left, right = node.left, node.comparators[0]
    return (
        (_is_name_dunder_main(left) and _is_string_dunder_main(right))
        or (_is_string_dunder_main(left) and _is_name_dunder_main(right))
    )


def _is_name_dunder_main(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "__name__"


def _is_string_dunder_main(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value == "__main__"
