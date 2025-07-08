from django.urls import path
from . import views
from .views import register

urlpatterns = [
    path('', views.home, name='home'),
    path('accounts/profile/', views.profile, name='profile'),
    path('accounts/register/', views.register, name='register'),
    path('accounts/login/', views.user_login, name='login'),
    path('accounts/logout/', views.user_logout, name='logout'),
    path('accounts/edit_profile/', views.edit_profile, name='edit_profile'),
    path('accounts/track_click/', views.track_job_click, name='track_job_click'),
    path('accounts/similar_users/', views.similar_users_recommendations, name='similar_users'),
    path('accounts/record-click/', views.record_job_click, name='record_click'),
    path('accounts/search/', views.search_jobs, name='search_jobs'),
    path('accounts/evaluate/', views.evaluate_system, name='evaluate_system'),




]
