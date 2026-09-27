import pytest


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Offer loading waits between clicks and before retries; tests skip the waiting."""
    import cardmarket_scrapedo.client as client
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
