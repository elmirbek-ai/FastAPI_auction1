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


class ReadOnlyAdmin:
    # Admin UI must not bypass API authorization, bid immutability or
    # auction history rules. Future admin mutations need audited workflows.
    can_create = False
    can_edit = False
    can_delete = False
    can_export = False
    can_import = False


class CarAdmin(ReadOnlyAdmin, ModelView, model=Car):
    column_list = [Car.id, Car.model]
    name = 'Car'
    name_plural = 'Cars'


class AuctionAdmin(ReadOnlyAdmin, ModelView, model=Auction):
    column_list = [Auction.id]
    name = 'Auction'
    name_plural = 'Auctions'


class BidAdmin(ReadOnlyAdmin, ModelView, model=Bid):
    column_list = [Bid.id, Bid.user]
    name = 'Bid'
    name_plural = 'Bids'


class FeedbackAdmin(ReadOnlyAdmin, ModelView, model=Feedback):
    column_list = [Feedback.id, Feedback.text]
    name = 'Feedback'
    name_plural = 'Feedbacks'
