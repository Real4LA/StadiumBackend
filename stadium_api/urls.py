from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet,
    user_login,
    register_user,
    available_slots,
    book_slot,
    cancel_booking,
    my_bookings,
    request_password_reset,
    reset_password,
)

router = DefaultRouter()
router.register(r'users', UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/', user_login, name='user-login'),
    path('auth/register/', register_user, name='register'),
    path('auth/verify-code/', UserViewSet.as_view({'post': 'verify_code'}), name='verify-code'),
    path('auth/resend-code/', UserViewSet.as_view({'post': 'resend_code'}), name='resend-code'),
    path('auth/password-reset/', request_password_reset, name='request-password-reset'),
    path('auth/password-reset/confirm/', reset_password, name='reset-password'),
    path('calendar/available_slots/', available_slots, name='available-slots'),
    path('calendar/book_slot/', book_slot, name='book-slot'),
    path('calendar/cancel_booking/', cancel_booking, name='cancel-booking'),
    path('calendar/my_bookings/', my_bookings, name='my-bookings'),
]