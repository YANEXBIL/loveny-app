# accounts/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.forms import inlineformset_factory # Import inlineformset_factory
from .models import UserProfile, ProfileImage # Import ProfileImage model

# Custom User Creation Form (for registration)
class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = UserProfile
        fields = ('username', 'email', 'first_name', 'last_name', 'user_type', 'gender', 'date_of_birth', 'location', 'phone_number')

# User Profile Form (for editing profile)
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = (
            'first_name', 'last_name', 'bio', 'gender', 'date_of_birth', 'profile_picture', 'location',
            'user_type', 'seeking', 'phone_number'
        )
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 4}),
        }

# Form for a single ProfileImage
class ProfileImageForm(forms.ModelForm):
    class Meta:
        model = ProfileImage
        fields = ['image']

# Formset for handling multiple ProfileImages related to a UserProfile
# This will be used in the profile_edit_view to allow adding/editing/deleting multiple images
ProfileImageFormSet = inlineformset_factory(
    UserProfile, # Parent model
    ProfileImage, # Child model
    form=ProfileImageForm,
    fields=['image'],
    extra=3, # Number of empty forms to display for new images
    can_delete=True, # Allow deleting existing images
    widgets={
        'image': forms.FileInput(attrs={'class': 'hidden'}) # Hide default file input for custom styling
    }
)
