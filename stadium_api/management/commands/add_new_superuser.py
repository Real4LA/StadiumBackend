from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Deletes all existing superusers and creates a new one with admin/admin credentials'

    def handle(self, *args, **options):
        # Delete all existing superusers
        User.objects.filter(is_superuser=True).delete()
        self.stdout.write('Deleted all existing superusers')

        # Create new superuser with simple credentials
        User.objects.create_superuser(
            username='admin',
            email='admin@admin.com',
            password='admin'
        )
        self.stdout.write('Created new superuser with username: admin, password: admin')