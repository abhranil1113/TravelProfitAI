"""
TBO InventoryIQ - Feature Engineering Notebook Execution Engine (Phase 3)
Executes notebooks/09_feature_engineering.ipynb in a controlled, headless environment,
captures real analytical outputs and tables, and updates the .ipynb JSON file.
"""

import sys
import os
import json
import ast
import io
import types
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

_current_cell_outputs = []


def mock_display(*args, **kwargs):
    global _current_cell_outputs
    for arg in args:
        if hasattr(arg, "to_html") and hasattr(arg, "to_string"):
            # Pandas DataFrame or Series
            _current_cell_outputs.append({
                "output_type": "display_data",
                "data": {
                    "text/html": [arg.to_html()],
                    "text/plain": [arg.to_string()],
                },
                "metadata": {},
            })
        else:
            _current_cell_outputs.append({
                "output_type": "display_data",
                "data": {
                    "text/plain": [str(arg)],
                },
                "metadata": {},
            })


def setup_ipython_shim():
    ipython = types.ModuleType("IPython")
    ipython.get_ipython = lambda: None
    ipython.version_info = (8, 24, 0)
    ipython.__version__ = "8.24.0"
    display_mod = types.ModuleType("IPython.display")
    display_mod.display = mock_display
    ipython.display = display_mod
    sys.modules["IPython"] = ipython
    sys.modules["IPython.display"] = display_mod


def execute_notebook(nb_path: Path) -> dict:
    global _current_cell_outputs
    print(f"\n========================================================")
    print(f"Executing: {nb_path.name}")
    print(f"========================================================")

    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    # Clean namespace for notebook execution
    nb_globals = {
        "__name__": "__main__",
        "__file__": str(nb_path),
        "sys": sys,
        "Path": Path,
        "display": mock_display,
    }

    cell_execution_count = 0
    executed_code_cells = 0
    total_outputs_captured = 0
    cell_summaries = []

    for idx, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "code":
            continue

        cell_execution_count += 1
        executed_code_cells += 1
        cell["execution_count"] = cell_execution_count
        cell["outputs"] = []
        _current_cell_outputs = []

        code = "".join(cell["source"]).strip()
        if not code:
            continue

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            print(f"  [ERROR] Syntax error in Cell {idx+1}: {e}")
            raise e

        # Check if the last node is an expression (e.g. DataFrame display)
        last_is_expr = bool(tree.body and isinstance(tree.body[-1], ast.Expr))
        if last_is_expr:
            body_stmts = tree.body[:-1]
            last_expr = tree.body[-1].value
        else:
            body_stmts = tree.body
            last_expr = None

        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            # Execute preceding statements
            if body_stmts:
                body_mod = ast.Module(body=body_stmts, type_ignores=[])
                compiled_body = compile(body_mod, f"<cell_{idx+1}>", "exec")
                exec(compiled_body, nb_globals)

            # Evaluate final expression if present
            eval_result = None
            if last_expr is not None:
                compiled_expr = compile(ast.Expression(body=last_expr), f"<cell_{idx+1}_expr>", "eval")
                eval_result = eval(compiled_expr, nb_globals)

        # Collect captured stdout/stderr
        captured_out = stdout_buf.getvalue()
        captured_err = stderr_buf.getvalue()

        outputs = []
        if captured_out:
            lines = [line + "\n" for line in captured_out.splitlines()]
            outputs.append({
                "output_type": "stream",
                "name": "stdout",
                "text": lines,
            })

        if captured_err:
            lines = [line + "\n" for line in captured_err.splitlines()]
            outputs.append({
                "output_type": "stream",
                "name": "stderr",
                "text": lines,
            })

        # Collect IPython display calls
        for disp in _current_cell_outputs:
            outputs.append(disp)

        # Collect final expression output if not None
        if eval_result is not None:
            if hasattr(eval_result, "to_html") and hasattr(eval_result, "to_string"):
                outputs.append({
                    "output_type": "execute_result",
                    "execution_count": cell_execution_count,
                    "data": {
                        "text/html": [eval_result.to_html()],
                        "text/plain": [eval_result.to_string()],
                    },
                    "metadata": {},
                })
            else:
                outputs.append({
                    "output_type": "execute_result",
                    "execution_count": cell_execution_count,
                    "data": {
                        "text/plain": [repr(eval_result)],
                    },
                    "metadata": {},
                })

        cell["outputs"] = outputs
        total_outputs_captured += len(outputs)
        summary = f"Cell {idx+1:02d} [Exec #{cell_execution_count:02d}]: {len(outputs)} output(s) captured."
        print(f"  {summary}")
        cell_summaries.append({
            "cell_index": idx + 1,
            "execution_count": cell_execution_count,
            "output_count": len(outputs),
            "output_types": [o["output_type"] for o in outputs],
        })

    # Save back to notebook file
    with open(nb_path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1)

    print(f"\nSuccessfully saved {nb_path.name} with {executed_code_cells} executed cells and {total_outputs_captured} outputs.")

    return {
        "notebook": nb_path.name,
        "executed_code_cells": executed_code_cells,
        "total_outputs": total_outputs_captured,
        "cell_summaries": cell_summaries,
        "status": "SUCCESS",
    }


def main():
    setup_ipython_shim()
    nb_path = BASE_DIR / "notebooks" / "09_feature_engineering.ipynb"
    result = execute_notebook(nb_path)
    print("\nExecution Summary:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
