"""Re-export tests for factura_electronica analysis module."""

from business_analyzer.analysis import factura_electronica as fe


def test_reexports():
    assert fe.FacturaElectronicaRunner is not None
    assert fe.factura_electronica_summary_from_documento_rows is not None
    assert fe.worst_rejection_document_types is not None
