"""Provider adapters: no real requests are made. HTTP is mocked."""
import httpx
import pytest

from backend.app.providers.adapters import all_providers
from backend.app.providers.base_provider import ProviderResult, UnsupportedData
from backend.app.providers.pandascore_provider import PandaScoreProvider


def test_all_providers_pending_without_credentials():
    for p in all_providers():
        s = p.status()
        assert s["configured"] is False
        assert s["state"] == "integration_pending"
        assert "key" not in str(s).lower() or s["env_var"].endswith("_API_KEY")  # only the variable name


def test_missing_key_returns_structured_unsupported():
    r = PandaScoreProvider(api_key="").get_matches()
    assert isinstance(r, UnsupportedData)
    assert r.status == "not_configured" and r.data is None


def test_unverified_endpoint_is_not_called():
    calls = []
    transport = httpx.MockTransport(lambda req: calls.append(req) or httpx.Response(200, json=[]))
    p = PandaScoreProvider(api_key="dummy", client=httpx.Client(transport=transport, base_url="https://x"))
    r = p.get_tournaments()
    assert isinstance(r, UnsupportedData) and r.status == "not_verified"
    assert calls == []


def test_retry_with_backoff_on_429(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    responses = iter([httpx.Response(429, headers={"Retry-After": "1"}), httpx.Response(500), httpx.Response(200, json=[{"id": 1}])])
    transport = httpx.MockTransport(lambda req: next(responses))

    class Verified(PandaScoreProvider):
        verified_endpoints = {"get_matches": "/csgo/matches"}
        requests_per_second = 0

    p = Verified(api_key="dummy", client=httpx.Client(transport=transport, base_url="https://x"))
    r = p.get_matches()
    assert isinstance(r, ProviderResult) and r.data == [{"id": 1}]


def test_non_retryable_error_raises(monkeypatch):
    transport = httpx.MockTransport(lambda req: httpx.Response(401))

    class Verified(PandaScoreProvider):
        verified_endpoints = {"get_matches": "/csgo/matches"}
        requests_per_second = 0

    p = Verified(api_key="dummy", client=httpx.Client(transport=transport, base_url="https://x"))
    with pytest.raises(httpx.HTTPStatusError):
        p.get_matches()


def test_file_placed_in_raw_folder_is_registered_without_copy(tmp_path, monkeypatch):
    """A CSV moved straight into data/raw/oracles_elixir is registered in place."""
    from pipelines.oracle_elixir import download
    raw = tmp_path / "raw"
    raw.mkdir()
    monkeypatch.setattr(download, "RAW_DIR", raw)
    monkeypatch.setattr(download, "MANIFEST", raw / "manifest.json")
    monkeypatch.setattr(download, "ensure_dirs", lambda: None)
    f = raw / "2024_LoL.csv"
    f.write_text("gameid\n1\n")
    e = download.import_local_file(f)
    assert e["filename"] == "2024_LoL.csv"
    assert sorted(p.name for p in raw.iterdir()) == ["2024_LoL.csv", "manifest.json"]
    assert download.import_local_file(f)["sha256"] == e["sha256"]  # idempotent


def test_database_url_normalised_for_psycopg():
    from backend.app.core.config import Settings
    assert Settings(database_url="postgresql://u:p@h:5432/d").database_url == "postgresql+psycopg://u:p@h:5432/d"
    assert Settings(database_url="postgres://u:p@h/d").database_url == "postgresql+psycopg://u:p@h/d"
    assert Settings(database_url="sqlite:///x.db").database_url == "sqlite:///x.db"
    assert Settings(cors_origins="https://a.vercel.app/, http://localhost:3000").cors_origin_list == [
        "https://a.vercel.app", "http://localhost:3000"]
