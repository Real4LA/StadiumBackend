from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    UserViewSet,
    user_login,
    CalendarAPIView,
    register_user,
    token_obtain_pair,
    get_user_info
)

router = DefaultRouter()
router.register(r'users', UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('login/', user_login, name='user-login'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Calendar endpoints
    path('calendar/', CalendarAPIView.as_view(), name='calendar'),
    path('calendar/available_slots/', CalendarAPIView.as_view(), name='available_slots'),
    path('calendar/book/', CalendarAPIView.as_view(), name='book_slot'),
    path('calendar/my-bookings/', CalendarAPIView.as_view(), name='my_bookings'),
    path('users/', register_user, name='register'),
    path('users/me/', get_user_info, name='user_info'),
] 