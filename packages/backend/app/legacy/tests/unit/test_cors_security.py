from api.cors import get_cors_allowed_origins


def test_configured_origin_is_allowed():
    assert get_cors_allowed_origins("http://localhost:3000") == [
        "http://localhost:3000"
    ]


def test_trailing_slash_is_removed():
    assert get_cors_allowed_origins("http://localhost:3000/") == [
        "http://localhost:3000"
    ]


def test_missing_origin_disables_cross_origin_access():
    assert get_cors_allowed_origins(None) == []


def test_empty_origin_disables_cross_origin_access():
    assert get_cors_allowed_origins("") == []


def test_whitespace_origin_disables_cross_origin_access():
    assert get_cors_allowed_origins("   ") == []

def test_wildcard_origin_is_rejected():
    assert get_cors_allowed_origins("*") == []


def test_javascript_scheme_is_rejected():
    assert get_cors_allowed_origins("javascript:alert(1)") == []


def test_origin_with_path_is_rejected():
    assert get_cors_allowed_origins("http://localhost:3000/untrusted") == []


def test_origin_with_credentials_is_rejected():
    assert get_cors_allowed_origins(
        "http://user:password@localhost:3000"
    ) == []


def test_valid_https_origin_is_allowed():
    assert get_cors_allowed_origins("https://example.com") == [
        "https://example.com"
    ]


def test_invalid_port_is_rejected():
    assert get_cors_allowed_origins("http://localhost:99999") == []