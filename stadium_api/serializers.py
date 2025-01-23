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
    profile = UserProfileSerializer(required=False)  # Nested serializer for profile
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'first_name', 'last_name', 'profile')
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True},
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
        profile_data = {}
        if 'profile' in validated_data:
            profile_data = validated_data.pop('profile')
        
        password = validated_data.pop('password')
        
        # Create user
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()

        # Update profile with phone if provided
        if profile_data:
            profile = user.profile
            profile.phone = profile_data.get('phone')
            profile.save()

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
            profile = instance.profile
            if 'phone' in profile_data:
                profile.phone = profile_data['phone']
            profile.save()

        return instance

    def validate(self, data):
        # Add any additional validation here
        if 'phone' in data and data['phone']:
            phone = data['phone']
            if UserProfile.objects.filter(phone=phone).exists():
                raise serializers.ValidationError({
                    "phone": ["This phone number is already registered."]
                })
        return data

class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True) 