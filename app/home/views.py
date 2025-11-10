from django.shortcuts import render
from django.views import View
from django.db import connection
from django.utils import timezone
from tracker.models import AMPServer, GameStatistic, UserStatistic, DiscordUser

class HomeView(View):
    def get(self, request):
        servers = AMPServer.objects.filter(
            module='GenericModule',
            running=True,
            cover_image__isnull=False
        ).order_by('display_order')
        
        cursor = connection.cursor()
        now = timezone.now()
        
        # Total unique players
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM tracker_gamesession WHERE ended_at IS NULL")
        active_players = cursor.fetchone()[0] or 0
        total_users = UserStatistic.objects.count() + active_players
        
        # Total gaming hours (cumulative + both ended AND active sessions)
        cumulative_gaming = sum(s.total_gaming_seconds for s in UserStatistic.objects.all()) // 3600
        cursor.execute("""
            SELECT COALESCE(SUM(duration_seconds), 0) + 
                   COALESCE(SUM(EXTRACT(EPOCH FROM (NOW() - started_at))), 0)
            FROM tracker_gamesession 
            WHERE ended_at IS NOT NULL OR ended_at IS NULL
        """)
        realtime_gaming = cursor.fetchone()[0] // 3600
        total_gaming_hours = cumulative_gaming + realtime_gaming
        
        # Total voice hours (cumulative + both ended AND active)
        cumulative_voice = sum(s.total_voice_seconds for s in UserStatistic.objects.all()) // 3600
        cursor.execute("""
            SELECT COALESCE(SUM(duration_seconds), 0) + 
                   COALESCE(SUM(EXTRACT(EPOCH FROM (NOW() - started_at))), 0)
            FROM tracker_voicesession 
            WHERE ended_at IS NOT NULL OR ended_at IS NULL
        """)
        realtime_voice = cursor.fetchone()[0] // 3600
        total_voice_hours = cumulative_voice + realtime_voice
        
        # Total messages (cumulative + real-time)
        cumulative_messages = sum(s.total_messages for s in UserStatistic.objects.all())
        cursor.execute("SELECT COUNT(*) FROM tracker_message")
        realtime_messages = cursor.fetchone()[0] or 0
        total_messages = cumulative_messages + realtime_messages
        
        # Top gamers (include active sessions with live duration calculation)
        user_gaming = {}
        for stat in UserStatistic.objects.select_related('user'):
            user_gaming[stat.user.id] = stat.total_gaming_seconds
        
        cursor.execute("""
            SELECT user_id, 
                   COALESCE(SUM(duration_seconds), 0) + 
                   COALESCE(SUM(CASE WHEN ended_at IS NULL THEN EXTRACT(EPOCH FROM (NOW() - started_at))::int ELSE 0 END), 0)
            FROM tracker_gamesession 
            GROUP BY user_id
        """)
        for user_id, seconds in cursor.fetchall():
            user_gaming[user_id] = user_gaming.get(user_id, 0) + seconds
        
        top_gamers_dict = {}
        for user_id, seconds in user_gaming.items():
            try:
                user = DiscordUser.objects.get(id=user_id)
                top_gamers_dict[user.username] = seconds
            except:
                pass
        
        top_gamers = sorted(top_gamers_dict.items(), key=lambda x: x[1], reverse=True)[:5]
        top_gamers = [{'user': {'username': name}, 'hours': int(seconds // 3600)} for name, seconds in top_gamers]
        
        # Most played games (include active + ended)
        game_seconds = {}
        for stat in GameStatistic.objects.all():
            game_seconds[stat.game_name] = stat.total_seconds
        
        cursor.execute("""
            SELECT game_name, 
                   COALESCE(SUM(duration_seconds), 0) + 
                   COALESCE(SUM(CASE WHEN ended_at IS NULL THEN EXTRACT(EPOCH FROM (NOW() - started_at))::int ELSE 0 END), 0)
            FROM tracker_gamesession 
            GROUP BY game_name
        """)
        for game_name, seconds in cursor.fetchall():
            game_seconds[game_name] = game_seconds.get(game_name, 0) + seconds
        
        top_games = sorted(game_seconds.items(), key=lambda x: x[1], reverse=True)[:5]
        top_games = [(name, int(seconds // 3600)) for name, seconds in top_games]
        
        # Top voice users (include active + ended)
        user_voice = {}
        for stat in UserStatistic.objects.select_related('user'):
            user_voice[stat.user.id] = stat.total_voice_seconds
        
        cursor.execute("""
            SELECT user_id, 
                   COALESCE(SUM(duration_seconds), 0) + 
                   COALESCE(SUM(CASE WHEN ended_at IS NULL THEN EXTRACT(EPOCH FROM (NOW() - started_at))::int ELSE 0 END), 0)
            FROM tracker_voicesession 
            GROUP BY user_id
        """)
        for user_id, seconds in cursor.fetchall():
            user_voice[user_id] = user_voice.get(user_id, 0) + seconds
        
        top_voice_dict = {}
        for user_id, seconds in user_voice.items():
            try:
                user = DiscordUser.objects.get(id=user_id)
                top_voice_dict[user.username] = seconds
            except:
                pass
        
        top_voice = sorted(top_voice_dict.items(), key=lambda x: x[1], reverse=True)[:5]
        top_voice = [{'user': {'username': name}, 'hours': int(seconds // 3600)} for name, seconds in top_voice]
        
        # Top chatters
        user_messages = {}
        for stat in UserStatistic.objects.select_related('user'):
            user_messages[stat.user.id] = stat.total_messages
        
        cursor.execute("SELECT user_id, COUNT(*) FROM tracker_message GROUP BY user_id")
        for user_id, count in cursor.fetchall():
            user_messages[user_id] = user_messages.get(user_id, 0) + count
        
        top_chatters_dict = {}
        for user_id, count in user_messages.items():
            try:
                user = DiscordUser.objects.get(id=user_id)
                top_chatters_dict[user.username] = count
            except:
                pass
        
        top_chatters = sorted(top_chatters_dict.items(), key=lambda x: x[1], reverse=True)[:5]
        top_chatters = [{'user': {'username': name}, 'messages': int(count)} for name, count in top_chatters]
        
        cursor.close()
        
        context = {
            'servers': servers,
            'total_users': total_users,
            'total_gaming_hours': total_gaming_hours,
            'total_voice_hours': total_voice_hours,
            'total_messages': total_messages,
            'top_gamers': top_gamers,
            'top_games': top_games,
            'top_voice': top_voice,
            'top_chatters': top_chatters,
        }
        return render(request, 'home/index.html', context)
