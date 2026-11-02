from webrtc_preview_app.reexec import build_reexec_argv, validate_catalog_url


def test_validate_catalog_url_normalizes() -> None:
    assert validate_catalog_url("192.168.1.10:7011") == (
        "http://192.168.1.10:7011/api/preview/catalog"
    )


def test_validate_catalog_url_rejects_empty() -> None:
    try:
        validate_catalog_url("")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "required" in str(exc)


def test_build_reexec_argv_web_dev() -> None:
    argv = build_reexec_argv(
        "http://127.0.0.1:7011/api/preview/catalog",
        mode="web",
        host="0.0.0.0",
        port=7050,
        ui=False,
    )
    assert argv[1:4] == ["-m", "webrtc_preview_app", "web"]
    assert "--open" not in argv
    assert "--catalog" in argv
    assert "7050" in argv
