"""
FastAPI Backend for UK Grocery Compare
Handles user authentication and shopping list management
"""
import os
import csv
import jwt
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel, EmailStr

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/grocery_db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


# Database Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    shopping_lists = relationship("ShoppingList", back_populates="user", cascade="all, delete-orphan")


class ShoppingList(Base):
    __tablename__ = "shopping_lists"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="shopping_lists")
    items = relationship("ListItem", back_populates="shopping_list", cascade="all, delete-orphan")


class ListItem(Base):
    __tablename__ = "list_items"
    id = Column(Integer, primary_key=True, index=True)
    list_id = Column(Integer, ForeignKey("shopping_lists.id"), nullable=False)
    item_name = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    shopping_list = relationship("ShoppingList", back_populates="items")


class Price(Base):
    __tablename__ = "prices"
    id = Column(Integer, primary_key=True, index=True)
    item = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False)
    unit = Column(String, nullable=False)
    store = Column(String, nullable=False, index=True)
    price_per_unit_gbp = Column(Float, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)


# Create tables
Base.metadata.create_all(bind=engine)


# Pydantic models
class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class ListItemCreate(BaseModel):
    item_name: str
    quantity: float


class ShoppingListCreate(BaseModel):
    name: str
    items: List[ListItemCreate] = []


class ShoppingListUpdate(BaseModel):
    name: Optional[str] = None
    items: Optional[List[ListItemCreate]] = None


class ListItemResponse(BaseModel):
    id: int
    item_name: str
    quantity: float
    class Config:
        from_attributes = True


class ShoppingListResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    items: List[ListItemResponse]
    class Config:
        from_attributes = True


class PriceResponse(BaseModel):
    item: str
    category: str
    unit: str
    store: str
    price_per_unit_gbp: float
    last_updated: datetime
    notes: Optional[str] = None
    class Config:
        from_attributes = True


# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Auth helpers
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(email: str = Depends(verify_token), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# Create FastAPI app
app = FastAPI(title="UK Grocery Compare API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Load prices from CSV on startup
@app.on_event("startup")
def load_prices():
    db = SessionLocal()
    try:
        # Check if prices already loaded
        if db.query(Price).count() > 0:
            return
        
        csv_path = os.path.join(os.path.dirname(__file__), "uk_grocery_prices.csv")
        if not os.path.exists(csv_path):
            return
        
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                price = Price(
                    item=row["item"],
                    category=row["category"],
                    unit=row["unit"],
                    store=row["store"],
                    price_per_unit_gbp=float(row["price_per_unit_gbp"]),
                    notes=row.get("notes", "")
                )
                db.add(price)
            db.commit()
            print(f"Loaded prices from CSV")
    except Exception as e:
        print(f"Error loading prices: {e}")
    finally:
        db.close()


# API Routes
@app.post("/auth/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    db_user = User(email=user.email, hashed_password=pwd_context.hash(user.password))
    db.add(db_user)
    db.commit()
    return {"access_token": create_access_token({"sub": user.email}), "token_type": "bearer"}


@app.post("/auth/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not pwd_context.verify(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return {"access_token": create_access_token({"sub": user.email}), "token_type": "bearer"}


@app.get("/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email}


@app.get("/lists", response_model=List[ShoppingListResponse])
def get_lists(current_user: User = Depends(get_current_user)):
    return current_user.shopping_lists


@app.post("/lists", response_model=ShoppingListResponse, status_code=status.HTTP_201_CREATED)
def create_list(list_data: ShoppingListCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    shopping_list = ShoppingList(name=list_data.name, user_id=current_user.id)
    db.add(shopping_list)
    db.commit()
    db.refresh(shopping_list)
    for item in list_data.items:
        db.add(ListItem(list_id=shopping_list.id, item_name=item.item_name, quantity=item.quantity))
    db.commit()
    db.refresh(shopping_list)
    return shopping_list


@app.get("/lists/{list_id}", response_model=ShoppingListResponse)
def get_list(list_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lst = db.query(ShoppingList).filter(ShoppingList.id == list_id, ShoppingList.user_id == current_user.id).first()
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")
    return lst


@app.delete("/lists/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_list(list_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lst = db.query(ShoppingList).filter(ShoppingList.id == list_id, ShoppingList.user_id == current_user.id).first()
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")
    db.delete(lst)
    db.commit()


@app.get("/prices", response_model=List[PriceResponse])
def get_prices(db: Session = Depends(get_db)):
    return db.query(Price).all()


@app.get("/prices/items")
def get_items(db: Session = Depends(get_db)):
    results = db.query(Price.item, Price.category, Price.unit).distinct().all()
    return [{"item": r[0], "category": r[1], "unit": r[2]} for r in results]


@app.get("/prices/stores")
def get_stores(db: Session = Depends(get_db)):
    return [r[0] for r in db.query(Price.store).distinct().all()]


# Serve frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_frontend():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)