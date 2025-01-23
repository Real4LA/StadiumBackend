from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile

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

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'first_name', 'last_name', 'profile')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        profile_data = validated_data.pop('profile', None)
        password = validated_data.pop('password')
        
        # Create user
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()

        # Create profile
        if profile_data:
            UserProfile.objects.create(user=user, **profile_data)
        else:
            UserProfile.objects.create(user=user)

        return user

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