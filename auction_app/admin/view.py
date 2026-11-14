from sqladmin import ModelView
from auction_app.db.models import UserProfile, Car, Auction, Bid, Feedback


class UserProfileAdmin(ModelView, model=UserProfile):
    # Read-only overview: never expose raw password hashes or allow account
    # credentials/roles to be overwritten through automatically generated forms.
    column_list = [UserProfile.id, UserProfile.username]
    column_details_list = [UserProfile.id, UserProfile.username]
    can_create = False
    can_edit = False
    can_delete = False
    can_export = False
    can_import = False
    name = 'User'
    name_plural = 'Users'


class CarAdmin(ModelView, model=Car):
    column_list = [Car.id, Car.model] 
    name = 'Car'
    name_plural = 'Car'


class AuctionAdmin(ModelView, model=Auction):
    column_list = [Auction.id]
    name = 'Auction'
    name_plural = 'Auction'


class BidAdmin(ModelView, model=Bid): 
    column_list = [Bid.id, Bid.user]
    name = 'Bid'
    name_plural = 'Bid'


class FeedbackAdmin(ModelView, model=Feedback):
    column_list = [Feedback.id, Feedback.text]
    name = 'Feedback'
    name_plural = 'Feedback'
