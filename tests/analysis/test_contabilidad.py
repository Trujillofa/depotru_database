"""Re-export tests for contabilidad analysis module."""

from business_analyzer.analysis import contabilidad as cont


def test_reexports():
    assert cont.ContabilidadRunner is not None
    assert cont.pyg_summary_from_clase_rows is not None
