from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    POSITION_CHOICES = [
        ('PD', 'Production Director'),
        ('PM', 'Production Manager'),
        ('PS', 'Production Staff'),
        ('SD', 'Sales Director'),
        ('SM', 'Sales Manager'),
        ('SS', 'Sales Staff'),
    ]
    
    position = models.CharField(max_length=3, choices=POSITION_CHOICES, blank=True)
    email_confirmed = models.BooleanField(default=False)
    activation_token = models.UUIDField(default=uuid.uuid4, editable=False)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()