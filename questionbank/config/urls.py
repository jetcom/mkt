from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.mixins import LoginRequiredMixin


class ProtectedHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'index.html'
    login_url = '/login/'


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('questions.urls')),
    path('api/ai/', include('ai_tools.urls')),
    path('api/exams/', include('exams.urls')),
    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    # Frontend routes - protected
    path('', ProtectedHomeView.as_view(), name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
