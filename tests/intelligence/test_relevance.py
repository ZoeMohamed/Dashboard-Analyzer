from app.contracts import Topic
from app.intelligence.relevance import is_relevant_evidence, mentions_product


def test_cartoon_upin_ipin_rejected():
    topic = Topic(
        id="ayam-goreng",
        name="Ayam Goreng",
        keywords=["ayam goreng"],
        product_terms=["ayam", "goreng"],
        exclude_terms=["upin ipin", "kartun"],
    )
    # Kasus wajib: konten Upin Ipin ayam goreng harus ditolak
    text = "Upin dan Ipin episode makan ayam goreng sama Kak Ros di kampung durian runtuh"
    is_rel, score, reason = is_relevant_evidence(text, topic)
    assert not is_rel
    assert score < 0.5
    assert "dikecualikan" in reason.lower() or "upin ipin" in reason.lower()


def test_umkm_review_accepted():
    topic = Topic(
        id="ayam-goreng",
        name="Ayam Goreng",
        keywords=["ayam goreng"],
        product_terms=["ayam", "goreng"],
        exclude_terms=["upin ipin", "kartun"],
    )
    # Review kuliner UMKM lokal yang relevan
    text = "Ayam goreng kremes Bu Kris rasanya gurih banget sambalnya juara harga ramah kantong"
    is_rel, score, reason = is_relevant_evidence(text, topic)
    assert is_rel
    assert score >= 0.8
    assert "lolos" in reason.lower()


def test_product_clitics_matching():
    topic = Topic(
        id="cappuccino-cincau",
        name="Cappuccino Cincau",
        keywords=["cappuccino cincau"],
        product_terms=["cappuccino", "cincau"],
        exclude_terms=["kartun"],
    )
    # Mengandung klitika "-nya"
    text = "Seger banget cincaunya kenyal dan manisnya pas"
    assert mentions_product(text, topic)
    is_rel, score, _ = is_relevant_evidence(text, topic)
    assert is_rel


def test_unrelated_text_rejected():
    topic = Topic(
        id="cappuccino-cincau",
        name="Cappuccino Cincau",
        keywords=["cappuccino cincau"],
        product_terms=["cappuccino", "cincau"],
        exclude_terms=["kartun"],
    )
    text = "Besok ada rapat koordinasi di balai desa jam 9 pagi"
    is_rel, score, _ = is_relevant_evidence(text, topic)
    assert not is_rel
    assert score == 0.0
