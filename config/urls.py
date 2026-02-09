from django.contrib import admin
from django.urls import path

from alt_text_app import views

urlpatterns = [
    ## main ---------------------------------------------------------
    path('image_uploader/', views.upload_image, name='image_upload_url'),
    path('image/report/<uuid:pk>/', views.view_report, name='image_report_url'),
    ## htmx fragment endpoints --------------------------------------
    path('image/report/<uuid:pk>/status.fragment', views.status_fragment, name='status_fragment_url'),
    path('image/report/<uuid:pk>/alt_text.fragment', views.alt_text_fragment, name='alt_text_fragment_url'),
    path('image/preview/<uuid:pk>/', views.image_preview, name='image_preview_url'),
    path('info/', views.info, name='info_url'),
    ## other --------------------------------------------------------
    path('', views.root, name='root_url'),
    path('admin/', admin.site.urls),
    path('error_check/', views.error_check, name='error_check_url'),
    path('version/', views.version, name='version_url'),
]
