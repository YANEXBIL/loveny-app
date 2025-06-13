# accounts/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import UserProfile

class CustomUserCreationForm(UserCreationForm):
    """
    A custom form for creating new users.
    Extends Django's UserCreationForm to include fields from UserProfile.
    """
    # Add date_of_birth to the registration form
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False,
        label="Date of Birth"
    )

    class Meta(UserCreationForm.Meta):
        model = UserProfile
        # Add 'date_of_birth' and any other custom fields you want during initial registration
        fields = UserCreationForm.Meta.fields + ('date_of_birth',)


class UserProfileForm(forms.ModelForm):
    """
    Form for updating a user's profile information.
    """
    class Meta:
        model = UserProfile
        # Fields that can be updated on the profile page
        fields = [
            'bio',
            'gender',
            'date_of_birth',
            'profile_picture',
            'location',
            'user_type',
            'seeking',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'user_type': 'I am looking for:',
            'seeking': 'Who are you seeking (gender)?:' # Updated label for clarity
        }
