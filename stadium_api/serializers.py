from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('phone',)

    def validate_phone(self, value):
        if not value:  # If phone is empty or None
            return value
            
        # Clean the phone number (remove spaces, dashes, etc.)
        cleaned_phone = ''.join(filter(str.isdigit, str(value)))
        
        # Check if phone number exists
        if UserProfile.objects.filter(phone=cleaned_phone).exists():
            raise serializers.ValidationError("This phone number is already registered")
        return cleaned_phone

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(required=False)
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)  # Make email required

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'first_name', 'last_name', 'profile')
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True},  # Make email required
            'first_name': {'required': False},
            'last_name': {'required': False}
        }

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("Email address is required.")
        try:
            validate_email(value)
        except ValidationError:
            raise serializers.ValidationError("Enter a valid email address.")
            
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        profile_data = validated_data.pop('profile', None)
        password = validated_data.pop('password')
        email = validated_data.get('email')

        if not email:
            raise serializers.ValidationError({"email": "Email address is required."})

        # Create user
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()

        # Create profile
        if profile_data:
            UserProfile.objects.create(user=user, **profile_data)
        else:
            UserProfile.objects.create(user=user)

        # Send verification email
        try:
            send_mail(
                subject=f"Welcome to {settings.SITE_NAME}",
                message=f"Thank you for registering with {settings.SITE_NAME}. Your account has been created successfully.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception as e:
            # If email sending fails, rollback the transaction
            logger.error(f"Failed to send email: {str(e)}")
            raise serializers.ValidationError({"email": "Failed to send verification email. Please check your email address."})

        return user

    @transaction.atomic
    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', None)
        password = validated_data.pop('password', None)

        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)
        
        instance.save()

        # Update profile
        if profile_data:
            profile = getattr(instance, 'profile', None)
            if profile:
                for attr, value in profile_data.items():
                    setattr(profile, attr, value)
                profile.save()
            else:
                UserProfile.objects.create(user=instance, **profile_data)

        return instance

    def validate(self, data):
        # Add any additional validation here
        if 'profile' in data and data['profile']:
            phone = data['profile'].get('phone')
            if phone:
                # Check if phone exists
                cleaned_phone = ''.join(filter(str.isdigit, phone))
                if UserProfile.objects.filter(phone=cleaned_phone).exists():
                    raise serializers.ValidationError({
                        "profile": {
                            "phone": ["This phone number is already registered."]
                        }
                    })
        return data

class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True) 