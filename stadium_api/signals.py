from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db import DEFAULT_DB_ALIAS

@receiver(post_migrate)
def create_superuser(sender, **kwargs):
    if kwargs.get('using', DEFAULT_DB_ALIAS) != DEFAULT_DB_ALIAS:
        return
    
    # Create superuser only if no superuser exists
    if not User.objects.filter(is_superuser=True).exists():
        User.objects.create_superuser(
            username='admin',
            email='admin@admin.com',
            password='admin'
        )
        print('Superuser created successfully')
    else:
        print('Superuser already exists') 