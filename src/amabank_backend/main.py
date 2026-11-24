from datetime import datetime
import random
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="AMABank API", version="1.0.0")

# Allow requests from Expo Go, Android APK, and Expo Web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Schemas 
class PhoneCheckRequest(BaseModel):
    phone: str


class RegisterRequest(BaseModel):
    firstName: str
    lastName: str
    fullName: Optional[str] = None
    phone: str
    email: str
    address: str
    idType: str
    idNumber: str
    passcode: str


class LoginRequest(BaseModel):
    phone: str
    passcode: str


class UserUpdateRequest(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    fullName: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    cardFrozen: Optional[bool] = None


class TransactionCreateRequest(BaseModel):
    userId: int = 1
    status: str = "Completed"
    recipient: str
    accountRef: Optional[str] = ""
    amount: float
    fee: float = 0.0
    total: Optional[float] = None
    note: Optional[str] = ""
    type: str  # "credit" or "debit"


class TransactionUpdateRequest(BaseModel):
    note: str


# In-Memory Data Store 
def generate_account_number() -> str:
    return f"9090 {random.randint(1000, 9999)} {random.randint(1000, 9999)}"


def generate_card_number() -> str:
    return f"4532 {random.randint(1000, 9999)} {random.randint(1000, 9999)} {random.randint(1000, 9999)}"


def generate_reference_no() -> str:
    stamp = datetime.now().strftime("%y%m%d%H%M")
    return f"REF{stamp}{random.randint(100, 999)}"


users_db = [
    {
        "id": 1,
        "firstName": "FJ",
        "lastName": "Nopuente",
        "fullName": "FJ Nopuente",
        "phone": "+639171234567",
        "email": "fj@amabank.ph",
        "address": "Cagayan de Oro City",
        "idType": "National ID (PhilSys)",
        "idNumber": "1234567890123456",
        "passcode": "123456",
        "balance": 0.0,
        "accountNumber": "9090 9123 4909",
        "code": "AMAPH-2029",
        "cardNumber": "4532 8910 3412 4909",
        "cardExpiry": "08/29",
        "cardCvv": "614",
        "cardFrozen": False,
        "kycVerified": True,
    }
]

transactions_db = []


# Health Check 
@app.get("/")
def root():
    return {"status": "online", "service": "AMABank FastAPI"}


# Auth & KYC Endpoints
@app.post("/auth/check-phone")
def check_phone(payload: PhoneCheckRequest):
    normalized = payload.phone.strip()
    exists = any(u["phone"] == normalized for u in users_db)
    if exists:
        raise HTTPException(status_code=400, detail="Mobile number is already registered.")
    return {"available": True, "phone": normalized}


@app.post("/auth/register")
def register_user(payload: RegisterRequest):
    normalized_phone = payload.phone.strip()
    if any(u["phone"] == normalized_phone for u in users_db):
        raise HTTPException(status_code=400, detail="Mobile number is already registered.")

    new_id = max((u["id"] for u in users_db), default=0) + 1
    full_name = payload.fullName or f"{payload.firstName.strip()} {payload.lastName.strip()}"

    new_user = {
        "id": new_id,
        "firstName": payload.firstName.strip(),
        "lastName": payload.lastName.strip(),
        "fullName": full_name,
        "phone": normalized_phone,
        "email": payload.email.strip(),
        "address": payload.address.strip(),
        "idType": payload.idType,
        "idNumber": payload.idNumber.strip(),
        "passcode": payload.passcode.strip(),
        "balance": 0.0,
        "accountNumber": generate_account_number(),
        "code": "AMAPH-2029",
        "cardNumber": generate_card_number(),
        "cardExpiry": "08/29",
        "cardCvv": str(random.randint(100, 999)),
        "cardFrozen": False,
        "kycVerified": True,
    }
    users_db.append(new_user)
    return new_user


@app.post("/auth/login")
def login_user(payload: LoginRequest):
    normalized_phone = payload.phone.strip()
    user = next((u for u in users_db if u["phone"] == normalized_phone), None)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found. Please register first.")
    if user["passcode"] != payload.passcode.strip():
        raise HTTPException(status_code=401, detail="Incorrect 6-digit MPIN.")
    return user


# User & Card Endpoints
@app.get("/users/{user_id}")
def get_user(user_id: int):
    user = next((u for u in users_db if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


@app.patch("/users/{user_id}")
def update_user(user_id: int, payload: UserUpdateRequest):
    user = next((u for u in users_db if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    updates = payload.model_dump(exclude_unset=True)
    user.update(updates)
    if "firstName" in updates or "lastName" in updates:
        user["fullName"] = f"{user['firstName']} {user['lastName']}".strip()
    return user


# Transactions CRUD Endpoints
@app.get("/transactions/{user_id}")
def get_transactions(user_id: int):
    user_txs = [tx for tx in transactions_db if tx["userId"] == user_id]
    return list(reversed(user_txs))


@app.post("/transactions")
def create_transaction(payload: TransactionCreateRequest):
    user = next((u for u in users_db if u["id"] == payload.userId), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    total_amount = payload.total if payload.total is not None else (payload.amount + payload.fee)

    if payload.type == "debit":
        if user["balance"] < total_amount:
            raise HTTPException(status_code=400, detail="Insufficient balance.")
        user["balance"] = round(user["balance"] - total_amount, 2)
    else:
        user["balance"] = round(user["balance"] + payload.amount, 2)

    new_id = max((tx["id"] for tx in transactions_db), default=0) + 1
    new_tx = {
        "id": new_id,
        "userId": payload.userId,
        "referenceNo": generate_reference_no(),
        "status": payload.status,
        "recipient": payload.recipient,
        "accountRef": payload.accountRef,
        "amount": payload.amount,
        "fee": payload.fee,
        "total": total_amount,
        "note": payload.note or "",
        "type": payload.type,
        "date": datetime.now().strftime("%b %d, %Y • %I:%M %p"),
    }
    transactions_db.append(new_tx)
    return new_tx


@app.patch("/transactions/{tx_id}")
def update_transaction(tx_id: int, payload: TransactionUpdateRequest):
    tx = next((t for t in transactions_db if t["id"] == tx_id), None)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    tx["note"] = payload.note
    return tx


@app.delete("/transactions/{tx_id}")
def delete_transaction(tx_id: int):
    global transactions_db
    tx = next((t for t in transactions_db if t["id"] == tx_id), None)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    transactions_db = [t for t in transactions_db if t["id"] != tx_id]
    return {"deleted": True, "id": tx_id}