from typing import List
from datetime import datetime, timezone
from sqlalchemy import func
from fastapi import Depends, HTTPException, APIRouter
from auction_app.authentication import get_current_user
from auction_app.db.models import UserProfile
from sqlalchemy.orm import Session
from auction_app.db.database import SessionLocal
from auction_app.db.models import Bid, Auction, StatusCar
from auction_app.db.schema import BidSchema, BidCreateSchema

bid_router = APIRouter(prefix='/bid', tags=['Bid'])

# Dependency to get the DB session
async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create a new bid
@bid_router.post('/', response_model=BidSchema, summary='Создать ставку')
async def create_bid(
    bid: BidCreateSchema,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    # Lock the parent auction so concurrent bidders cannot both pass the
    # highest-bid check against the same earlier maximum on PostgreSQL.
    auction = (
        db.query(Auction)
        .filter(Auction.id == bid.auction_id)
        .with_for_update()
        .first()
    )
    if auction is None:
        raise HTTPException(status_code=404, detail='Auction not found')
    if auction.car.seller_id == user.id:
        raise HTTPException(status_code=403, detail='Seller cannot bid on own auction')
    if user.role.value != 'buyer':
        raise HTTPException(status_code=403, detail='Buyer role required')
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if (
        auction.status != StatusCar.active
        or auction.start_time > now
        or auction.end_time <= now
    ):
        raise HTTPException(status_code=409, detail='Auction is not open for bidding')

    highest = db.query(func.max(Bid.amount)).filter(
        Bid.auction_id == auction.id
    ).scalar()
    minimum = max(auction.start_price, highest or 0)
    if bid.amount <= minimum:
        raise HTTPException(
            status_code=409,
            detail='Bid must be greater than start price and current highest bid',
        )

    bid_db = Bid(auction_id=auction.id, user_id=user.id, amount=bid.amount)
    db.add(bid_db)
    db.commit()
    db.refresh(bid_db)
    return bid_db


# Get all bids for an auction
@bid_router.get('/auction/{auction_id}', response_model=List[BidSchema], summary='Получить все ставки для аукциона')
async def bid_list(auction_id: int, db: Session = Depends(get_db)):
    return db.query(Bid).filter(Bid.auction_id == auction_id).all()

# Get a bid by ID
@bid_router.get('/{bid_id}', response_model=BidSchema, summary='Получить ставку по ID')
async def bid_detail(bid_id: int, db: Session = Depends(get_db)):
    bid = db.query(Bid).filter(Bid.id == bid_id).first()

    if bid is None:
        raise HTTPException(status_code=404, detail='Ставка не найдена')
    return bid

# Delete a bid
@bid_router.delete('/{bid_id}', summary='Удалить ставку')
async def bid_delete(bid_id: int, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    bid_db = db.query(Bid).filter(Bid.id == bid_id).first()

    if bid_db is None:
        raise HTTPException(status_code=404, detail='Ставка не найдена')

    if bid_db.user_id != user.id:
        raise HTTPException(status_code=403, detail='Not the owner of this bid')
    # An accepted bid is part of the auction audit trail. Withdrawal requires
    # a separately designed cancellation procedure, not destructive DELETE.
    raise HTTPException(
        status_code=409,
        detail='Placed bids cannot be deleted',
    )
