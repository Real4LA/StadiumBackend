from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('stadium_api', '0005_alter_calendarsettings_options_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Reservation',
        ),
        migrations.DeleteModel(
            name='Stadium',
        ),
    ] 