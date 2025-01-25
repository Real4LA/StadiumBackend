from django.views.generic import TemplateView
from django.views.decorators.cache import never_cache
from django.conf import settings
import os

# Serve React frontend
index = never_cache(TemplateView.as_view(template_name='index.html')) 