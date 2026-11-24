from datetime import datetime
import random
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="AMABank API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-Memory Database ---
users = [
    {
        "id": 1,
        "firstName": "FJ",
        "fullName": "Fvienj Bennet Nopuente",
        "email": "fj.nopuente@amabank.ph",
        "address": "Puntod, Cagayan de Oro City",
        "idType": "National ID",
        "idNumber": "4829-1039-5821-0094",
        "tier": "Verified Account",
        "accountNumber": "9090 9123 4909",
        "code": "AMAPH-2029",
        "phone": "9171233387",
        "maskedPhone": "+63********3387",
        "passcode": "123456",
        "balance": 0.0,
        "cardNumber": "4532 8910 3412 4909",
        "cardExpiry": "08/29",
        "cardCvv": "614",
        "cardFrozen": False,
    }
]

transactions = []

next_user_id = 2


# --- Pydantic Schemas ---
class PhoneCheckRequest(BaseModel):
    phone: str


class RegisterRequest(BaseModel):
    fullName: str
    email: str
    address: str
    idType: str
    idNumber: str
    phone: str
    passcode: str


class LoginRequest(BaseModel):
    phone: str


class PasscodeRequest(BaseModel):
    userId: int
    passcode: str


class UserUpdateRequest(BaseModel):
    fullName: str | None = None
    firstName: str | None = None
    email: str | None = None
    address: str | None = None
    passcode: str | None = None
    cardFrozen: bool | None = None


class TransactionCreate(BaseModel):
    id: str | None = None
    userId: int
    status: str
    recipient: str
    accountRef: str = ""
    amount: float
    fee: float = 0.0
    total: float | None = None
    note: str = ""
    type: str  # "debit" or "credit"


class NoteUpdate(BaseModel):
    note: str


# --- Auth & KYC Endpoints ---
@app.post("/auth/check-phone")
def checkPhone(data: PhoneCheckRequest):
    if len(data.phone) != 10 or not data.phone.isdigit():
        raise HTTPException(status_code=400, detail="Enter a valid 10-digit mobile number")

    for user in users:
        if user["phone"] == data.phone:
            raise HTTPException(status_code=400, detail="Mobile number is already registered")

    return {"available": True, "otpRef": "PA6Q"}


@app.post("/auth/register")
def registerUser(data: RegisterRequest):
    global next_user_id

    for user in users:
        if user["phone"] == data.phone:
            raise HTTPException(status_code=400, detail="Phone number already registered")

    first_name = data.fullName.strip().split(" ")[0]
    last4 = str(random.randint(1000, 9999))
    acct_num = f"9090 {random.randint(1000, 9999)} {last4}"
    card_num = f"4532 {random.randint(1000, 9999)} {random.randint(1000, 9999)} {last4}"

    new_user = {
        "id": next_user_id,
        "firstName": first_name,
        "fullName": data.fullName.strip(),
        "email": data.email.strip(),
        "address": data.address.strip(),
        "idType": data.idType,
        "idNumber": data.idNumber.strip(),
        "tier": "Verified Account",
        "accountNumber": acct_num,
        "code": "AMAPH-2029",
        "phone": data.phone,
        "maskedPhone": f"+63********{data.phone[-4:]}",
        "passcode": data.passcode,
        "balance": 0.0,
        "cardNumber": card_num,
        "cardExpiry": "08/29",
        "cardCvv": str(random.randint(100, 999)),
        "cardFrozen": False,
    }
    users.append(new_user)
    next_user_id += 1

    return {"message": "KYC verified and account created", "user": new_user}


@app.post("/auth/login")
def loginUser(data: LoginRequest):
    for user in users:
        if user["phone"] == data.phone:
            return {"message": "OTP sent", "user": user, "otpRef": "PA6Q"}

    raise HTTPException(
        status_code=404,
        detail="Account not found. Please register first.",
    )


@app.post("/auth/verify-passcode")
def verifyPasscode(data: PasscodeRequest):
    for user in users:
        if user["id"] == data.userId:
            if user["passcode"] != data.passcode:
                raise HTTPException(status_code=401, detail="Incorrect MPIN")
            return {"verified": True, "user": user}
    raise HTTPException(status_code=404, detail="User not found")


# --- User & Balance Endpoints ---
@app.get("/users")
def getUsers():
    return users


@app.get("/users/{user_id}")
def getUser(user_id: int):
    for user in users:
        if user["id"] == user_id:
            return user
    raise HTTPException(status_code=404, detail="User not found")


@app.patch("/users/{user_id}")
def updateUser(user_id: int, data: UserUpdateRequest):
    for user in users:
        if user["id"] == user_id:
            if data.fullName is not None:
                user["fullName"] = data.fullName
            if data.firstName is not None:
                user["firstName"] = data.firstName
            if data.email is not None:
                user["email"] = data.email
            if data.address is not None:
                user["address"] = data.address
            if data.passcode is not None:
                user["passcode"] = data.passcode
            if data.cardFrozen is not None:
                user["cardFrozen"] = data.cardFrozen
            return user
    raise HTTPException(status_code=404, detail="User not found")


# --- Transactions CRUD Endpoints ---
@app.get("/transactions/{user_id}")
def getTransactions(user_id: int):
    return [tx for tx in transactions if tx["userId"] == user_id]


@app.post("/transactions")
def createTransaction(data: TransactionCreate):
    target_user = None
    for user in users:
        if user["id"] == data.userId:
            target_user = user
            break

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    deduction = data.total if data.total is not None else data.amount

    if data.type == "debit":
        if deduction > target_user["balance"]:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        target_user["balance"] -= deduction
    else:
        target_user["balance"] += data.amount

    now_str = datetime.now().strftime("%B %d, %Y at %H:%M:%S")
    new_tx = {
        "id": data.id or str(int(datetime.now().timestamp() * 1000)),
        "userId": data.userId,
        "status": data.status,
        "recipient": data.recipient,
        "accountRef": data.accountRef,
        "from": target_user["fullName"],
        "bank": "AMABank",
        "amount": data.amount,
        "fee": data.fee,
        "total": deduction,
        "note": data.note,
        "referenceNo": f"REF{random.randint(100000000000, 999999999999)}",
        "date": now_str,
        "type": data.type,
    }
    transactions.insert(0, new_tx)

    return {"transaction": new_tx, "balance": target_user["balance"]}


@app.patch("/transactions/{tx_id}")
def updateTransactionNote(tx_id: str, data: NoteUpdate):
    for tx in transactions:
        if str(tx["id"]) == str(tx_id):
            tx["note"] = data.note
            return tx
    raise HTTPException(status_code=404, detail="Transaction not found")


@app.delete("/transactions/{tx_id}")
def deleteTransaction(tx_id: str):
    for index, tx in enumerate(transactions):
        if str(tx["id"]) == str(tx_id):
            deleted = transactions.pop(index)
            return {"message": "Successfully deleted", "data": deleted}
    raise HTTPException(status_code=404, detail="Transaction not found")
