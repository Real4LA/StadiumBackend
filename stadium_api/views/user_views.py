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
from django.core.mail import send_mail
from django.conf import settings
import random
import logging

logger = logging.getLogger(__name__)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]  # Allow any by default

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action == 'me':
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]

    def create(self, request):
        try:
            logger.info("=== Starting User Creation ===")
            logger.info(f"Request data: {request.data}")

            # Check if username exists
            if User.objects.filter(username=request.data.get('username')).exists():
                return Response(
                    {"error": "Username already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if email exists
            if User.objects.filter(email=request.data.get('email')).exists():
                return Response(
                    {"error": "Email already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if phone exists
            if UserProfile.objects.filter(phone=request.data.get('phone')).exists():
                return Response(
                    {"error": "Phone number already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create user with is_active=False
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save(is_active=False)
            logger.info(f"Created user with ID: {user.id}")

            # Generate and save verification code
            verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            logger.info(f"Generated verification code: {verification_code}")

            # Update profile with verification code
            UserProfile.objects.filter(user_id=user.id).update(
                verification_code=verification_code,
                is_verified=False
            )
            
            # Send verification email
            subject = 'Verify your email address'
            message = f'''
Hi {user.first_name},

Thank you for signing up! Your verification code is:

{verification_code}

Please enter this code to verify your account.

If you didn't create this account, you can safely ignore this email.

Best regards,
Tottenham Stadium Team
'''
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            logger.info(f"Sent verification email to: {user.email}")

            return Response({
                "message": "Please check your email for the verification code.",
                "email": user.email,
                "userId": user.id
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error in create: {str(e)}")
            logger.exception(e)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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

                # Compare codes
                stored_code = str(profile.verification_code or '').strip()
                if not stored_code:
                    logger.error("No verification code stored in profile")
                    return Response(
                        {"error": "No verification code found"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                logger.info("Code comparison:")
                logger.info(f"- Stored code: '{stored_code}'")
                logger.info(f"- Received code: '{code}'")
                logger.info(f"- Match: {stored_code == code}")

                if stored_code != code:
                    logger.error("Verification code mismatch")
                    return Response(
                        {"error": "Invalid verification code"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Activate user
                user = profile.user
                user.is_active = True
                user.save()
                logger.info("User activated successfully")

                # Mark as verified and clear code
                profile.is_verified = True
                profile.verification_code = None
                profile.save()
                logger.info("Profile marked as verified")

                # Generate tokens
                refresh = RefreshToken.for_user(user)
                logger.info("Generated new tokens")
                
                response_data = {
                    "message": "Email verified successfully",
                    "tokens": {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    },
                    "user": UserSerializer(user).data
                }
                logger.info("=== Verification Successful ===")
                return Response(response_data)

            except UserProfile.DoesNotExist:
                logger.error(f"No profile found for user_id: {user_id}")
                return Response(
                    {"error": "User not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            logger.error("=== Verification Failed ===")
            logger.error(f"Error: {str(e)}")
            logger.exception(e)
            return Response(
                {"error": "Verification failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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
            subject = 'Your New Verification Code'
            message = f'''
Hi {profile.user.first_name},

Your new verification code is:

{verification_code}

Please enter this code to verify your account.

Best regards,
Tottenham Stadium Team
'''
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [profile.user.email],
                fail_silently=False,
            )

            logger.info(f"Successfully sent new code to {profile.user.email}")
            return Response({
                "message": "New verification code sent successfully",
                "email": profile.user.email
            })

        except Exception as e:
            logger.error(f"Error in resend_code: {str(e)}")
            logger.exception(e)
            return Response(
                {"error": "Failed to resend code. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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