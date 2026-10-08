from datetime import datetime, timedelta
import os
import sqlite3
import uuid
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from passlib.context import CryptContext
from jose import JWTError, jwt
import stripe
from motore_preventivi import calcola_preventivo
from generatore_pdf import crea_pdf_preventivo

# Configurazione Sicurezza JWT & Stripe
SECRET_KEY = os.getenv("SECRET_KEY", "chiave_segreta_super_sicura_da_cambiare_in_produzione")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 ore
TRIAL_DAYS = 15

# Dominio dell'app (prende quello di Render o fallback su localhost)
BASE_URL = os.getenv("BASE_URL", "https://preventivi-pro.onrender.com")

# Configurazione della chiave Stripe tramite variabile d'ambiente
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "price_1UL9qvRotEeMbBqAwAA6XeDo")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

app = FastAPI(
    title="Preventivi Pro API - Multi-tenant & Trial",
    description="Backend SaaS con autenticazione JWT, database SQLite, gestione trial e pagamenti Stripe",
)

app.mount("/static", StaticFiles(directory="static"), name="static")

DB_FILE = "preventivi.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS utenti (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            professionista TEXT,
            partita_iva TEXT,
            recapito TEXT,
            email TEXT,
            data_registrazione TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS preventivi (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            data_creazione TEXT,
            cliente TEXT,
            progetto TEXT,
            periodo TEXT,
            totale_finale REAL,
            pdf_url TEXT,
            FOREIGN KEY(user_id) REFERENCES utenti(id)
        )
    ''')
    conn.commit()
    conn.close()


init_db()


def calcola_stato_trial(data_registrazione_str: str):
    try:
        data_reg = datetime.fromisoformat(data_registrazione_str)
        scadenza = data_reg + timedelta(days=TRIAL_DAYS)
        oggi = datetime.now()
        delta = scadenza - oggi
        days_left = delta.days

        if oggi > scadenza:
            return {"expired": True, "days_left": 0}
        return {"expired": False, "days_left": max(0, days_left)}
    except Exception:
        return {"expired": True, "days_left": 0}


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenziali di autenticazione non valide",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM utenti WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()

    if user is None:
        raise credentials_exception

    user_dict = dict(user)
    trial_info = calcola_stato_trial(user_dict["data_registrazione"])
    if trial_info["expired"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="⚠️ Il tuo periodo di prova gratuito di 15 giorni è scaduto. Passa a PRO per continuare."
        )

    return user_dict


class UserRegister(BaseModel):
    username: str = Field(..., max_length=50)
    password: str = Field(..., min_length=6)
    professionista: str = Field(..., max_length=100)
    partita_iva: Optional[str] = Field("", max_length=30)
    recapito: Optional[str] = Field("", max_length=40)
    email: Optional[str] = Field("", max_length=100)


class VoceSpesa(BaseModel):
    descrizione: str = Field(..., max_length=100)
    importo: float = Field(..., ge=0, le=1000000)


class PreventivoRequest(BaseModel):
    cliente: str = Field(..., max_length=100)
    progetto: str = Field(..., max_length=150)
    data: Optional[str] = Field("", max_length=50)
    validita: Optional[str] = Field("15 giorni dalla data", max_length=50)
    ore_lavoro: float = Field(..., ge=0, le=10000)
    costo_orario: float = Field(..., ge=0, le=10000)
    sconto_percentuale: float = Field(0.0, ge=0, le=100)
    voci_extra: Optional[List[VoceSpesa]] = Field(default=[], max_length=20)


@app.post("/api/register")
def register_user(user: UserRegister):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM utenti WHERE username = ?", (user.username,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Username già registrato.")

    user_id = uuid.uuid4().hex
    hashed_pwd = get_password_hash(user.password)
    data_reg_attuale = datetime.now().isoformat()

    cursor.execute('''
        INSERT INTO utenti (id, username, password_hash, professionista, partita_iva, recapito, email, data_registrazione)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, user.username, hashed_pwd, user.professionista, user.partita_iva, user.recapito, user.email,
          data_reg_attuale))
    conn.commit()
    conn.close()
    return {"message": "Registrazione avvenuta con successo. Hai 15 giorni di prova gratuita!"}


@app.post("/api/login")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM utenti WHERE username = ?", (form_data.username,))
    user = cursor.fetchone()
    conn.close()

    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username o password errati",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_dict = dict(user)
    trial_info = calcola_stato_trial(user_dict["data_registrazione"])
    if trial_info["expired"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="⚠️ Il tuo periodo di prova di 15 giorni è scaduto."
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "professionista": user["professionista"],
        "days_left": trial_info["days_left"]
    }


@app.get("/api/user/me")
def read_users_me(current_user: dict = Depends(get_current_user)):
    trial_info = calcola_stato_trial(current_user["data_registrazione"])
    return {
        "username": current_user["username"],
        "professionista": current_user["professionista"],
        "partita_iva": current_user["partita_iva"],
        "recapito": current_user["recapito"],
        "email": current_user["email"],
        "days_left": trial_info["days_left"]
    }


@app.post("/api/crea-sessione-checkout")
def crea_sessione_checkout(current_user: dict = Depends(get_current_user)):
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': STRIPE_PRICE_ID,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f'{BASE_URL}/pagamento/successo?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{BASE_URL}/pagamento/annullato',
            client_reference_id=str(current_user["id"]),
            customer_email=current_user.get("email") if current_user.get("email") else None
        )
        return {"url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/pagamento/successo", response_class=HTMLResponse)
def pagamento_successo():
    return """<html><body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
        <h1 style="color: green;">🎉 Pagamento completato con successo!</h1>
        <a href="/">Torna all'applicazione</a></body></html>"""


@app.get("/pagamento/annullato", response_class=HTMLResponse)
def pagamento_annullato():
    return """<html><body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
        <h1 style="color: orange;">⚠️ Pagamento Annullato</h1>
        <a href="/">Torna alla dashboard</a></body></html>"""


@app.get("/", response_class=HTMLResponse)
def home():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/preventivi")
def lista_preventivi(current_user: dict = Depends(get_current_user)):
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM preventivi WHERE user_id = ? ORDER BY data_creazione DESC LIMIT 30",
                       (current_user["id"],))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/preventivi/{preventivo_id}")
def elimina_preventivo(preventivo_id: str, current_user: dict = Depends(get_current_user)):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM preventivi WHERE id = ? AND user_id = ?", (preventivo_id, current_user["id"]))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Preventivo non trovato.")

        cursor.execute("DELETE FROM preventivi WHERE id = ? AND user_id = ?", (preventivo_id, current_user["id"]))
        conn.commit()
        conn.close()
        return {"message": "Preventivo eliminato con successo."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/calcola")
def genera_preventivo(dati: PreventivoRequest, current_user: dict = Depends(get_current_user)):
    try:
        calcoli = calcola_preventivo(
            ore_lavoro=dati.ore_lavoro,
            costo_orario=dati.costo_orario,
            margine_percentuale=0.0,
            sconto_percentuale=dati.sconto_percentuale,
            voci_extra=[v.dict() for v in dati.voci_extra]
        )

        dati_dict = {
            "professionista": current_user["professionista"],
            "partita_iva": current_user["partita_iva"],
            "recapito": current_user["recapito"],
            "email": current_user["email"],
            "cliente": dati.cliente,
            "progetto": dati.progetto,
            "data": dati.data,
            "validita": dati.validita,
            "ore_lavoro": dati.ore_lavoro,
            "costo_orario": dati.costo_orario
        }

        preventivo_id = uuid.uuid4().hex[:8]
        nome_file_univoco = f"preventivo_{preventivo_id}.pdf"
        crea_pdf_preventivo(dati_dict, calcoli, filename=nome_file_univoco)

        pdf_url = f"/static/{nome_file_univoco}"
        timestamp_attuale = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO preventivi (id, user_id, data_creazione, cliente, progetto, periodo, totale_finale, pdf_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (preventivo_id, current_user["id"], timestamp_attuale, dati.cliente, dati.progetto, dati.data,
              calcoli["totale_finale"], pdf_url))
        conn.commit()
        conn.close()

        return {
            "id": preventivo_id,
            "professionista": current_user["professionista"],
            "cliente": dati.cliente,
            "progetto": dati.progetto,
            "dettaglio_economico": calcoli,
            "pdf_url": pdf_url
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app_server:app", host="127.0.0.1", port=8000, reload=True)