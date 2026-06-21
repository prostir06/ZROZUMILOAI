"""URL routes for accounts app."""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AuthConfigView,
    ChangePasswordView,
    CurrentUserView,
    CustomTokenObtainPairView,
    RegisterView,
    UserDetailView,
    UserListCreateView,
)

urlpatterns = [
    path('config/', AuthConfigView.as_view(), name='auth_config'),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', CurrentUserView.as_view(), name='current_user'),
    path('me/change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('users/', UserListCreateView.as_view(), name='user_list_create'),
    path('users/<int:user_id>/', UserDetailView.as_view(), name='user_delete'),
]
