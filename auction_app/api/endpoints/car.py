from typing import List

from fastapi import Depends, HTTPException, APIRouter
from auction_app.authentication import get_current_user
from auction_app.db.models import UserProfile
from sqlalchemy.orm import Session

from auction_app.db.database import SessionLocal
from auction_app.db.models import Car
from auction_app.db.schema import CarSchema

car_router = APIRouter(prefix='/car', tags=['Car'])



async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Create a new car
@car_router.post('/', response_model=CarSchema, summary='Создать машину')
async def create_car(car: CarSchema, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    if user.role.value != 'seller':
        raise HTTPException(status_code=403, detail='Seller role required')
    car_db = Car(
        brand=car.brand,
        model=car.model,
        year=car.year,
        fuel_type=car.fuel_type,
        transmission=car.transmission,
        mileage=car.mileage,
        price=car.price,
        description=car.description,
        image=car.image,
        seller_id=user.id
    )
    db.add(car_db)
    db.commit()
    db.refresh(car_db)
    return car_db


# Get all cars
@car_router.get('/', response_model=List[CarSchema], summary='Получить все машины')
async def car_list(db: Session = Depends(get_db)):
    return db.query(Car).all()


# Get a car by ID
@car_router.get('/{car_id}', response_model=CarSchema, summary='Получить машину по ID')
async def car_detail(car_id: int, db: Session = Depends(get_db)):
    car = db.query(Car).filter(Car.id == car_id).first()

    if car is None:
        raise HTTPException(status_code=404, detail='Машина не найдена')
    return car


# Update a car
@car_router.put('/{car_id}', response_model=CarSchema, summary='Обновить машину')
async def car_update(car_id: int, car: CarSchema, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    car_db = db.query(Car).filter(Car.id == car_id).first()

    if car_db is None:
        raise HTTPException(status_code=404, detail='Машина не найдена')

    if car_db.seller_id != user.id:
        raise HTTPException(status_code=403, detail='Not the owner of this car')

    car_db.brand = car.brand
    car_db.model = car.model
    car_db.year = car.year
    car_db.fuel_type = car.fuel_type
    car_db.transmission = car.transmission
    car_db.mileage = car.mileage
    car_db.price = car.price
    car_db.description = car.description
    car_db.image = car.image
    car_db.seller_id = user.id

    db.add(car_db)
    db.commit()
    db.refresh(car_db)
    return car_db


# Delete a car
@car_router.delete('/{car_id}', summary='Удалить машину')
async def car_delete(car_id: int, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    car_db = db.query(Car).filter(Car.id == car_id).first()

    if car_db is None:
        raise HTTPException(status_code=404, detail='Машина не найдена')

    if car_db.seller_id != user.id:
        raise HTTPException(status_code=403, detail='Not the owner of this car')
    db.delete(car_db)
    db.commit()
    return {'message': 'Машина удалена'}


# Search for cars by brand, model, and fuel type
@car_router.get('/search/', response_model=List[CarSchema], summary='Поиск машин')
async def search_car(brand: str = '', model: str = '', fuel_type: str = '', db: Session = Depends(get_db)):
    query = db.query(Car)

    # If brand is provided, filter by brand
    if brand:
        query = query.filter(Car.brand.ilike(f'%{brand}%'))

    # If model is provided, filter by model
    if model:
        query = query.filter(Car.model.ilike(f'%{model}%'))

    # If fuel_type is provided, filter by fuel type
    if fuel_type:
        query = query.filter(Car.fuel_type == fuel_type)

    cars = query.all()

    if not cars:
        raise HTTPException(status_code=404, detail='Машины не найдены')

    return cars
