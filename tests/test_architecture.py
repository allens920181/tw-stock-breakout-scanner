"""
架構守門測試：確保分層依賴方向不被破壞（規則說明見 docs/ARCHITECTURE.md）。

新增子套件時，請在 ALLOWED 補上它可以依賴哪些層；違規 import 會讓這支測試失敗。
"""
import ast
import pathlib

PKG = pathlib.Path(__file__).resolve().parents[1] / "twscanner"

# 每一層「可以 import 的層」（含自己）。由下而上：越下層依賴越少。
ALLOWED = {
    "core": {"core"},
    "data": {"core", "data"},
    "analysis": {"core", "analysis"},
    "storage": {"core", "storage"},
    "strategy": {"core", "data", "analysis", "strategy"},
    "market": {"core", "data", "analysis", "market"},
    "portfolio": {"core", "data", "analysis", "portfolio"},
    "reporting": {"core", "analysis", "reporting"},
    "research": {"core", "data", "analysis", "strategy", "market", "research"},
    "services": {"core", "data", "analysis", "strategy", "market", "portfolio",
                 "research", "storage", "reporting", "services"},
    "ui": {"core", "data", "analysis", "strategy", "market", "portfolio",
           "research", "storage", "reporting", "services", "ui"},
    "cli": {"core", "data", "reporting", "services"},
}
# 只有 UI 層可以碰 Streamlit
UI_ONLY_LIBS = {"streamlit"}


def _layer(path):
    rel = path.relative_to(PKG)
    return rel.parts[0].removesuffix(".py") if len(rel.parts) > 1 or rel.stem != "__init__" else None


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.level:
                raise AssertionError(f"{path}: 請用絕對 import（from twscanner.x import y），不要用相對 import")
            yield node.lineno, node.module
        elif isinstance(node, ast.Import):
            for a in node.names:
                yield node.lineno, a.name


def _modules():
    return [p for p in PKG.rglob("*.py") if _layer(p)]


def test_every_layer_is_declared():
    layers = {_layer(p) for p in _modules()}
    assert layers <= set(ALLOWED), f"新的子套件未在 ALLOWED 宣告：{layers - set(ALLOWED)}"


def test_layer_dependencies():
    violations = []
    for path in _modules():
        layer = _layer(path)
        for lineno, mod in _imports(path):
            parts = mod.split(".")
            if parts[0] == "twscanner" and len(parts) > 1 and parts[1] in ALLOWED:
                target = parts[1]
                if target not in ALLOWED[layer]:
                    violations.append(f"{path.relative_to(PKG.parent)}:{lineno} {layer} → {target}（{mod}）")
            if parts[0] in UI_ONLY_LIBS and layer != "ui":
                violations.append(f"{path.relative_to(PKG.parent)}:{lineno} {layer} 不可 import {parts[0]}")
    assert not violations, "違反分層規則：\n" + "\n".join(violations)


def test_entrypoints_stay_thin():
    root = PKG.parent
    for name, limit in (("app.py", 20), ("main.py", 15)):
        n = len((root / name).read_text(encoding="utf-8").splitlines())
        assert n <= limit, f"{name} 應只做啟動（{n} 行 > {limit}），邏輯請放進 twscanner/"
