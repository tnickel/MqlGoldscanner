"""Statischer Test: das MT5-Modul enthält NUR Whitelist-Aufrufe (KiScanner-Muster).
TIMEFRAME-/Sonstige Konstanten sind erlaubt — geprüft werden Funktions-CALLS."""
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from goldscanner.mt5.kurse import ERLAUBTE_MT5_AUFRUFE

MODUL = Path(__file__).resolve().parents[1] / "src" / "goldscanner" / "mt5" / "kurse.py"


def _mt5_funktionsaufrufe() -> set[str]:
    baum = ast.parse(MODUL.read_text(encoding="utf-8"))
    return {k.func.attr for k in ast.walk(baum)
            if isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute)
            and isinstance(k.func.value, ast.Name) and k.func.value.id == "mt5"}


def test_nur_whitelist_aufrufe():
    gefunden = _mt5_funktionsaufrufe()
    assert gefunden, "es sollten MT5-Aufrufe vorhanden sein"
    verboten = gefunden - ERLAUBTE_MT5_AUFRUFE
    assert not verboten, f"Whitelist verletzt: {verboten}"
