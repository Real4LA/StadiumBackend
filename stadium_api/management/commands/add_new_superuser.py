from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Creates an additional superuser'

    def handle(self, *args, **options):
        username = 'stadium_admin'
        if User.objects.filter(username=username).exists():
            self.stdout.write('User stadium_admin already exists')
        else:
            User.objects.create_superuser(
                username=username,
                email='stadium.v0.1.0@gmail.com',
                password='StadiumAdmin2024!'
            )
            self.stdout.write(f'New superuser {username} created successfully')