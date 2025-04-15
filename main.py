from fastapi import FastAPI, HTTPException, Depends  # FastAPI core components
from pydantic import BaseModel, EmailStr, Field  # For data validation and parsing
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # Async engine and session from SQLAlchemy
from sqlalchemy.ext.declarative import declarative_base  # Base class for SQLAlchemy models
from sqlalchemy.orm import sessionmaker, declarative_base  # ORM tools
from sqlalchemy import Column, Integer, String, select  # Column types and SQL expressions
import re  # Regular expressions module

# ------------------- FastAPI Initialization -------------------
app = FastAPI()  # Initialize FastAPI app instance

# ------------------- Database Configuration -------------------
DATABASE_URL = "mysql+aiomysql://root:Prema$1998@localhost/student_management"  # Async MySQL DB URL

engine = create_async_engine(DATABASE_URL, echo=True)  # Create async engine

# Create an async session class
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Base class for ORM models
Base = declarative_base()

# Dependency to get async DB session
async def get_db():  # Dependency function to yield a DB session
    async with AsyncSessionLocal() as session:  # Context manager to open and close session
        yield session

# ------------------- Database Models -------------------

# Student model class
class Student(Base):
    __tablename__ = "students"  # Name of the table

    id = Column(Integer, primary_key=True, index=True)  # Primary key column
    name = Column(String(50), nullable=False)  # Name column
    age = Column(Integer, nullable=False)  # Age column
    address = Column(String(255), nullable=False)  # Address column
    email = Column(String(100), nullable=False, unique=True)  # Unique email column
    subject = Column(String(100), nullable=False)  # Subject column
    semester = Column(Integer, nullable=False)  # Semester column

# User model class
class User(Base):
    __tablename__ = "users"  # Table name for users

    id = Column(Integer, primary_key=True, index=True)  # Primary key
    username = Column(String(50), unique=True, nullable=False)  # Unique username
    password = Column(String(255), nullable=False)  # Password (should be hashed in real apps)

# ------------------- Pydantic Schemas -------------------

# Schema for user creation
class UserCreate(BaseModel):
    username: str  # Username
    password: str  # Password

# Schema to return user data
class UserOut(BaseModel):
    id: int  # ID
    username: str  # Username

    class Config:
        orm_mode = True  # Allow ORM objects to be returned

# Schema for student creation
class StudentCreate(BaseModel):
    name: str  # Name
    age: int = Field(..., ge=18, le=30)  # Age must be between 18-30
    address: str  # Address
    email: EmailStr  # Valid email address
    subject: str  # Subject
    semester: int = Field(..., ge=1, le=8)  # Semester must be between 1-8

# Schema to return student data
class StudentOut(BaseModel):
    id: int  # ID
    name: str  # Name
    age: int  # Age
    address: str  # Address
    email: str  # Email
    subject: str  # Subject
    semester: int  # Semester

    class Config:
        orm_mode = True  # Enable ORM mode for model conversion

# ------------------- Utility Functions -------------------

def validate_password(password: str):  # Validate password strength
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r'\d', password):
        return "Password must contain at least one digit."
    if not re.search(r'[A-Z]', password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r'[a-z]', password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r'[\W_]', password):
        return "Password must contain at least one special character."
    return None  # Return None if valid

# ------------------- API Endpoints -------------------

@app.post("/register", response_model=UserOut)
async def register_user(user: UserCreate, db: AsyncSession = Depends(get_db)):  # Register endpoint
    result = await db.execute(select(User).where(User.username == user.username))  # Query for username
    existing_user = result.scalar_one_or_none()  # Get existing user
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken.")  # Username exists

    password_error = validate_password(user.password)  # Validate password
    if password_error:
        raise HTTPException(status_code=400, detail=password_error)  # Raise error

    new_user = User(username=user.username, password=user.password)  # Create new user
    db.add(new_user)  # Add user to session
    await db.commit()  # Commit changes
    await db.refresh(new_user)  # Refresh instance
    return new_user  # Return new user

@app.post("/login")
async def login_user(user: UserCreate, db: AsyncSession = Depends(get_db)):  # Login endpoint
    result = await db.execute(select(User).where(User.username == user.username))  # Query username
    db_user = result.scalar_one_or_none()  # Get result
    if not db_user or db_user.password != user.password:
        raise HTTPException(status_code=401, detail="Invalid username or password.")  # Invalid credentials
    return {"message": "Login successful."}  # Success message

@app.post("/students", response_model=StudentOut)
async def add_student(student: StudentCreate, db: AsyncSession = Depends(get_db)):  # Add student
    result = await db.execute(select(Student).where(Student.email == student.email))  # Check email
    existing = result.scalar_one_or_none()  # Get existing student
    if existing:
        raise HTTPException(status_code=400, detail="Email already in use.")  # Email exists

    new_student = Student(**student.dict())  # Create new student
    db.add(new_student)  # Add to session
    await db.commit()  # Commit changes
    await db.refresh(new_student)  # Refresh instance
    return new_student  # Return student

@app.get("/students", response_model=list[StudentOut])
async def get_all_students(db: AsyncSession = Depends(get_db)):  # Get all students
    result = await db.execute(select(Student))  # Query all students
    students = result.scalars().all()  # Fetch all
    return students  # Return students

@app.get("/students/{student_id}", response_model=StudentOut)
async def get_student(student_id: int, db: AsyncSession = Depends(get_db)):  # Get student by ID
    result = await db.execute(select(Student).where(Student.id == student_id))  # Query student
    student = result.scalar_one_or_none()  # Fetch result
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")  # Not found
    return student  # Return student

@app.put("/students/{student_id}", response_model=StudentOut)
async def update_student(student_id: int, updated: StudentCreate, db: AsyncSession = Depends(get_db)):  # Update student
    result = await db.execute(select(Student).where(Student.id == student_id))  # Query student
    student = result.scalar_one_or_none()  # Fetch student
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")  # Not found

    for key, value in updated.dict().items():
        setattr(student, key, value)  # Update fields

    await db.commit()  # Commit changes
    await db.refresh(student)  # Refresh
    return student  # Return student

@app.delete("/students/{student_id}")
async def delete_student(student_id: int, db: AsyncSession = Depends(get_db)):  # Delete student
    result = await db.execute(select(Student).where(Student.id == student_id))  # Query student
    student = result.scalar_one_or_none()  # Fetch
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")  # Not found

    await db.delete(student)  # Delete
    await db.commit()  # Commit
    return {"message": "Student deleted successfully"}  # Success message 