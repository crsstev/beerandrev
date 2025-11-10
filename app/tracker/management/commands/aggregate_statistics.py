from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from datetime import timedelta
from tracker.models import GameStatistic, UserStatistic, GameSession, VoiceSession, Message, DiscordUser, ActivityEvent

class Command(BaseCommand):
    help = 'Aggregate session/message data into statistics, then clear temporary tables'

    def handle(self, *args, **options):
        self.stdout.write("🔄 Starting statistics aggregation...")
        
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        cursor = connection.cursor()
        
        # 1. Aggregate game statistics
        cursor.execute("""
            SELECT game_name, COALESCE(SUM(duration_seconds), 0), COUNT(*)
            FROM tracker_gamesession
            WHERE ended_at IS NOT NULL
            GROUP BY game_name
        """)
        
        for game_name, total_seconds, count in cursor.fetchall():
            stat, created = GameStatistic.objects.get_or_create(game_name=game_name)
            stat.total_seconds += total_seconds
            stat.total_sessions += count
            
            # Calculate this week and month
            cursor.execute(
                "SELECT COALESCE(SUM(duration_seconds), 0) FROM tracker_gamesession WHERE game_name = %s AND ended_at IS NOT NULL AND ended_at > %s",
                [game_name, week_ago]
            )
            stat.total_seconds_this_week = cursor.fetchone()[0]
            
            cursor.execute(
                "SELECT COALESCE(SUM(duration_seconds), 0) FROM tracker_gamesession WHERE game_name = %s AND ended_at IS NOT NULL AND ended_at > %s",
                [game_name, month_ago]
            )
            stat.total_seconds_this_month = cursor.fetchone()[0]
            
            stat.save()
            action = "Created" if created else "Updated"
            self.stdout.write(f"  {action}: {game_name} (+{total_seconds // 3600}h)")
        
        # 2. Aggregate user statistics
        cursor.execute("""
            SELECT DISTINCT user_id FROM tracker_gamesession
            UNION
            SELECT DISTINCT user_id FROM tracker_voicesession
            UNION
            SELECT DISTINCT user_id FROM tracker_message
        """)
        
        user_ids = [row[0] for row in cursor.fetchall()]
        
        for user_id in user_ids:
            try:
                user = DiscordUser.objects.get(id=user_id)
                
                # Gaming hours
                cursor.execute(
                    "SELECT COALESCE(SUM(duration_seconds), 0) FROM tracker_gamesession WHERE user_id = %s AND ended_at IS NOT NULL",
                    [user_id]
                )
                gaming_seconds = cursor.fetchone()[0]
                
                cursor.execute(
                    "SELECT COALESCE(SUM(duration_seconds), 0) FROM tracker_gamesession WHERE user_id = %s AND ended_at IS NOT NULL AND ended_at > %s",
                    [user_id, week_ago]
                )
                gaming_seconds_week = cursor.fetchone()[0]
                
                cursor.execute(
                    "SELECT COALESCE(SUM(duration_seconds), 0) FROM tracker_gamesession WHERE user_id = %s AND ended_at IS NOT NULL AND ended_at > %s",
                    [user_id, month_ago]
                )
                gaming_seconds_month = cursor.fetchone()[0]
                
                # Voice hours
                cursor.execute(
                    "SELECT COALESCE(SUM(duration_seconds), 0) FROM tracker_voicesession WHERE user_id = %s AND ended_at IS NOT NULL",
                    [user_id]
                )
                voice_seconds = cursor.fetchone()[0]
                
                cursor.execute(
                    "SELECT COALESCE(SUM(duration_seconds), 0) FROM tracker_voicesession WHERE user_id = %s AND ended_at IS NOT NULL AND ended_at > %s",
                    [user_id, week_ago]
                )
                voice_seconds_week = cursor.fetchone()[0]
                
                cursor.execute(
                    "SELECT COALESCE(SUM(duration_seconds), 0) FROM tracker_voicesession WHERE user_id = %s AND ended_at IS NOT NULL AND ended_at > %s",
                    [user_id, month_ago]
                )
                voice_seconds_month = cursor.fetchone()[0]
                
                # Messages
                cursor.execute(
                    "SELECT COUNT(*) FROM tracker_message WHERE user_id = %s",
                    [user_id]
                )
                message_count = cursor.fetchone()[0]
                
                cursor.execute(
                    "SELECT COUNT(*) FROM tracker_message WHERE user_id = %s AND created_at > %s",
                    [user_id, week_ago]
                )
                message_count_week = cursor.fetchone()[0]
                
                cursor.execute(
                    "SELECT COUNT(*) FROM tracker_message WHERE user_id = %s AND created_at > %s",
                    [user_id, month_ago]
                )
                message_count_month = cursor.fetchone()[0]
                
                stat, created = UserStatistic.objects.get_or_create(user=user)
                stat.total_gaming_seconds += gaming_seconds
                stat.total_gaming_seconds_this_week = gaming_seconds_week
                stat.total_gaming_seconds_this_month = gaming_seconds_month
                stat.total_voice_seconds += voice_seconds
                stat.total_voice_seconds_this_week = voice_seconds_week
                stat.total_voice_seconds_this_month = voice_seconds_month
                stat.total_messages += message_count
                stat.total_messages_this_week = message_count_week
                stat.total_messages_this_month = message_count_month
                stat.save()
                
                action = "Created" if created else "Updated"
                self.stdout.write(f"  {action}: {user.username} (+{gaming_seconds // 3600}h gaming, +{voice_seconds // 3600}h voice)")
            except DiscordUser.DoesNotExist:
                pass
        
        # 3. Clear temporary tables
        GameSession.objects.all().delete()
        VoiceSession.objects.all().delete()
        Message.objects.all().delete()
        ActivityEvent.objects.all().delete()
        
        self.stdout.write(self.style.SUCCESS('✅ Statistics aggregated and temp tables cleared'))
        cursor.close()
