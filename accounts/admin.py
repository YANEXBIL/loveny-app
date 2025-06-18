# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
# Import only the models that actually exist in your models.py
from .models import UserProfile, Like, SubscriptionPlan, UserSubscription, PaymentTransaction 


# Register your custom UserProfile model with the admin site
@admin.register(UserProfile)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_staff', 'is_premium', 'user_type', 'gender', 'phone_number')
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


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_days', 'is_active', 'created_at', 'get_features_display')
    list_filter = ('is_active',)
    search_fields = ('name',)
    # Add 'features' to the fields that can be edited in the admin
    fields = ('name', 'price', 'duration_days', 'description', 'features', 'is_active')

    def get_features_display(self, obj):
        """Displays features as a comma-separated string for list_display."""
        return ", ".join(obj.features) if obj.features else "No features"
    get_features_display.short_description = "Features"


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
    readonly_fields = ('gateway_response',)
