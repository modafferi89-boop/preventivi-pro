import os
import sqlite3
import pytest
from fastapi.testclient import TestClient
from main import app, get_db, init_db

# Nome del database dedicato ai test
TEST_DB = "test_preventivi.db"

# Inizializzazione del DB di test
init_db(TEST_DB)


# Override della dipendenza get_db per puntare al database di test
def override_get_db():
    conn = sqlite3.connect(TEST_DB)
    try:
        yield conn
    finally:
        conn.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    """Pulisce le tabelle del database di test prima di ogni esecuzione."""
    init_db(TEST_DB)
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM preventivi")
    cursor.execute("DELETE FROM users")
    conn.commit()
    conn.close()
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

    # 1. Registrazione
    response_reg = client.post("/api/register", json=user_data)
    assert response_reg.status_code == 200

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
    user_data = {
        "username": "vincenzo_test",
        "password": "securepassword123",
        "professionista": "Vincenzo Modafferi",
        "partita_iva": "12345678901",
        "recapito": "Reggio Calabria",
        "email": "vincenzo@example.com"
    }

    # Registriamo e facciamo il login per ottenere il token
    client.post("/api/register", json=user_data)
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

    # Verifica del totale finale calcolato dal motore (680.76)
    assert res_data["dettaglio_economico"]["totale_finale"] == 680.76


# --- NUOVI TEST AVANZATI PER EDGE CASES ---

def test_duplicate_user_registration():
    """Verifica che non sia possibile registrare due utenti con lo stesso username."""
    user_data = {
        "username": "utente_doppio",
        "password": "password123",
        "professionista": "Mario Rossi",
        "partita_iva": "98765432109",
        "recapito": "Milano",
        "email": "mario@example.com"
    }

    # Prima registrazione (deve riuscire)
    response_1 = client.post("/api/register", json=user_data)
    assert response_1.status_code == 200

    # Seconda registrazione con lo stesso username (deve fallire con 400)
    response_2 = client.post("/api/register", json=user_data)
    assert response_2.status_code == 400
    assert response_2.json()["detail"] == "Username già registrato"


def test_preventivo_validation_errors():
    """Verifica che Pydantic blocchi valori negativi per ore o costi (errore 422)."""
    user_data = {
        "username": "test_val",
        "password": "password123",
        "professionista": "Test",
        "partita_iva": "11111111111",
        "recapito": "Roma",
        "email": "test@example.com"
    }
    client.post("/api/register", json=user_data)
    login_res = client.post("/api/login", data={"username": "test_val", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Payload con ore di lavoro negative (non consentite dal modello Pydantic)
    preventivo_errato = {
        "cliente": "Cliente Test",
        "progetto": "Progetto Errato",
        "ore_lavoro": -5.0,  # Valore non valido
        "costo_orario": 50.0,
        "sconto_percentuale": 0.0
    }

    response = client.post("/api/calcola", json=preventivo_errato, headers=headers)
    assert response.status_code == 422


def test_unauthorized_access():
    """Verifica che un utente non autenticato non possa accedere agli endpoint protetti."""
    response = client.get("/api/preventivi")
    assert response.status_code == 401