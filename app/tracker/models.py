from django.db import models
from django.utils import timezone
from datetime import timedelta, date

class DiscordUser(models.Model):
    discord_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username


class GameStatistic(models.Model):
    game_name = models.CharField(max_length=255, unique=True)
    total_seconds = models.BigIntegerField(default=0)
    total_sessions = models.IntegerField(default=0)
    total_seconds_this_week = models.BigIntegerField(default=0)
    total_seconds_this_month = models.BigIntegerField(default=0)
    steam_app_id = models.IntegerField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.game_name}: {self.total_seconds // 3600}h"


class UserStatistic(models.Model):
    user = models.OneToOneField(DiscordUser, on_delete=models.CASCADE, related_name='statistic')
    total_gaming_seconds = models.BigIntegerField(default=0)
    total_voice_seconds = models.BigIntegerField(default=0)
    total_messages = models.IntegerField(default=0)
    total_gaming_seconds_this_week = models.BigIntegerField(default=0)
    total_gaming_seconds_this_month = models.BigIntegerField(default=0)
    total_voice_seconds_this_week = models.BigIntegerField(default=0)
    total_voice_seconds_this_month = models.BigIntegerField(default=0)
    total_messages_this_week = models.IntegerField(default=0)
    total_messages_this_month = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}: {self.total_gaming_seconds // 3600}h gaming"


class WeeklyUserStatistic(models.Model):
    user = models.OneToOneField(DiscordUser, on_delete=models.CASCADE, related_name='weekly_statistic')
    week_start = models.DateField(default=date.today)
    gaming_seconds = models.BigIntegerField(default=0)
    sessions = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}: {self.gaming_seconds // 3600}h (week of {self.week_start})"


class WeeklyGameStatistic(models.Model):
    game_name = models.CharField(max_length=255, unique=True)
    week_start = models.DateField(default=date.today)
    seconds = models.BigIntegerField(default=0)
    sessions = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.game_name}: {self.seconds // 3600}h (week of {self.week_start})"


class GameSession(models.Model):
    user = models.ForeignKey(DiscordUser, on_delete=models.CASCADE)
    game_name = models.CharField(max_length=255)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user.username} - {self.game_name}"


class VoiceSession(models.Model):
    user = models.ForeignKey(DiscordUser, on_delete=models.CASCADE)
    channel_name = models.CharField(max_length=255)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user.username} - {self.channel_name}"


class Message(models.Model):
    user = models.ForeignKey(DiscordUser, on_delete=models.CASCADE)
    channel_name = models.CharField(max_length=255)
    message_length = models.IntegerField()
    created_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} in {self.channel_name}"


class ActivityEvent(models.Model):
    user = models.ForeignKey(DiscordUser, on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=50)
    activity_name = models.CharField(max_length=255)
    activity_details = models.JSONField(default=dict)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user.username} - {self.activity_type}"


class AMPServer(models.Model):
    instance_id = models.CharField(max_length=255, unique=True)
    instance_name = models.CharField(max_length=255)
    friendly_name = models.CharField(max_length=255)
    module = models.CharField(max_length=255)
    module_display_name = models.CharField(max_length=255, null=True, blank=True)
    ip = models.CharField(max_length=255)
    port = models.IntegerField()
    running = models.BooleanField(default=False)
    app_state = models.IntegerField()
    cpu_usage_percent = models.FloatField(default=0)
    memory_usage_mb = models.FloatField(default=0)
    active_users = models.IntegerField(default=0)
    cover_image = models.CharField(max_length=255, null=True, blank=True)
    cover_fetched = models.BooleanField(default=False)
    steam_app_id = models.IntegerField(null=True, blank=True)
    display_order = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.module_display_name or self.friendly_name}"

    def is_game(self):
        return self.module != 'ADS'


class AMPServerMetric(models.Model):
    server = models.ForeignKey(AMPServer, on_delete=models.CASCADE, related_name='metrics')
    cpu_usage_percent = models.FloatField()
    memory_usage_mb = models.FloatField()
    active_users = models.IntegerField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        return f"{self.server.module_display_name or self.server.friendly_name} @ {self.recorded_at}"
