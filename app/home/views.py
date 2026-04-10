import re
from django.shortcuts import render
from django.views import View
from django.db import connection
from django.utils import timezone
from datetime import timedelta
from zoneinfo import ZoneInfo
from tracker.models import AMPServer, GameStatistic, UserStatistic, WeeklyUserStatistic, WeeklyGameStatistic, DiscordUser

EASTERN = ZoneInfo('America/New_York')

def get_week_start_utc(now):
    now_eastern = now.astimezone(EASTERN)
    days_since_monday = now_eastern.weekday()
    week_start_eastern = (now_eastern - timedelta(days=days_since_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return week_start_eastern.astimezone(ZoneInfo('UTC')), week_start_eastern.date()

def users_sorted(scores_by_id, limit=5):
    result = []
    for user_id, score in sorted(scores_by_id.items(), key=lambda x: x[1], reverse=True):
        try:
            result.append((DiscordUser.objects.get(id=user_id), score))
            if len(result) >= limit:
                break
        except DiscordUser.DoesNotExist:
            pass
    return result


class HomeView(View):
    def get(self, request):
        servers = AMPServer.objects.filter(
            module='GenericModule',
            running=True,
            cover_image__isnull=False
        ).order_by('display_order')

        cursor = connection.cursor()
        now = timezone.now()
        week_start_utc, week_start_date = get_week_start_utc(now)

        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM tracker_gamesession WHERE ended_at IS NULL")
        active_players = cursor.fetchone()[0] or 0
        total_users = UserStatistic.objects.count() + active_players

        cumulative_gaming = sum(s.total_gaming_seconds for s in UserStatistic.objects.all()) // 3600
        cursor.execute("""
            SELECT COALESCE(SUM(duration_seconds), 0) +
                   COALESCE(SUM(CASE WHEN ended_at IS NULL THEN EXTRACT(EPOCH FROM (NOW() - started_at)) ELSE 0 END), 0)
            FROM tracker_gamesession
        """)
        realtime_gaming = cursor.fetchone()[0] // 3600
        total_gaming_hours = cumulative_gaming + realtime_gaming

        cumulative_voice = sum(s.total_voice_seconds for s in UserStatistic.objects.all()) // 3600
        cursor.execute("""
            SELECT COALESCE(SUM(duration_seconds), 0) +
                   COALESCE(SUM(CASE WHEN ended_at IS NULL THEN EXTRACT(EPOCH FROM (NOW() - started_at)) ELSE 0 END), 0)
            FROM tracker_voicesession
        """)
        realtime_voice = cursor.fetchone()[0] // 3600
        total_voice_hours = cumulative_voice + realtime_voice

        cumulative_messages = sum(s.total_messages for s in UserStatistic.objects.all())
        cursor.execute("SELECT COUNT(*) FROM tracker_message")
        realtime_messages = cursor.fetchone()[0] or 0
        total_messages = cumulative_messages + realtime_messages

        # Weekly top gamers
        user_gaming_weekly = {}
        for stat in WeeklyUserStatistic.objects.select_related('user').filter(week_start=week_start_date):
            user_gaming_weekly[stat.user.id] = stat.gaming_seconds

        cursor.execute("""
            SELECT user_id,
                   COALESCE(SUM(duration_seconds), 0) +
                   COALESCE(SUM(CASE WHEN ended_at IS NULL THEN EXTRACT(EPOCH FROM (NOW() - started_at))::int ELSE 0 END), 0)
            FROM tracker_gamesession
            WHERE started_at >= %s
            GROUP BY user_id
        """, [week_start_utc])
        for user_id, seconds in cursor.fetchall():
            user_gaming_weekly[user_id] = user_gaming_weekly.get(user_id, 0) + seconds

        top_gamers = [
            {'user': user, 'hours': int(seconds // 3600)}
            for user, seconds in users_sorted(user_gaming_weekly)
        ]

        # Weekly top games
        def _norm(name):
            return re.sub(r'[™®©]', '', name).strip().lower()
        steam_ids = {_norm(s.game_name): s.steam_app_id for s in GameStatistic.objects.exclude(steam_app_id__isnull=True)}

        game_seconds_weekly = {}
        for stat in WeeklyGameStatistic.objects.filter(week_start=week_start_date):
            game_seconds_weekly[stat.game_name] = stat.seconds

        cursor.execute("""
            SELECT game_name,
                   COALESCE(SUM(duration_seconds), 0) +
                   COALESCE(SUM(CASE WHEN ended_at IS NULL THEN EXTRACT(EPOCH FROM (NOW() - started_at))::int ELSE 0 END), 0)
            FROM tracker_gamesession
            WHERE started_at >= %s
            GROUP BY game_name
        """, [week_start_utc])
        for game_name, seconds in cursor.fetchall():
            game_seconds_weekly[game_name] = game_seconds_weekly.get(game_name, 0) + seconds

        top_games = [
            {'name': name, 'hours': int(seconds // 3600), 'steam_app_id': steam_ids.get(_norm(name))}
            for name, seconds in sorted(game_seconds_weekly.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        # Top voice users
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

        top_voice = [
            {'user': user, 'hours': int(seconds // 3600)}
            for user, seconds in users_sorted(user_voice)
        ]

        # Top chatters
        user_messages = {}
        for stat in UserStatistic.objects.select_related('user'):
            user_messages[stat.user.id] = stat.total_messages

        cursor.execute("SELECT user_id, COUNT(*) FROM tracker_message GROUP BY user_id")
        for user_id, count in cursor.fetchall():
            user_messages[user_id] = user_messages.get(user_id, 0) + count

        top_chatters = [
            {'user': user, 'messages': int(count)}
            for user, count in users_sorted(user_messages)
        ]

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
