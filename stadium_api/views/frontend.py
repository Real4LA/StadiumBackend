from django.views.generic import TemplateView
from django.views.decorators.cache import never_cache
from django.conf import settings
from django.http import HttpResponse
import os

@never_cache
def index(request):
    """Serve the React app's index.html for all non-API routes."""
    try:
        # In production, let whitenoise handle static files
        if not settings.DEBUG:
            with open(os.path.join(settings.REACT_APP_DIR, 'index.html'), 'r') as f:
                return HttpResponse(f.read())
        # In development, serve from template
        else:
            return TemplateView.as_view(template_name='index.html')(request)
    except Exception as e:
        # If index.html is not found, return a basic HTML response
        return HttpResponse(
            '''
            <!DOCTYPE html>
            <html>
                <head>
                    <title>Tottenham Stadium</title>
                </head>
                <body>
                    <div id="root"></div>
                    <script src="/static/js/main.js"></script>
                </body>
            </html>
            ''',
            content_type='text/html'
        ) 