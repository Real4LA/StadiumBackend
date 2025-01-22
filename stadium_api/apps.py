from django.apps import AppConfig


class StadiumApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'stadium_api'

    def ready(self):
        import stadium_api.signals  # noqa
