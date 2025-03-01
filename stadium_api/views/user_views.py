from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from ..serializers import UserSerializer
from ..models import UserProfile
from django.core.mail import send_mail, get_connection
from django.conf import settings
import random
import logging
import traceback
import socket

logger = logging.getLogger(__name__)

def send_verification_email(user, verification_code, is_resend=False):
    """Helper function to send verification email with enhanced error handling"""
    try:
        # Test email settings
        logger.info("Testing email settings...")
        logger.info(f"EMAIL_HOST: {settings.EMAIL_HOST}")
        logger.info(f"EMAIL_PORT: {settings.EMAIL_PORT}")
        logger.info(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
        logger.info(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
        logger.info(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")

        # Test SMTP connection
        logger.info("Testing SMTP connection...")
        connection = get_connection()
        try:
            connection.open()
            logger.info("SMTP connection successful")
        except socket.error as e:
            logger.error(f"SMTP connection failed: {str(e)}")
            raise
        finally:
            connection.close()

        subject = 'Your New Verification Code' if is_resend else 'Verify your email address'
        message = f'''
Hi {user.first_name or 'there'},

{'Here is your new verification code' if is_resend else 'Thank you for signing up! Your verification code is'}:

{verification_code}

Please enter this code to verify your account.

If you didn't create this account, you can safely ignore this email.

Best regards,
Tottenham Stadium Team
'''
        logger.info(f"Sending email to {user.email}")
        logger.info(f"Subject: {subject}")
        logger.info(f"From: {settings.DEFAULT_FROM_EMAIL}")

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        logger.info(f"Email sent successfully to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.action == 'me':
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]

    def create(self, request):
        try:
            logger.info("=== Starting User Registration ===")
            logger.info(f"Request data: {request.data}")

            # Validate unique fields first
            if User.objects.filter(username=request.data.get('username')).exists():
                return Response(
                    {"error": "Username already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if User.objects.filter(email=request.data.get('email')).exists():
                return Response(
                    {"error": "Email already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            phone = request.data.get('phone')
            if phone and UserProfile.objects.filter(phone=phone).exists():
                return Response(
                    {"error": "Phone number already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Generate verification code
            verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            logger.info(f"Generated verification code: {verification_code}")

            # Create user first
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save(is_active=False)
            logger.info(f"Created user with ID: {user.id}")

            # Update profile with verification code
            user.profile.verification_code = verification_code
            user.profile.is_verified = False
            user.profile.save()
            logger.info("Updated user profile with verification code")

            # Send verification email
            try:
                send_verification_email(user, verification_code)
            except Exception as email_error:
                # If email fails, delete the user and return error
                user.delete()
                return Response({
                    "error": "Failed to send verification email. Please try again.",
                    "details": str(email_error)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                "user": UserSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error("=== Registration Failed ===")
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response({
                "error": "Registration failed. Please try again.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='verify-code', permission_classes=[AllowAny], authentication_classes=[])
    def verify_code(self, request):
        try:
            logger.info("=== Starting Verification Process ===")
            logger.info(f"Raw request data: {request.data}")
            logger.info(f"Request headers: {request.headers}")

            code = str(request.data.get('code', '')).strip()
            user_id = request.data.get('userId')
            
            logger.info(f"Parsed data - user_id: {user_id}, code: {code}")

            if not code or not user_id:
                logger.error("Missing required fields")
                logger.error(f"Code present: {bool(code)}")
                logger.error(f"User ID present: {bool(user_id)}")
                return Response(
                    {"error": "Verification code and user ID are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                # First find the profile
                profile = UserProfile.objects.select_related('user').get(user_id=user_id)
                logger.info(f"Found profile - user_id: {user_id}")
                logger.info(f"Profile data:")
                logger.info(f"- Verification code: {profile.verification_code}")
                logger.info(f"- Is verified: {profile.is_verified}")
                logger.info(f"- User active: {profile.user.is_active}")
                
                # Check if already verified
                if profile.is_verified:
                    logger.info("Profile is already verified")
                    return Response(
                        {"error": "Email is already verified"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Verify the code
                if code != profile.verification_code:
                    logger.error("Invalid verification code")
                    logger.error(f"Received: {code}")
                    logger.error(f"Expected: {profile.verification_code}")
                    return Response(
                        {"error": "Invalid verification code"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Code is valid, update profile and user
                profile.is_verified = True
                profile.verification_code = None  # Clear the code
                profile.save()

                # Activate the user
                user = profile.user
                user.is_active = True
                user.save()

                logger.info(f"Successfully verified user {user_id}")

                # Generate tokens for automatic login
                refresh = RefreshToken.for_user(user)
                
                return Response({
                    "message": "Email verified successfully",
                    "user": UserSerializer(user).data,
                    "tokens": {
                        "access": str(refresh.access_token),
                        "refresh": str(refresh),
                    }
                })

            except UserProfile.DoesNotExist:
                logger.error(f"Profile not found for user_id: {user_id}")
                return Response(
                    {"error": "User not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            logger.error("=== Verification Failed ===")
            logger.error(f"Error: {str(e)}")
            logger.exception(e)
            return Response({
                "error": "Verification failed. Please try again.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='resend-code', permission_classes=[AllowAny], authentication_classes=[])
    def resend_code(self, request):
        try:
            user_id = request.data.get('userId')
            logger.info(f"Resending code for user ID: {user_id}")

            if not user_id:
                return Response(
                    {"error": "User ID is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                profile = UserProfile.objects.select_related('user').get(
                    user_id=user_id,
                    is_verified=False
                )
            except UserProfile.DoesNotExist:
                return Response(
                    {"error": "User not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Generate new verification code
            verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            logger.info(f"Generated new code: {verification_code}")

            # Save new code
            profile.verification_code = verification_code
            profile.save()

            # Send new verification email
            try:
                send_verification_email(profile.user, verification_code, is_resend=True)
                return Response({"message": "Verification code resent successfully"})
            except Exception as email_error:
                logger.error(f"Failed to resend verification email: {str(email_error)}")
                return Response({
                    "error": "Failed to send verification email. Please try again.",
                    "details": str(email_error)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error("=== Resend Code Failed ===")
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response({
                "error": "Failed to resend code. Please try again.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated], authentication_classes=[JWTAuthentication])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

@api_view(['POST'])
@permission_classes([AllowAny])
def user_login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    
    user = authenticate(username=username, password=password)
    if user:
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'profile': {
                    'phone': user.profile.phone
                }
            },
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        })
    else:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        ) 