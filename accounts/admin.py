# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserProfile, ProfileImage, UserSubscription, PaymentTransaction # Import your models

# Custom User Admin
class CustomUserAdmin(UserAdmin):
    # Specify the form to use for adding and changing user instances
    # We might not need a custom form here if UserProfileForm is for frontend only
    # If you have an admin-specific form, define it: form = YourAdminUserChangeForm, add_form = YourAdminUserCreationForm

    # The fields to be used in displaying the User model.
    # These override the defaults in UserAdmin.
    list_display = (
        'username', 'email', 'first_name', 'last_name', 
        'is_staff', 'is_active', 'date_joined', 'is_premium', 
        'looking_for', # Changed 'user_type' to 'looking_for'
        'gender', 'location', 'phone_number',
    )
    list_filter = (
        'is_staff', 'is_active', 'is_superuser', 'is_premium', 
        'gender', 'looking_for', # Changed 'user_type' to 'looking_for'
        'seeking', 'date_joined',
    )
    search_fields = ('username', 'email', 'first_name', 'last_name', 'location')
    ordering = ('-date_joined',)

    # Fieldsets for editing an existing user
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'bio', 'gender', 'date_of_birth', 'location', 'phone_number')}),
        ('Dating Profile', {'fields': ('looking_for', 'seeking', 'height', 'body_type', 'ethnicity', 'religion', 'marital_status', 'has_children', 'education', 'occupation', 'drinking_habits', 'smoking_habits')}), # Changed 'user_type' to 'looking_for'
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Premium Status', {'fields': ('is_premium', 'premium_expiry_date')}),
        ('Profile Pictures', {'fields': ('profile_picture', 'main_additional_image')}), # Add profile_picture and main_additional_image
    )

    # Fieldsets for creating a new user (admin interface)
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password', 'password2', 'first_name', 'last_name', 
                       'bio', 'gender', 'date_of_birth', 'location', 'phone_number', 
                       'looking_for', 'seeking', 'is_premium', 'premium_expiry_date'), # Changed 'user_type' to 'looking_for'
        }),
    )

    filter_horizontal = ('groups', 'user_permissions',) # Add back groups and user_permissions if needed

# Register your custom UserProfile model with the custom admin class
admin.site.register(UserProfile, CustomUserAdmin)

# Register ProfileImage with basic admin (can be enhanced later)
@admin.register(ProfileImage)
class ProfileImageAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'image', 'is_main', 'order', 'uploaded_at')
    list_filter = ('is_main',)
    search_fields = ('user_profile__username',)
    raw_id_fields = ('user_profile',) # Use raw_id_fields for ForeignKey to show ID, good for large datasets
    list_editable = ('is_main', 'order') # Allow editing these directly in the list view

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'plan')
    search_fields = ('user__username', 'plan__name')
    raw_id_fields = ('user', 'plan')

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'amount', 'status', 'reference', 'created_at')
    list_filter = ('status', 'plan')
    search_fields = ('user__username', 'plan__name', 'reference')
    raw_id_fields = ('user', 'plan')
    readonly_fields = ('created_at', 'updated_at', 'gateway_response')
