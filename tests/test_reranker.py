from legal.retrieval.reranker import NewHampshireAuthorityReranker

def test_official_authority_ranks_first():
    reranker = NewHampshireAuthorityReranker()

    results = [
        {"authority_status": "unverified"},
        {"authority_status": "verified_official_nh"},
    ]

    reranked = reranker.rerank(results)

    assert reranked[0]["authority_status"] == "verified_official_nh"