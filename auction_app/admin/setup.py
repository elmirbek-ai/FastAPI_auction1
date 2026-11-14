"""SQLAdmin is opt-in and always requires an authentication backend."""
from auction_app.admin.auth import admin_from_environment


def setup_admin(app):
    backend = admin_from_environment()
    if backend is None:
        return None

    from sqladmin import Admin
    from auction_app.admin.view import (
        UserProfileAdmin, CarAdmin, AuctionAdmin, BidAdmin, FeedbackAdmin
    )
    from auction_app.db.database import engine

    admin = Admin(app, engine, authentication_backend=backend)
    for view in (UserProfileAdmin, CarAdmin, AuctionAdmin, BidAdmin, FeedbackAdmin):
        admin.add_view(view)
    return admin
