# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserProfile, Like, SubscriptionPlan, UserSubscription, PaymentTransaction, ProfileImage


# Inline admin for ProfileImage to manage them directly from the UserProfile admin page
class ProfileImageInline(admin.TabularInline): # Or admin.StackedInline for a different layout
    model = ProfileImage
    extra = 1 # Number of empty forms to display
    fields = ('image',) # Only need to display the image field


@admin.register(UserProfile)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_staff', 'is_premium', 'user_type', 'gender', 'phone_number')
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('bio', 'gender', 'date_of_birth', 'profile_picture', 'location', 'user_type', 'seeking', 'is_premium', 'phone_number')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('user_type', 'gender', 'date_of_birth', 'location', 'phone_number')}),
    )
    # Add the inline for ProfileImage
    inlines = [ProfileImageInline]


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
    fields = ('name', 'price', 'duration_days', 'description', 'features', 'is_active')

    def get_features_display(self, obj):
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

# Register ProfileImage directly if you also want a top-level admin for it
@admin.register(ProfileImage)
class ProfileImageAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'image', 'uploaded_at')
    list_filter = ('uploaded_at', 'user_profile__username')
    search_fields = ('user_profile__username',)
    raw_id_fields = ('user_profile',) # For easier selection of user_profile in admin
