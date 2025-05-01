from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload_view, name='upload'),  # or any view you want
]
