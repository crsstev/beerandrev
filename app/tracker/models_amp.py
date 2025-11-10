from django.db import models
from django.utils import timezone

class AMPServer(models.Model):
    instance_id = models.CharField(max_length=255, unique=True)
    instance_name = models.CharField(max_length=255)
    friendly_name = models.CharField(max_length=255)
    module = models.CharField(max_length=255)  # Game type
    module_display_name = models.CharField(max_length=255, null=True, blank=True)
    ip = models.CharField(max_length=255)
    port = models.IntegerField()
    running = models.BooleanField(default=False)
    app_state = models.IntegerField()
    
    # Latest metrics
    cpu_usage_percent = models.FloatField(default=0)
    memory_usage_mb = models.FloatField(default=0)
    active_users = models.IntegerField(default=0)
    
    # Cover art
    cover_image = models.CharField(max_length=255, null=True, blank=True)
    cover_fetched = models.BooleanField(default=False)
    
    # Display order
    display_order = models.IntegerField(default=0)
    
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.module_display_name or self.friendly_name}"

    def is_game(self):
        """Check if this is an actual game (not ADS)"""
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
