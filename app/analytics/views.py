from django.shortcuts import render
from django.views import View
from django.db.models import Count
from tracker.models import DiscordUser, GameSession, VoiceSession, Message, GameStatistic, UserStatistic, ActivityEvent

class AnalyticsDashboardView(View):
    def get(self, request):
        context = {
            'total_users': DiscordUser.objects.count(),
            'total_sessions': GameSession.objects.count(),
            'total_voice': VoiceSession.objects.count(),
            'total_messages': Message.objects.count(),
        }
        return render(request, 'analytics/dashboard.html', context)

class GameStatsView(View):
    def get(self, request):
        games = GameStatistic.objects.order_by('-total_seconds')
        context = {'games': games}
        return render(request, 'analytics/games.html', context)

class VoiceStatsView(View):
    def get(self, request):
        stats = UserStatistic.objects.select_related('user').filter(
            total_voice_seconds__gt=0
        ).order_by('-total_voice_seconds')[:10]
        session_counts = {
            row['user_id']: row['cnt']
            for row in VoiceSession.objects.values('user_id').annotate(cnt=Count('id'))
        }
        voice_users = [
            {
                'user': stat.user,
                'hours': stat.total_voice_seconds // 3600,
                'sessions': session_counts.get(stat.user.id, 0),
            }
            for stat in stats
        ]
        context = {'voice_users': voice_users}
        return render(request, 'analytics/voice.html', context)

class MessageStatsView(View):
    def get(self, request):
        top_messages = Message.objects.values('user__username').annotate(count=Count('id')).order_by('-count')[:10]
        context = {'messages': top_messages}
        return render(request, 'analytics/messages.html', context)
