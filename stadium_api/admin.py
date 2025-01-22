from django.contrib import admin
from .models import CalendarSettings, UserProfile

# Register your models here.
admin.site.register(CalendarSettings)
admin.site.register(UserProfile)
