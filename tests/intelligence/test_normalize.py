from app.intelligence.normalize import normalize, tokenize


def test_normalize_slang_expansion():
    text = "cincaunya enak bgt tp hrg nya agak mahal krn ongkir udh naik"
    result = normalize(text)
    assert "banget" in result
    assert "tapi" in result
    assert "harga" in result
    assert "karena" in result
    assert "ongkos kirim" in result
    assert "sudah" in result


def test_normalize_removes_url_and_mentions():
    text = "Promo di https://example.com/promo hubungi @admin_capcin segera!"
    result = normalize(text)
    assert "https" not in result
    assert "@admin_capcin" not in result


def test_normalize_preserves_hashtag_words():
    text = "Seger banget #cappuccinocincau #kulinerbandung"
    result = normalize(text)
    assert "#" not in result
    assert "cappuccinocincau" in result
    assert "kulinerbandung" in result


def test_normalize_reduces_repeated_characters():
    text = "enakkkk bangeeeet nagihhhh"
    result = normalize(text)
    assert "enak" in result
    assert "banget" in result
    assert "nagih" in result


def test_tokenize():
    tokens = tokenize("Rasanya enak bgt!")
    assert tokens == ["rasanya", "enak", "banget"]
