from datetime import datetime, date, timezone
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator
from auction_app.db.models import RoleChoices, FuelType, Transmission, StatusCar


class UserRegistrationSchema(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    phone_number: Optional[str] = None
    role: RoleChoices = RoleChoices.buyer


class UserProfileSchema(BaseModel):
    id: int
    username: str
    email: EmailStr
    phone_number: Optional[str]
    role: RoleChoices
    date_registered: datetime


class CarWriteSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brand: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=40)
    year: date
    fuel_type: FuelType
    transmission: Transmission
    mileage: int = Field(ge=0)
    price: float = Field(gt=0)
    description: str = Field(min_length=1)
    image: str = Field(min_length=1)


class CarSchema(BaseModel):
    id: int
    brand: str
    model: str
    year: date
    fuel_type: FuelType
    transmission: Transmission
    mileage: int
    price: float
    description: str
    image: str
    seller_id: int


class AuctionWriteSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    car_id: int = Field(gt=0)
    start_price: int = Field(gt=0)
    min_price: Optional[int] = Field(default=None, ge=0)
    start_time: datetime
    end_time: datetime
    status: StatusCar = StatusCar.active

    @field_validator("start_time", "end_time")
    @classmethod
    def normalize_to_utc_naive(cls, value: datetime) -> datetime:
        # Database columns are timezone-naive and bidding compares UTC-naive
        # timestamps. Convert offset-aware values to UTC before persisting.
        # Existing timezone-naive clients are interpreted as UTC.
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    @model_validator(mode="after")
    def validate_time_window(self):
        if self.end_time <= self.start_time:
            raise ValueError("Auction end_time must be after start_time")
        return self


class AuctionSchema(BaseModel):
    id: int
    car_id: int
    start_price: int
    min_price: Optional[int]
    start_time: datetime
    end_time: datetime
    status: StatusCar


class BidCreateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auction_id: int = Field(gt=0)
    amount: int = Field(gt=0)

class BidSchema(BaseModel):
    id: int
    auction_id: int
    user_id: int
    amount: int
    date_registered: datetime


class FeedbackWriteSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seller_feedback_id: int = Field(gt=0)
    rating: int = Field(ge=1, le=5)
    text: str = Field(min_length=1, max_length=2000)


class FeedbackSchema(BaseModel):
    id: int
    seller_feedback_id: int
    bayer_id: int
    rating: int
    text: str
    create_date: datetime
