from typing import List
from fastapi import Depends, HTTPException, APIRouter
from auction_app.authentication import get_current_user
from auction_app.db.models import UserProfile
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from auction_app.db.database import SessionLocal
from auction_app.db.models import Auction, Car, Bid
from auction_app.db.schema import AuctionSchema, AuctionWriteSchema

auction_router = APIRouter(prefix='/auction', tags=['Auction'])

# Dependency to get the DB session
async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create a new auction
@auction_router.post('/', response_model=AuctionSchema, summary='Создать аукцион')
async def create_auction(auction: AuctionWriteSchema, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    car = db.query(Car).filter(Car.id == auction.car_id).with_for_update().first()
    if car is None:
        raise HTTPException(status_code=404, detail='Car not found')
    if car.seller_id != user.id:
        raise HTTPException(status_code=403, detail='Not the owner of this car')
    if auction.start_price <= 0 or auction.end_time <= auction.start_time:
        raise HTTPException(status_code=422, detail='Invalid auction price or time range')
    if db.query(Auction.id).filter(Auction.car_id == auction.car_id).first():
        raise HTTPException(status_code=409, detail='Car already has an auction')
    auction_db = Auction(
        car_id=auction.car_id,
        start_price=auction.start_price,
        min_price=auction.min_price,
        start_time=auction.start_time,
        end_time=auction.end_time,
        status=auction.status
    )
    try:
        db.add(auction_db)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail='Car already has an auction'
        ) from exc
    db.refresh(auction_db)
    return auction_db

# Get all auctions
@auction_router.get('/', response_model=List[AuctionSchema], summary='Получить все аукционы')
async def auction_list(db: Session = Depends(get_db)):
    return db.query(Auction).all()

# Get an auction by ID
@auction_router.get('/{auction_id}', response_model=AuctionSchema, summary='Получить аукцион по ID')
async def auction_detail(auction_id: int, db: Session = Depends(get_db)):
    auction = db.query(Auction).filter(Auction.id == auction_id).first()

    if auction is None:
        raise HTTPException(status_code=404, detail='Аукцион не найден')
    return auction

# Update an auction
@auction_router.put('/{auction_id}', response_model=AuctionSchema, summary='Обновить аукцион')
async def auction_update(auction_id: int, auction: AuctionWriteSchema, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    auction_db = db.query(Auction).filter(Auction.id == auction_id).with_for_update().first()

    if auction_db is None:
        raise HTTPException(status_code=404, detail='Аукцион не найден')

    if auction_db.car.seller_id != user.id:
        raise HTTPException(status_code=403, detail='Not the owner of this auction')
    new_car = db.query(Car).filter(Car.id == auction.car_id).first()
    if new_car is None:
        raise HTTPException(status_code=404, detail='Car not found')
    if new_car.seller_id != user.id:
        raise HTTPException(status_code=403, detail='Not the owner of the new car')
    if db.query(Bid.id).filter(Bid.auction_id == auction_db.id).first():
        raise HTTPException(
            status_code=409, detail='Cannot alter an auction after bids are placed'
        )
    if auction.start_price <= 0 or auction.end_time <= auction.start_time:
        raise HTTPException(status_code=422, detail='Invalid auction price or time range')
    if auction.car_id != auction_db.car_id and db.query(Auction.id).filter(
        Auction.car_id == auction.car_id
    ).first():
        raise HTTPException(status_code=409, detail='Car already has an auction')
    auction_db.car_id = auction.car_id
    auction_db.start_price = auction.start_price
    auction_db.min_price = auction.min_price
    auction_db.start_time = auction.start_time
    auction_db.end_time = auction.end_time
    auction_db.status = auction.status

    try:
        db.add(auction_db)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail='Car already has an auction'
        ) from exc
    db.refresh(auction_db)
    return auction_db

# Delete an auction
@auction_router.delete('/{auction_id}', summary='Удалить аукцион')
async def auction_delete(auction_id: int, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    auction_db = db.query(Auction).filter(Auction.id == auction_id).with_for_update().first()

    if auction_db is None:
        raise HTTPException(status_code=404, detail='Аукцион не найден')

    if auction_db.car.seller_id != user.id:
        raise HTTPException(status_code=403, detail='Not the owner of this auction')
    if db.query(Bid.id).filter(Bid.auction_id == auction_db.id).first():
        raise HTTPException(
            status_code=409, detail='Auction with accepted bids cannot be deleted'
        )
    db.delete(auction_db)
    db.commit()
    return {'message': 'Аукцион удален'}
