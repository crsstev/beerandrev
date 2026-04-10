from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('', views.AnalyticsDashboardView.as_view(), name='dashboard'),
    path('games/', views.GameStatsView.as_view(), name='games'),
    path('voice/', views.VoiceStatsView.as_view(), name='voice'),
    path('messages/', views.MessageStatsView.as_view(), name='messages'),
]
