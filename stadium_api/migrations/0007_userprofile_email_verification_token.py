# Generated by Django 5.1.5 on 2025-01-21 13:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stadium_api', '0006_remove_stadium_and_reservation'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='email_verification_token',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
