# Generated by Django 5.1.5 on 2025-01-20 12:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stadium_api', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservation',
            name='calendar_event_id',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='stadium',
            name='calendar_id',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
