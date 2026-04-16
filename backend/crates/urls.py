"""
URL configuration for crates project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
"""
Project root URLConf for CRATES.

- `/admin/` Django admin
- `/api/` REST API routed to apps.core.urls
"""

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path

from crates.admin_site import crates_admin_site
from apps.core.media_views import serve_media

urlpatterns = [
    re_path(r"^media/(?P<path>.*)$", serve_media, name="media-serve"),
    path("admin/", crates_admin_site.urls),
    path("api/", include("apps.core.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
