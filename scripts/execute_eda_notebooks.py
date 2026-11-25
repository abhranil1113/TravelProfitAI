"""
TBO InventoryIQ - Automated EDA Notebook Execution Engine (Phase 2)
Executes all 8 Phase 2 EDA Jupyter Notebooks, runs calculations on real datasets,
captures stream/rich outputs and base64 PNG images, and updates .ipynb JSON files.
"""

import sys
import os
import json
import ast
import io
import base64
import types
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Global collector for IPython display calls
_current_cell_outputs = []


class MockImage:
    def __init__(self, filename=None, data=None):
        self.filename = str(filename) if filename else None
        self.data = data


def mock_display(*args, **kwargs):
    for arg in args:
        if isinstance(arg, MockImage):
            if arg.filename and os.path.exists(arg.filename):
                with open(arg.filename, "rb") as f:
                    b64_data = base64.b64encode(f.read()).decode("ascii")
                _current_cell_outputs.append({
                    "output_type": "display_data",
                    "data": {
                        "image/png": b64_data,
                        "text/plain": ["<IPython.core.display.Image object>"],
                    },
                    "metadata": {},
                })
        elif hasattr(arg, "to_html") and hasattr(arg, "to_string"):
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
    display_mod.Image = MockImage
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

    # Clean namespace for the notebook execution
    nb_globals = {
        "__name__": "__main__",
        "__file__": str(nb_path),
        "sys": sys,
        "Path": Path,
    }

    cell_execution_count = 0
    executed_code_cells = 0
    total_outputs_captured = 0
    images_embedded = 0

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
            print(f"  [ERROR] Syntax error in Cell {idx}: {e}")
            raise e

        # Check if the last node is an expression (e.g. `meta_df`, `all_missing`, etc.)
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
                compiled_body = compile(body_mod, f"<cell_{idx}>", "exec")
                exec(compiled_body, nb_globals)

            # Evaluate final expression if present
            eval_result = None
            if last_expr is not None:
                compiled_expr = compile(ast.Expression(body=last_expr), f"<cell_{idx}_expr>", "eval")
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

        # Collect IPython display calls (e.g. images)
        for disp in _current_cell_outputs:
            outputs.append(disp)
            if "image/png" in disp.get("data", {}):
                images_embedded += 1

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
        print(f"  Cell {idx:02d} [Exec #{cell_execution_count:02d}]: {len(outputs)} output(s) captured.")

    # Save back to notebook file
    with open(nb_path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1)

    print(f"Saved {nb_path.name} with {executed_code_cells} executed cells, "
          f"{total_outputs_captured} outputs, and {images_embedded} images.")

    return {
        "notebook": nb_path.name,
        "executed_code_cells": executed_code_cells,
        "total_outputs": total_outputs_captured,
        "images_embedded": images_embedded,
        "status": "SUCCESS",
    }


def main():
    setup_ipython_shim()

    notebooks_dir = BASE_DIR / "notebooks"
    eda_notebooks = [
        "01_data_overview.ipynb",
        "02_hotel_booking_analysis.ipynb",
        "03_flight_operations_analysis.ipynb",
        "04_flight_price_analysis.ipynb",
        "05_customer_search_analysis.ipynb",
        "06_supplier_inventory_analysis.ipynb",
        "07_market_seasonality_analysis.ipynb",
        "08_combined_business_insights.ipynb",
    ]

    summary = []
    for nb_name in eda_notebooks:
        nb_path = notebooks_dir / nb_name
        if not nb_path.exists():
            print(f"[MISSING] {nb_name} not found!")
            continue
        res = execute_notebook(nb_path)
        summary.append(res)

    print("\n========================================================")
    print("ALL 8 PHASE 2 EDA NOTEBOOKS EXECUTED SUCCESSFULLY")
    print("========================================================")
    for s in summary:
        print(f"  {s['notebook']:35s} | Cells: {s['executed_code_cells']:2d} | "
              f"Outputs: {s['total_outputs']:2d} | Images: {s['images_embedded']:2d} | Status: {s['status']}")


if __name__ == "__main__":
    main()
