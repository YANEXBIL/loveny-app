# accounts/admin.py

from django.contrib import admin
from .models import UserProfile, Like, Conversation, Message, SubscriptionPlan, UserSubscription, PaymentTransaction # Import all models

# Register your models here.
admin.site.register(UserProfile)
admin.site.register(Like)
admin.site.register(Conversation)
admin.site.register(Message)

# Register the new payment models
admin.site.register(SubscriptionPlan)
admin.site.register(UserSubscription)
admin.site.register(PaymentTransaction)

