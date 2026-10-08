import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    """Pulisce o prepara l'ambiente prima di ogni esecuzione di test."""
    yield


def test_root_endpoint():
    """Verifica che la root restituisca la dashboard HTML o risponda correttamente."""
    response = client.get("/")
    assert response.status_code == 200
    assert "<html" in response.text.lower() or "<!doctype html>" in response.text.lower()


def test_user_registration_and_login():
    """Verifica il flusso completo di registrazione e login utente."""
    user_data = {
        "username": "vincenzo_test",
        "password": "securepassword123",
        "professionista": "Vincenzo Modafferi",
        "partita_iva": "12345678901",
        "recapito": "Reggio Calabria",
        "email": "vincenzo@example.com"
    }

    # 1. Registrazione (accetta 200 OK o 400 se l'utente è già registrato nei test precedenti)
    response_reg = client.post("/api/register", json=user_data)
    assert response_reg.status_code in [200, 400]

    # 2. Login per ottenere il token JWT
    response_login = client.post(
        "/api/login",
        data={"username": "vincenzo_test", "password": "securepassword123"}
    )
    assert response_login.status_code == 200
    data = response_login.json()
    assert "access_token" in data
    assert data["professionista"] == "Vincenzo Modafferi"


def test_genera_preventivo_protetto():
    """Verifica che un utente autenticato possa generare un preventivo correttamente."""
    # Eseguiamo il login per recuperare il token
    response_login = client.post(
        "/api/login",
        data={"username": "vincenzo_test", "password": "securepassword123"}
    )

    # Se l'utente non esiste, lo registriamo al volo
    if response_login.status_code != 200:
        client.post("/api/register", json={
            "username": "vincenzo_test",
            "password": "securepassword123",
            "professionista": "Vincenzo Modafferi",
            "partita_iva": "12345678901",
            "recapito": "Reggio Calabria",
            "email": "vincenzo@example.com"
        })
        response_login = client.post(
            "/api/login",
            data={"username": "vincenzo_test", "password": "securepassword123"}
        )

    token = response_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Dati del preventivo da testare
    preventivo_payload = {
        "cliente": "Cliente di Prova",
        "progetto": "Sito Web e Consulenza",
        "data": "2026-10-02",
        "validita": "30 giorni",
        "ore_lavoro": 10.0,
        "costo_orario": 50.0,
        "sconto_percentuale": 10.0,
        "voci_extra": [
            {"descrizione": "Hosting Annuale", "importo": 120.0}
        ]
    }

    response = client.post("/api/calcola", json=preventivo_payload, headers=headers)
    assert response.status_code == 200
    res_data = response.json()

    assert "id" in res_data
    assert res_data["cliente"] == "Cliente di Prova"
    assert "dettaglio_economico" in res_data

    # Verifica del totale finale restituito dal motore dei preventivi (inclusivo di eventuali tasse/IVA gestite dal motore)
    assert res_data["dettaglio_economico"]["totale_finale"] == 680.76