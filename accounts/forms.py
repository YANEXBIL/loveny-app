# accounts/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import UserProfile # Import your custom UserProfile model

# Custom User Creation Form (for registration)
class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = UserProfile
        # Ensure all required fields are listed for registration
        fields = ('username', 'email', 'user_type', 'gender', 'date_of_birth', 'location', 'phone_number') # Added phone_number

# User Profile Form (for editing profile)
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        # List all fields that can be edited by the user on their profile page
        fields = (
            'bio', 'gender', 'date_of_birth', 'profile_picture', 'location',
            'user_type', 'seeking', 'phone_number' # Added phone_number
        )
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 4}),
        }
