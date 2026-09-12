from legal.connectors.nh_supreme_court_opinions import parse_supreme_court_opinion_index


HTML = """
<html><body>
<h1>2025 Published Opinions</h1>
<a href="/our-courts/supreme-court/orders-and-opinions/2025/2025-nh-001.pdf">2025 N.H. 1 Smith v. Jones</a>
<a href="/our-courts/supreme-court/orders-and-opinions/2025/2025-nh-002.pdf">FAM-24-123 Doe v. Doe 1/15/2025</a>
</body></html>
"""


def test_supreme_court_opinion_index_parser_extracts_pdf_references():
    opinions, audit = parse_supreme_court_opinion_index(
        HTML,
        source_id="nh-supreme-court-2025",
        url="https://www.courts.nh.gov/our-courts/supreme-court/orders-and-opinions",
    )

    assert audit.status == "parsed"
    assert len(opinions) == 2
    assert opinions[0].href.endswith("2025-nh-001.pdf")
    assert opinions[0].validate() == []
    assert opinions[1].docket_number == "FAM-24-123"
