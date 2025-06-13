# accounts/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser # Import AbstractUser
import os # Import os for default image path
from datetime import date # IMPORT THIS LINE


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

# Define user type choices including sugar daddy/mummy, hookup, and dating
USER_TYPE_CHOICES = [
    ('DATING', 'Dating'),
    ('HOOKUP', 'Hookup'),
    ('SUGAR_DADDY', 'Sugar Daddy'),
    ('SUGAR_MUMMY', 'Sugar Mummy'),
]

class UserProfile(AbstractUser):
    """
    Custom UserProfile model extending Django's AbstractUser.
    This allows us to add custom fields to the default User model.
    """
    # Personal Information
    bio = models.TextField(max_length=500, blank=True, null=True, help_text="Tell us about yourself.")
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to='profile_pics/',
        blank=True,
        null=True,
        default='profile_pics/default_avatar.png' # Set a default image path
    )
    location = models.CharField(max_length=100, blank=True, null=True)

    # Dating/Hookup/Sugar specific fields
    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default='DATING', # Default to general dating
        help_text="Are you looking for dating, hookups, or are you a sugar daddy/mummy?"
    )
    seeking = models.CharField(
        max_length=1,
        choices=SEEKING_CHOICES,
        blank=True,
        null=True,
        help_text="Who are you seeking?"
    )
    is_premium = models.BooleanField(default=False) # New field for premium status

    def __str__(self):
        """
        Returns the username as the string representation of the UserProfile object.
        """
        return self.username

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

# Model: Like
class Like(models.Model):
    """
    Represents a 'like' action between two UserProfile instances.
    A 'like' exists when 'liker' expresses interest in 'liked_user'.
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
        # Ensures that one user can only like another user once.
        unique_together = ('liker', 'liked_user')
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.liker.username} likes {self.liked_user.username}"

    def is_match(self):
        """
        Checks if this like creates a mutual match.
        A match occurs if the liked_user also likes the liker.
        """
        return Like.objects.filter(
            liker=self.liked_user,
            liked_user=self.liker
        ).exists()

# Model: Conversation (for chat)
class Conversation(models.Model):
    """
    Represents a private conversation between two users.
    Each conversation is unique to a pair of users.
    """
    user1 = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='conversations_initiated',
        help_text="The first participant in the conversation."
    )
    user2 = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='conversations_received',
        help_text="The second participant in the conversation."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="The date and time when the conversation was initiated."
    )

    class Meta:
        # Ensures that there's only one conversation between any two users,
        # regardless of which user is 'user1' or 'user2'.
        unique_together = ('user1', 'user2')
        ordering = ['-created_at']

    def __str__(self):
        return f"Conversation between {self.user1.username} and {self.user2.username}"

    @classmethod
    def get_or_create_conversation(cls, user_a, user_b):
        """
        Retrieves an existing conversation between user_a and user_b,
        or creates a new one if it doesn't exist.
        Ensures consistent ordering of users (user1 < user2 by ID) to prevent duplicates.
        """
        # Ensure user1 always has the smaller ID to maintain unique_together
        if user_a.id > user_b.id:
            user_a, user_b = user_b, user_a 

        conversation, created = cls.objects.get_or_create(
            user1=user_a,
            user2=user_b,
        )
        return conversation, created

# Model: Message (for chat)
class Message(models.Model):
    """
    Represents a single message within a conversation.
    """
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        help_text="The conversation this message belongs to."
    )
    sender = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        help_text="The user who sent this message."
    )
    content = models.TextField(
        help_text="The text content of the message."
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="The date and time when the message was sent."
    )

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {self.sender.username}: {self.content[:50]}..."


# New Models for Subscription and Payments
class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(help_text="Duration of the plan in days")
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (₦{self.price})"

class UserSubscription(models.Model):
    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s subscription to {self.plan.name if self.plan else 'N/A'}"

    def save(self, *args, **kwargs):
        if self.plan and not self.end_date:
            from datetime import timedelta
            self.end_date = self.start_date + timedelta(days=self.plan.duration_days)
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

    def __str__(self):
        return f"Transaction {self.reference} for {self.user.username} - {self.status}"
