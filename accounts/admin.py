# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin # For custom user model in admin
# Import only the models that actually exist in your models.py
from .models import UserProfile, Like, SubscriptionPlan, UserSubscription, PaymentTransaction 


# Register your custom UserProfile model with the admin site
# Use the default UserAdmin for full functionality, or customize it as needed
@admin.register(UserProfile)
class CustomUserAdmin(UserAdmin):
    # You can customize fields displayed in the admin list view
    list_display = ('username', 'email', 'is_staff', 'is_premium', 'user_type', 'gender', 'phone_number')
    # Add phone_number to fields that can be edited in the admin
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('bio', 'gender', 'date_of_birth', 'profile_picture', 'location', 'user_type', 'seeking', 'is_premium', 'phone_number')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('user_type', 'gender', 'date_of_birth', 'location', 'phone_number')}),
    )


# Register other models with the admin site
@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ('liker', 'liked_user', 'timestamp', 'is_match')
    list_filter = ('timestamp',)
    search_fields = ('liker__username', 'liked_user__username')


# Conversation and Message models are removed, so we remove their registration:
# @admin.register(Conversation)
# class ConversationAdmin(admin.ModelAdmin):
#     list_display = ('user1', 'user2', 'created_at')
#     search_fields = ('user1__username', 'user2__username')


# @admin.register(Message)
# class MessageAdmin(admin.ModelAdmin):
#     list_display = ('conversation', 'sender', 'timestamp', 'content')
#     list_filter = ('timestamp', 'sender__username')
#     search_fields = ('content', 'sender__username')


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_days', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'plan')
    search_fields = ('user__username',)


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'amount', 'status', 'reference', 'created_at')
    list_filter = ('status', 'plan')
    search_fields = ('user__username', 'reference')
    readonly_fields = ('gateway_response',) # Gateway response should generally not be editable via admin
