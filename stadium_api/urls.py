from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet,
    user_login,
    register_user,
    available_slots,
    book_slot,
    cancel_booking,
)

router = DefaultRouter()
router.register(r'users', UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/', user_login, name='user-login'),
    path('auth/register/', register_user, name='register'),
    path('calendar/available_slots/', available_slots, name='available-slots'),
    path('calendar/book_slot/', book_slot, name='book-slot'),
    path('calendar/cancel_booking/', cancel_booking, name='cancel-booking'),
]