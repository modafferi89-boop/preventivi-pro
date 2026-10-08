from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy import Column, Float, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

# Caricamento variabili d'ambiente dal file .env
load_dotenv()

# 1. SECRET_KEY sicura letta da variabile d'ambiente (con fallback di sicurezza)
SECRET_KEY = os.getenv(
    "SECRET_KEY", "chiave-segreta-molto-sicura-per-preventivi-pro-da-cambiare-in-produzione"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

app = FastAPI(title="Preventivi Pro", version="1.0.0")

# --- CONFIGURAZIONE CORS ---
# Permette l'accesso sicuro sia in locale che dai domini di produzione (es. Render)
origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://preventivi-pro.onrender.com",  # Sostituisci o integra con il tuo dominio definitivo su Render
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Usa ["*"] temporaneamente se vuoi consentire qualsiasi origine durante i test
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Configurazione Database: legge DATABASE_URL dal cloud o usa SQLite locale per default
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SQLite = f"sqlite:///{BASE_DIR / 'preventivi_pro.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_SQLite)

# Fix per eventuali URL di PostgreSQL su Render che iniziano con postgres:// anziché postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if "sqlite" in DATABASE_URL
    else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Definizione delle Tabelle ORM
class DBUser(Base):
    __tablename__ = "users"
    username = Column(String, primary_key=True, index=True)
    password = Column(String, nullable=False)
    professionista = Column(String)
    partita_iva = Column(String)
    recapito = Column(String)
    email = Column(String)


class DBPreventivo(Base):
    __tablename__ = "preventivi"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, index=True)
    cliente = Column(String)
    progetto = Column(String)
    data = Column(String)
    validita = Column(String)
    ore_lavoro = Column(Float)
    costo_orario = Column(Float)
    sconto_percentuale = Column(Float)
    totale_finale = Column(Float)
    dettaglio_json = Column(Text)


# Creazione automatica delle tabelle all'avvio
Base.metadata.create_all(bind=engine)


# Dipendenza per la sessione del database
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Modelli Pydantic con validazione dei dati
class UserRegister(BaseModel):
    username: str
    password: str
    professionista: Optional[str] = "Professionista"
    partita_iva: Optional[str] = ""
    recapito: Optional[str] = ""
    email: Optional[str] = ""


class VoceExtra(BaseModel):
    descrizione: str
    importo: float = Field(
        ..., ge=0.0, description="L'importo non può essere negativo"
    )


class PreventivoRequest(BaseModel):
    cliente: str
    progetto: str
    data: Optional[str] = None
    validita: Optional[str] = "30 giorni"
    ore_lavoro: float = Field(
        ..., ge=0.0, description="Le ore di lavoro non possono essere negative"
    )
    costo_orario: float = Field(
        ..., ge=0.0, description="Il costo orario non può essere negativo"
    )
    margine_percentuale: Optional[float] = Field(
        0.0, ge=0.0, le=100.0, description="Il margine deve essere tra 0 e 100"
    )
    sconto_percentuale: Optional[float] = Field(
        0.0, ge=0.0, le=100.0, description="Lo sconto deve essere tra 0 e 100"
    )
    voci_extra: Optional[List[VoceExtra]] = []


# Utility funzioni
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenziali non valide o token scaduto",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    user = db.query(DBUser).filter(DBUser.username == username).first()
    if user is None:
        raise credentials_exception
    return {"username": user.username, "professionista": user.professionista}


# Endpoint Principali - Restituisce la Dashboard Frontend integrata nella cartella static
@app.get("/", response_class=HTMLResponse)
def read_root():
    index_path = BASE_DIR / "static" / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return """
    <!DOCTYPE html>
    <html lang="it">
    <head><meta charset="UTF-8"><title>Preventivi Pro</title></head>
    <body>
        <h1>Benvenuto su Preventivi Pro</h1>
        <p>File index.html non trovato nella cartella static del progetto.</p>
    </body>
    </html>
    """


# Endpoint leggero di Health Check per il servizio Keep-Alive (UptimeRobot / Cron-Job.org)
@app.get("/health")
def health_check():
    return {"status": "online", "message": "Preventivi Pro è attivo e operativo!"}


@app.get("/api/user/me")
def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user


@app.post("/api/register")
def register_user(user: UserRegister, db: Session = Depends(get_db)):
    existing_user = (
        db.query(DBUser).filter(DBUser.username == user.username).first()
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="Username già registrato")

    hashed_pwd = get_password_hash(user.password)
    db_user = DBUser(
        username=user.username,
        password=hashed_pwd,
        professionista=user.professionista,
        partita_iva=user.partita_iva,
        recapito=user.recapito,
        email=user.email,
    )
    db.add(db_user)
    db.commit()
    return {"message": "Utente registrato con successo"}


@app.post("/api/login")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(DBUser).filter(DBUser.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username o password errati",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": form_data.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "professionista": user.professionista,
    }


@app.post("/api/calcola")
def calcola_e_salva_preventivo(
    dati: PreventivoRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    voci_extra_dicts = []
    for v in dati.voci_extra:
        if hasattr(v, "model_dump"):
            voci_extra_dicts.append(v.model_dump())
        else:
            voci_extra_dicts.append(v.dict())

    subtotale_lavorazione = dati.ore_lavoro * dati.costo_orario
    utile_stimato = subtotale_lavorazione * (
        (dati.margine_percentuale or 0.0) / 100.0
    )

    totale_voci_extra = sum(v["importo"] for v in voci_extra_dicts)
    subtotale_complessivo = (
        subtotale_lavorazione + utile_stimato + totale_voci_extra
    )

    sconto_valore = subtotale_complessivo * (
        (dati.sconto_percentuale or 0.0) / 100.0
    )
    totale_imponibile = subtotale_complessivo - sconto_valore

    iva = totale_imponibile * 0.22
    totale_finale = totale_imponibile + iva

    dettaglio_economico = {
        "subtotale_lavorazione": round(subtotale_lavorazione, 2),
        "utile_stimato": round(utile_stimato, 2),
        "voci_extra": voci_extra_dicts,
        "totale_voci_extra": round(totale_voci_extra, 2),
        "subtotale_complessivo": round(subtotale_complessivo, 2),
        "sconto_valore": round(sconto_valore, 2),
        "totale_imponibile": round(totale_imponibile, 2),
        "iva": round(iva, 2),
        "totale_finale": round(totale_finale, 2),
        "totale_complessivo_finale": round(totale_finale, 2),
    }

    db_preventivo = DBPreventivo(
        username=current_user["username"],
        cliente=dati.cliente,
        progetto=dati.progetto,
        data=dati.data,
        validita=dati.validita,
        ore_lavoro=dati.ore_lavoro,
        costo_orario=dati.costo_orario,
        sconto_percentuale=dati.sconto_percentuale,
        totale_finale=round(totale_finale, 2),
        dettaglio_json=json.dumps(dettaglio_economico),
    )
    db.add(db_preventivo)
    db.commit()
    db.refresh(db_preventivo)

    return {
        "id": db_preventivo.id,
        "cliente": dati.cliente,
        "progetto": dati.progetto,
        "dettaglio_economico": dettaglio_economico,
    }


@app.get("/api/preventivi")
def lista_preventivi(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(DBPreventivo)
        .filter(DBPreventivo.username == current_user["username"])
        .order_by(DBPreventivo.id.desc())
        .all()
    )

    preventivi = []
    for r in rows:
        preventivi.append(
            {
                "id": r.id,
                "cliente": r.cliente,
                "progetto": r.progetto,
                "data": r.data,
                "validita": r.validita,
                "ore_lavoro": r.ore_lavoro,
                "costo_orario": r.costo_orario,
                "sconto_percentuale": r.sconto_percentuale,
                "totale_finale": r.totale_finale,
                "dettaglio_json": json.loads(r.dettaglio_json)
                if r.dettaglio_json
                else {},
            }
        )
    return preventivi


@app.get("/api/preventivi/{preventivo_id}")
def dettaglio_preventivo(
    preventivo_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    r = (
        db.query(DBPreventivo)
        .filter(
            DBPreventivo.id == preventivo_id,
            DBPreventivo.username == current_user["username"],
        )
        .first()
    )

    if not r:
        raise HTTPException(
            status_code=404, detail="Preventivo non trovato o non autorizzato"
        )

    return {
        "id": r.id,
        "cliente": r.cliente,
        "progetto": r.progetto,
        "data": r.data,
        "validita": r.validita,
        "ore_lavoro": r.ore_lavoro,
        "costo_orario": r.costo_orario,
        "sconto_percentuale": r.sconto_percentuale,
        "totale_finale": r.totale_finale,
        "dettaglio_json": json.loads(r.dettaglio_json)
        if r.dettaglio_json
        else {},
    }


@app.delete("/api/preventivi/{preventivo_id}")
def elimina_preventivo(
    preventivo_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    r = (
        db.query(DBPreventivo)
        .filter(
            DBPreventivo.id == preventivo_id,
            DBPreventivo.username == current_user["username"],
        )
        .first()
    )

    if not r:
        raise HTTPException(
            status_code=404, detail="Preventivo non trovato o non autorizzato"
        )

    db.delete(r)
    db.commit()
    return {"message": "Preventivo eliminato con successo"}


# 3. Avvio dinamico di Uvicorn per la produzione
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)