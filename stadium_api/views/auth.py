from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from ..serializers import UserSerializer
from django.contrib.auth.models import User
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
import random
import string
import logging

logger = logging.getLogger(__name__)

def generate_reset_code():
    """Generate a 6-digit reset code."""
    return ''.join(random.choices(string.digits, k=6))

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    try:
        with transaction.atomic():
            serializer = UserSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
            
    except serializers.ValidationError as e:
        return Response({
            'errors': e.detail
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Unexpected error during registration")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def token_obtain_pair(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(username=username, password=password)
    
    if user is not None:
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        })
    else:
        return Response(
            {'error': 'Invalid credentials'}, 
            status=status.HTTP_401_UNAUTHORIZED
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_info(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    """Request a password reset code."""
    try:
        email = request.data.get('email')
        if not email:
            return Response(
                {'error': 'Email is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(email=email).first()
        if not user:
            # Return success even if user not found to prevent email enumeration
            return Response({'message': 'If an account exists with this email, a reset code will be sent.'})

        # Generate and save reset code
        reset_code = generate_reset_code()
        user.profile.verification_code = reset_code
        user.profile.save()

        # Send reset code email
        subject = 'Password Reset Code - Tottenham Stadium'
        message = f'''Hello {user.first_name or user.username},

You have requested to reset your password. Here is your password reset code:

{reset_code}

If you did not request this reset, please ignore this email.

Best regards,
Tottenham Stadium Team'''

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            logger.info(f"Password reset code sent to {email}")
            return Response({'message': 'Reset code sent successfully'})
        except Exception as e:
            logger.error(f"Failed to send password reset code: {str(e)}")
            return Response(
                {'error': 'Failed to send reset code'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except Exception as e:
        logger.error(f"Password reset request error: {str(e)}")
        return Response(
            {'error': 'An error occurred'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """Reset password using the verification code."""
    try:
        email = request.data.get('email')
        code = request.data.get('code')
        new_password = request.data.get('new_password')

        if not all([email, code, new_password]):
            return Response(
                {'error': 'Email, code, and new password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(email=email).first()
        if not user or user.profile.verification_code != code:
            return Response(
                {'error': 'Invalid reset code'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update password and clear reset code
        user.set_password(new_password)
        user.profile.verification_code = None
        user.save()
        user.profile.save()

        logger.info(f"Password reset successful for user {user.username}")
        return Response({'message': 'Password reset successful'})

    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        return Response(
            {'error': 'An error occurred'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )