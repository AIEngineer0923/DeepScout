from deepscout_api.routes.research_runs import _report_pdf, _wrap_pdf_line


def test_pdf_wraps_long_lines_and_paginates() -> None:
    wrapped = _wrap_pdf_line("word " * 40, 20)
    assert all(len(line) <= 20 for line in wrapped)
    pdf = _report_pdf("Title that should appear", "# Heading\n\n" + ("citation [E1] " * 80))
    assert pdf.startswith(b"%PDF-1.4")
    assert b"Helvetica" in pdf
    assert b"Title that should appear" in pdf


def test_pdf_renders_markdown_tables_without_pipe_syntax() -> None:
    body = """# Confronto

| Dimensione | Hybrid RAG | GraphRAG |
| :--- | :--- | :--- |
| **Qualita** | Buona [1] | Alta |
"""
    pdf = _report_pdf("Report", body)
    assert pdf.startswith(b"%PDF-1.4")
    assert b"|" not in pdf
    assert b"Dimensione" in pdf
    assert b"Hybrid RAG" in pdf
    assert b"Qualita" in pdf
