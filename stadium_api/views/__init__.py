# This file makes the views directory a Python package 

from .user_views import UserViewSet, user_login
from .auth import register_user
from .calendar_views import available_slots, book_slot, cancel_booking, my_bookings

__all__ = [
    'UserViewSet',
    'user_login',
    'register_user',
    'available_slots',
    'book_slot',
    'cancel_booking',
    'my_bookings',
] 