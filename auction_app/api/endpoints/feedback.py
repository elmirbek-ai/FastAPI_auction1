from typing import List
from fastapi import Depends, HTTPException, APIRouter
from auction_app.authentication import get_current_user
from auction_app.db.models import UserProfile
from sqlalchemy.orm import Session
from auction_app.db.database import SessionLocal
from auction_app.db.models import Feedback
from auction_app.db.schema import FeedbackSchema

feedback_router = APIRouter(prefix='/feedback', tags=['Feedback'])

# Dependency to get the DB session
async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create a new feedback
@feedback_router.post('/', response_model=FeedbackSchema, summary='Создать отзыв')
async def create_feedback(feedback: FeedbackSchema, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    feedback_db = Feedback(
        seller_feedback_id=feedback.seller_feedback_id,
        bayer_id=user.id,
        rating=feedback.rating,
        text=feedback.text,
        create_date=feedback.create_date
    )
    db.add(feedback_db)
    db.commit()
    db.refresh(feedback_db)
    return feedback_db

# Get all feedback for a seller
@feedback_router.get('/seller/{seller_id}', response_model=List[FeedbackSchema], summary='Получить все отзывы для продавца')
async def feedback_list(seller_id: int, db: Session = Depends(get_db)):
    return db.query(Feedback).filter(Feedback.seller_feedback_id == seller_id).all()

# Get feedback by ID
@feedback_router.get('/{feedback_id}', response_model=FeedbackSchema, summary='Получить отзыв по ID')
async def feedback_detail(feedback_id: int, db: Session = Depends(get_db)):
    feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()

    if feedback is None:
        raise HTTPException(status_code=404, detail='Отзыв не найден')
    return feedback

# Delete a feedback
@feedback_router.delete('/{feedback_id}', summary='Удалить отзыв')
async def feedback_delete(feedback_id: int, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    feedback_db = db.query(Feedback).filter(Feedback.id == feedback_id).first()

    if feedback_db is None:
        raise HTTPException(status_code=404, detail='Отзыв не найден')

    if feedback_db.bayer_id != user.id:
        raise HTTPException(status_code=403, detail='Not the owner of this feedback')
    db.delete(feedback_db)
    db.commit()
    return {'message': 'Отзыв удален'}
