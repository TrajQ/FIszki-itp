import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        yield client


def test_strona_glowna(client):
    response = client.get("/")
    assert response.status_code == 200


@pytest.mark.parametrize("sciezka", ["/atlas/", "/mpzp/", "/fiszki/", "/dostepnosc/"])
def test_placeholdery_modulow(client, sciezka):
    response = client.get(sciezka)
    assert response.status_code == 200
