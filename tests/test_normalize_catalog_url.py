from webrtc_preview_app.service import normalize_catalog_url


def test_normalize_bare_host_port() -> None:
    assert normalize_catalog_url("192.168.1.10:7011") == "http://192.168.1.10:7011/api/preview/catalog"


def test_normalize_full_url() -> None:
    u = "http://192.168.1.10:7011/api/preview/catalog"
    assert normalize_catalog_url(u) == u


def test_normalize_origin_only() -> None:
    assert normalize_catalog_url("http://127.0.0.1:7011/") == "http://127.0.0.1:7011/api/preview/catalog"
