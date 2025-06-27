from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
import os
from datetime import date, timedelta
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator # Keep if still used, otherwise can remove
from django.utils.translation import gettext_lazy as _
from django.conf import settings # Make sure settings is imported for MEDIA_ROOT reference
from uuid import uuid4 # For unique filenames

# --- Custom Validators ---
def validate_image_file_size(value):
    """
    Validator to ensure the uploaded image file size does not exceed 5MB.
    """
    filesize = value.size
    if filesize > 5 * 1024 * 1024:  # 5 MB (5 * 1024 * 1024 bytes)
        raise ValidationError(_("The maximum file size that can be uploaded is 5MB."))
    return value

# --- Custom Upload Path Function ---
def user_image_directory_path(instance, filename):
    """
    Defines the upload path for user profile images and additional gallery images.
    Files will be uploaded to MEDIA_ROOT/profile_pictures/user_<id>/filename (for main profile_picture)
    or MEDIA_ROOT/profile_pictures/user_<id>/gallery/<filename> (for ProfileImage instances)
    """
    # Generate a unique filename using UUID to prevent collisions
    ext = filename.split('.')[-1]
    filename = f"{uuid4()}.{ext}"

    if isinstance(instance, UserProfile):
        # We use instance.id directly because UserProfile IS now the User model
        # For the main profile_picture field on UserProfile
        return os.path.join('profile_pictures', f'user_{instance.id}', filename)
        
    elif isinstance(instance, ProfileImage):
        # For ProfileImage instances (additional gallery images)
        # Ensure user_profile is available for ProfileImage instances
        return os.path.join('profile_pictures', f'user_{instance.user_profile.id}', 'gallery', filename)
        
    return os.path.join('uploads', filename) # Fallback just in case, though should not be hit


# Define choices for various profile fields
GENDER_CHOICES = [
    ('M', 'Male'),
    ('F', 'Female'),
    ('O', 'Other'),
]

SEEKING_CHOICES = [
    ('M', 'Male'),
    ('F', 'Female'),
    ('O', 'Other'),
    ('A', 'Anyone'),
]

LOOKING_FOR_CHOICES = [
    ('DATING', 'Dating'),
    ('HOOKUP', 'Hookup'),
    ('SUGAR_DADDY', 'Sugar Daddy'),
    ('SUGAR_MUMMY', 'Sugar Mummy'),
    ('SEXCALL', 'Sex Call'), # New option
]

HEIGHT_CHOICES = [(f'{i}', f"{int(i/12)}'{i%12}\"") for i in range(48, 97)] # 4'0" to 8'0"
BODY_TYPE_CHOICES = [
    ('SLIM', 'Slim'), ('ATHLETIC', 'Athletic'), ('AVERAGE', 'Average'),
    ('CURVY', 'Curvy'), ('MUSCULAR', 'Muscular'), ('PLUS_SIZE', 'Plus Size')
]
ETHNICITY_CHOICES = [
    ('CAUCASIAN', 'Caucasian'), ('AFRICAN', 'African'), ('ASIAN', 'Asian'),
    ('HISPANIC', 'Hispanic'), ('MIXED', 'Mixed'), ('OTHER', 'Other')
]
RELIGION_CHOICES = [
    ('CHRISTIANITY', 'Christianity'), ('ISLAM', 'Islam'), ('HINDUISM', 'Hinduism'),
    ('BUDDHISM', 'Buddhism'), ('ATHEIST', 'Atheist'), ('OTHER', 'Other')
]
MARITAL_STATUS_CHOICES = [
    ('SINGLE', 'Single'), ('DIVORCED', 'Divorced'), ('WIDOWED', 'Widowed'),
    ('SEPARATED', 'Separated'), ('IN_RELATIONSHIP', 'In a Relationship')
]
EDUCATION_CHOICES = [
    ('HIGH_SCHOOL', 'High School'), ('SOME_COLLEGE', 'Some College'),
    ('ASSOCIATES', 'Associates Degree'), ('BACHELORS', 'Bachelors Degree'),
    ('MASTERS', 'Masters Degree'), ('PHD', 'PhD')
]
OCCUPATION_CHOICES = [('STUDENT', 'Student'), ('EMPLOYED', 'Employed'), ('SELF_EMPLOYED', 'Self-Employed'), ('UNEMPLOYED', 'Unemployed'), ('RETIRED', 'Retired')]
DRINKING_CHOICES = [('NEVER', 'Never'), ('SOCIALLY', 'Socially'), ('FREQUENTLY', 'Frequently'), ('HEAVILY', 'Heavily')]
SMOKING_CHOICES = [('NON_SMOKER', 'Non-Smoker'), ('OCCASIONALLY', 'Occasionally'), ('REGULARLY', 'Regularly'), ('HEAVILY', 'Heavily')]


# --- Custom User Manager (for UserProfile, which is now AbstractUser) ---
class UserProfileManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(email, username, password, **extra_fields)

# --- Custom UserProfile model extending Django's AbstractUser ---
class UserProfile(AbstractUser):
    # Overriding default AbstractUser fields if needed, or adding new ones
    email = models.EmailField(_('email address'), unique=True, null=False, blank=False)
    username = models.CharField(_('username'), max_length=150, unique=True, null=False, blank=False)
    # The AbstractUser already provides first_name, last_name, is_staff, is_active, date_joined, etc.
    # IMPORTANT: We *DO NOT* redefine 'groups' or 'user_permissions' here, as AbstractUser handles them
    # and defining them again causes the clash.

    # Personal Information
    bio = models.TextField(max_length=500, blank=True, null=True, help_text="Tell us about yourself.")
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    
    # CORRECTED: Changed default to None so it doesn't store a media path for a static file.
    # The frontend will display settings.STATIC_URL + settings.DEFAULT_PROFILE_PICTURE_PATH if this is None.
    profile_picture = models.ImageField(
        upload_to=user_image_directory_path, 
        blank=True,
        null=True,
        default=None, # CRUCIAL CHANGE: No default media path.
        validators=[validate_image_file_size] 
    )
    location = models.CharField(max_length=100, blank=True, null=True)
    
    # Phone number for WhatsApp contact
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Your WhatsApp phone number including country code (e.g., +2348012345678)"
    )

    # This field links to a ProfileImage instance if it's currently used as the main profile picture.
    # It ensures the 'profile_picture' field (ImageField) is kept in sync with one of the 'ProfileImage' instances.
    main_additional_image = models.OneToOneField(
        'ProfileImage', 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        related_name='is_main_profile_picture_for', 
        help_text="Links to a ProfileImage instance if it's currently used as the main profile picture. (This field helps manage which gallery image is the main one visually, syncing with 'profile_picture')."
    )

    # Dating/Hookup/Sugar specific fields
    looking_for = models.CharField(
        max_length=20,
        choices=LOOKING_FOR_CHOICES, 
        default='DATING',
        help_text="Are you looking for dating, hookups, or are you a sugar daddy/mummy?"
    )
    seeking = models.CharField(
        max_length=1,
        choices=SEEKING_CHOICES,
        blank=True,
        null=True,
        help_text="Who are you seeking?"
    )
    is_premium = models.BooleanField(default=False)
    premium_expiry_date = models.DateTimeField(null=True, blank=True)

    # Detailed profile information (add/remove as per your design)
    height = models.CharField(max_length=10, choices=HEIGHT_CHOICES, blank=True, null=True)
    body_type = models.CharField(max_length=20, choices=BODY_TYPE_CHOICES, blank=True, null=True)
    ethnicity = models.CharField(max_length=50, choices=ETHNICITY_CHOICES, blank=True, null=True)
    religion = models.CharField(max_length=50, choices=RELIGION_CHOICES, blank=True, null=True)
    marital_status = models.CharField(max_length=30, choices=MARITAL_STATUS_CHOICES, blank=True, null=True)
    has_children = models.BooleanField(null=True, blank=True) 
    education = models.CharField(max_length=50, choices=EDUCATION_CHOICES, blank=True, null=True)
    occupation = models.CharField(max_length=100, choices=OCCUPATION_CHOICES, blank=True, null=True)
    drinking_habits = models.CharField(max_length=20, choices=DRINKING_CHOICES, blank=True, null=True)
    smoking_habits = models.CharField(max_length=20, choices=SMOKING_CHOICES, blank=True, null=True)
    
    # Custom manager for UserProfile
    objects = UserProfileManager()

    USERNAME_FIELD = 'email' # Use email as the unique identifier for login
    REQUIRED_FIELDS = ['username'] # Required when creating a user via createsuperuser, etc.

    def __str__(self):
        return self.username

    def clean(self):
        super().clean()
        if self.date_of_birth:
            today = date.today()
            age = today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
            if age < 18:
                raise ValidationError({'date_of_birth': _('You must be at least 18 years old.')})

    @property
    def get_age(self):
        """
        Calculates and returns the user's age based on their date of birth.
        """
        if self.date_of_birth:
            today = date.today()
            age = today.year - self.date_of_birth.year - \
                    ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
            return age
        return None

    @property
    def get_full_name(self):
        """
        Returns the user's full name, prioritizing `first_name` and `last_name` from AbstractUser,
        or falling back to username.
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        return self.username # Fallback if no names set

    class Meta:
        verbose_name = _("User Profile")
        verbose_name_plural = _("User Profiles")
        ordering = ['username'] # Inherited from AbstractUser, good to keep

# --- NEW Model for additional profile images ---
class ProfileImage(models.Model):
    """
    Stores additional images for a user's profile.
    Each image can be designated as the 'main' profile picture.
    """
    user_profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='profile_images', # Changed from 'additional_images' for consistency
        help_text="The user profile this image belongs to."
    )
    image = models.ImageField(
        upload_to=user_image_directory_path, 
        help_text="Additional profile image.",
        validators=[validate_image_file_size],
    )
    is_main = models.BooleanField(default=False) # Indicates if this image is the primary one
    order = models.PositiveIntegerField(default=0, blank=True, null=True, db_index=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-uploaded_at']  
        verbose_name = "Profile Image"
        verbose_name_plural = "Profile Images"
        # Removed unique_together = ('user_profile', 'is_main')
        # This constraint is handled in the save method for more flexible logic
        # as multiple images can technically be 'main' before save updates them.

    def save(self, *args, **kwargs):
        # If this image is set as main, ensure all others for this user are not main
        if self.is_main:
            # First, ensure no other ProfileImage is main for this user_profile
            ProfileImage.objects.filter(user_profile=self.user_profile).exclude(pk=self.pk).update(is_main=False)
            
            # Then, update the main profile_picture field on UserProfile to this image
            self.user_profile.profile_picture = self.image
            self.user_profile.save(update_fields=['profile_picture'])
            
            # Also update the main_additional_image foreign key on UserProfile
            self.user_profile.main_additional_image = self
            self.user_profile.save(update_fields=['main_additional_image'])

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Image for {self.user_profile.username} (Main: {self.is_main})"


# --- Signals for file deletion ---

@receiver(post_delete, sender=ProfileImage)
def auto_delete_file_on_delete_profile_image(sender, instance, **kwargs):
    """
    Deletes image file from filesystem when corresponding ProfileImage object is deleted.
    """
    if instance.image:
        if os.path.isfile(instance.image.path):
            os.remove(instance.image.path)

@receiver(pre_save, sender=ProfileImage)
def auto_delete_file_on_change_profile_image(sender, instance, **kwargs):
    """
    Deletes old image file from filesystem when corresponding ProfileImage object is updated
    with a new file.
    """
    if not instance.pk:
        return False # Object is new, no old file to delete

    try:
        old_image = sender.objects.get(pk=instance.pk).image
    except sender.DoesNotExist:
        return False # Old object doesn't exist, nothing to delete

    new_image = instance.image
    if old_image and old_image != new_image:
        if os.path.isfile(old_image.path):
            os.remove(old_image.path)

@receiver(post_delete, sender=UserProfile)
def auto_delete_file_on_delete_user_profile(sender, instance, **kwargs):
    """
    Deletes profile_picture file from filesystem when a UserProfile object is deleted.
    """
    # Only delete if it's a real file and not the default static path
    if instance.profile_picture:
        # Check if it's the configured default static image path (e.g., 'default_avatar.png')
        if hasattr(settings, 'DEFAULT_PROFILE_PICTURE_PATH') and \
           instance.profile_picture.name.endswith(settings.DEFAULT_PROFILE_PICTURE_PATH):
            return # Don't delete static default image
        
        # If it's stored with the 'profile_pics/' prefix but is the default, also skip
        if (hasattr(settings, 'DEFAULT_PROFILE_PICTURE_PATH') and 
            instance.profile_picture.name.startswith('profile_pics/') and 
            instance.profile_picture.name.endswith(settings.DEFAULT_PROFILE_PICTURE_PATH)):
            return

        if os.path.isfile(instance.profile_picture.path):
            os.remove(instance.profile_picture.path)
    
    # Cascade delete for ProfileImage instances and their files is handled by their own signals.

@receiver(pre_save, sender=UserProfile)
def auto_delete_file_on_change_user_profile(sender, instance, **kwargs):
    """
    Deletes old profile_picture file from filesystem when a UserProfile object is updated
    with a new profile picture.
    """
    if not instance.pk:
        return False # Object is new, no old file to delete

    try:
        old_profile_picture = sender.objects.get(pk=instance.pk).profile_picture
    except sender.DoesNotExist:
        return False # Old object doesn't exist, nothing to delete

    new_profile_picture = instance.profile_picture
    # Check if the new picture is different from the old one AND not the default
    if old_profile_picture and old_profile_picture != new_profile_picture:
        if hasattr(settings, 'DEFAULT_PROFILE_PICTURE_PATH') and \
           old_profile_picture.name.endswith(settings.DEFAULT_PROFILE_PICTURE_PATH):
            return # Don't delete static default image
        
        # If it's stored with the 'profile_pics/' prefix but is the default, also skip
        if (hasattr(settings, 'DEFAULT_PROFILE_PICTURE_PATH') and 
            old_profile_picture.name.startswith('profile_pics/') and 
            old_profile_picture.name.endswith(settings.DEFAULT_PROFILE_PICTURE_PATH)):
            return

        if os.path.isfile(old_profile_picture.path):
            os.remove(old_profile_picture.path)


# Model: Like (Updated to reflect UserProfile as the User model)
class Like(models.Model):
    """
    Represents a 'like' action between two UserProfile instances.
    """
    liker = models.ForeignKey(
        UserProfile, 
        on_delete=models.CASCADE,
        related_name='likes_given',
        help_text="The user who performed the 'like' action."
    )
    liked_user = models.ForeignKey(
        UserProfile, 
        on_delete=models.CASCADE,
        related_name='likes_received',
        help_text="The user who was 'liked'."
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="The date and time when the like was created."
    )

    class Meta:
        unique_together = ('liker', 'liked_user')
        ordering = ['-timestamp']
        verbose_name = "Like"
        verbose_name_plural = "Likes"

    def __str__(self):
        return f"{self.liker.username} likes {self.liked_user.username}"

    def is_match(self):
        """
        Checks if this like creates a mutual match.
        """
        return Like.objects.filter(
            liker=self.liked_user,
            liked_user=self.liker
        ).exists()


# Models for Subscription and Payments (Updated to reflect UserProfile as the User model)
class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(help_text="Duration of the plan in days")
    description = models.TextField(blank=True, null=True)
    features = models.JSONField(default=list, blank=True, help_text="List of features included in this plan (e.g., ['Ad-free experience', 'Send unlimited messages'])")
    is_active = models.BooleanField(default=True)
    paystack_plan_code = models.CharField(max_length=100, blank=True, null=True, unique=True, help_text="Paystack plan code for recurring subscriptions") # ADDED
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Subscription Plan"
        verbose_name_plural = "Subscription Plans"

    def __str__(self):
        return f"{self.name} (₦{self.price})"

class UserSubscription(models.Model):
    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='subscription') 
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    paystack_authorization_code = models.CharField(max_length=100, blank=True, null=True, help_text="Authorization code from Paystack for recurring payments") # ADDED
    paystack_subscription_code = models.CharField(max_length=100, blank=True, null=True, unique=True, help_text="Subscription code from Paystack for managing the subscription") # ADDED
    paystack_email_token = models.CharField(max_length=100, blank=True, null=True, help_text="Email token from Paystack for re-authorization if needed") # ADDED
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Subscription"
        verbose_name_plural = "User Subscriptions"

    def __str__(self):
        return f"{self.user.username}'s subscription to {self.plan.name if self.plan else 'N/A'}"

    def save(self, *args, **kwargs):
        # Calculate end_date only if it's not already set and plan exists
        if self.plan and not self.end_date:
            self.end_date = self.start_date + timedelta(days=self.plan.duration_days)
        
        # If the subscription is active and has an end_date, ensure it's not past
        # This logic might be better handled by a property or in views, but for simplicity here:
        if self.is_active and self.end_date and self.end_date < models.DateTimeField().now(): # Use models.DateTimeField().now() or django.utils.timezone.now()
            self.is_active = False # Automatically deactivate if past end_date

        super().save(*args, **kwargs)

class PaymentTransaction(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='payment_transactions') 
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=100, unique=True, help_text="Unique transaction reference from Paystack")
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('success', 'Success'),
            ('failed', 'Failed'),
            ('abandoned', 'Abandoned'),
        ],
        default='pending'
    )
    gateway_response = models.JSONField(blank=True, null=True, help_text="Full response from payment gateway")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Payment Transaction"
        verbose_name_plural = "Payment Transactions"

    def __str__(self):
        return f"Transaction {self.reference} for {self.user.username} - {self.status}"
