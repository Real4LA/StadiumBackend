import re
from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware

class CustomCsrfMiddleware(CsrfViewMiddleware):
    def process_view(self, request, callback, callback_args, callback_kwargs):
        # Check if the path matches any exempt patterns
        for exempt_url in getattr(settings, 'CSRF_EXEMPT_URLS', []):
            if re.compile(exempt_url).match(request.path_info):
                return None
        return super().process_view(request, callback, callback_args, callback_kwargs) 