"""Views for authentication and user management."""
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    AdminCreateUserSerializer,
    AdminUpdateUserSerializer,
    ChangePasswordSerializer,
    RegisterSerializer,
    UserCreateResponseSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """Public user registration."""

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = (permissions.AllowAny,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        data = UserCreateResponseSerializer(user).data
        data['api_key'] = user._created_api_key
        return Response(data, status=status.HTTP_201_CREATED)


class CurrentUserView(APIView):
    """Return authenticated user profile."""

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class ChangePasswordView(APIView):
    """Change password for the current user."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Пароль змінено'})


class UserListCreateView(generics.ListCreateAPIView):
    """List users or create new user (admin only)."""

    queryset = User.objects.select_related('api_key').all().order_by('username')
    permission_classes = (permissions.IsAdminUser,)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AdminCreateUserSerializer
        return UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        data = UserCreateResponseSerializer(user).data
        data['api_key'] = user._created_api_key
        return Response(data, status=status.HTTP_201_CREATED)


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update or delete user (admin only)."""

    queryset = User.objects.select_related('api_key').all()
    permission_classes = (permissions.IsAdminUser,)
    lookup_url_kwarg = 'user_id'

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return AdminUpdateUserSerializer
        return UserSerializer

    def perform_update(self, serializer):
        instance = serializer.instance
        new_is_staff = serializer.validated_data.get('is_staff')

        if instance.pk == self.request.user.pk and new_is_staff is False:
            raise ValidationError(
                'Не можна зняти права адміністратора з власного облікового запису',
            )

        if instance.is_superuser and new_is_staff is False:
            superusers_count = User.objects.filter(is_superuser=True).count()
            if superusers_count <= 1:
                raise ValidationError(
                    'Не можна зняти права останнього суперкористувача',
                )

        serializer.save()

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise ValidationError('Не можна видалити власний обліковий запис')

        if instance.is_superuser:
            superusers_count = User.objects.filter(is_superuser=True).count()
            if superusers_count <= 1:
                raise ValidationError('Не можна видалити останнього суперкористувача')

        instance.delete()


class CustomTokenObtainPairView(TokenObtainPairView):
    """JWT login with user info in response."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            username = request.data.get('username')
            try:
                user = User.objects.select_related('api_key').get(username=username)
                response.data['user'] = UserSerializer(user).data
            except User.DoesNotExist:
                pass
        return response
