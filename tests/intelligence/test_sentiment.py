from app.contracts import SentimentLabel
from app.intelligence.sentiment import LexiconAnalyzer, extract_aspects, top_keywords


def test_positive_sentiment():
    analyzer = LexiconAnalyzer()
    res = analyzer.analyze_text("enak banget es cincaunya segar juara")
    assert res.label == SentimentLabel.POSITIF
    assert res.score > 0.2


def test_negative_sentiment_with_negation():
    analyzer = LexiconAnalyzer()
    res = analyzer.analyze_text("tidak enak terlalu manis dan cincaunya alot")
    assert res.label == SentimentLabel.NEGATIF
    assert res.score < -0.2


def test_double_negation_positive():
    analyzer = LexiconAnalyzer()
    # "nggak mengecewakan" (mengecewakan = -1, dinegasi = +1)
    res = analyzer.analyze_text("rasanya mantap nggak mengecewakan sama sekali")
    assert res.label == SentimentLabel.POSITIF
    assert res.score > 0.0


def test_rhetorical_question_positive():
    analyzer = LexiconAnalyzer()
    # Kasus wajib: "siapa sih yang nggak suka es satu ini?" -> positif
    res = analyzer.analyze_text("Siapa sih yang nggak suka es cappuccino cincau ini?")
    assert res.label == SentimentLabel.POSITIF
    assert res.score == 1.0


def test_finally_product_launched_positive():
    analyzer = LexiconAnalyzer()
    # Kasus wajib: "akhirnya ... hadir" -> positif
    res = analyzer.analyze_text("Akhirnya es cappuccino cincau kekinian hadir dan bisa kamu nikmati")
    assert res.label == SentimentLabel.POSITIF
    assert res.score >= 0.8


def test_neutral_promotional_caption():
    analyzer = LexiconAnalyzer()
    # Kasus wajib: caption promosi / pengumuman tanpa opini -> netral
    res = analyzer.analyze_text("Grand launching outlet cabang baru tanggal 15 Oktober pukul 10.00 WIB")
    assert res.label == SentimentLabel.NETRAL


def test_delivery_complaint_and_taste_aspect():
    analyzer = LexiconAnalyzer()
    # Aspek pengiriman dan rasa diekstrak
    text = "Pengiriman lama banget kurirnya tumpah tapi rasa cincaunya tetap enak"
    res = analyzer.analyze_text(text)
    aspects = extract_aspects(text)
    assert "pengiriman" in aspects
    assert "rasa" in aspects


def test_top_keywords_extraction():
    texts = [
        "cappuccino cincau rasanya enak dan manis banget",
        "cincau kenyal rasa mantap harga murah",
        "es cappuccino cincau segar harga terjangkau",
    ]
    # Unigram keyword counter
    keywords = top_keywords(texts, exclude=["cappuccino", "cincau"], n=5, ngram=1)
    words = [kw for kw, _ in keywords]
    assert "dan" not in words  # stopword eliminated
    assert "cincau" not in words  # excluded product term eliminated
    assert any(w in words for w in ["rasa", "rasanya", "harga", "enak", "manis"])

    # Bigram keyword counter
    bigrams = top_keywords(texts, exclude=["cappuccino", "cincau"], n=5, ngram=2)
    assert len(bigrams) > 0
