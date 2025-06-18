# accounts/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.forms import inlineformset_factory
from .models import UserProfile, ProfileImage

# Define common Tailwind classes for input fields
COMMON_INPUT_CLASSES = 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-pink-500 focus:border-pink-500 sm:text-sm'
COMMON_SELECT_CLASSES = 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-pink-500 focus:border-pink-500 sm:text-sm'
COMMON_TEXTAREA_CLASSES = 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-pink-500 focus:border-pink-500 sm:text-sm'


# Custom User Creation Form (for registration)
class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = UserProfile
        fields = ('username', 'email', 'first_name', 'last_name', 'user_type', 'gender', 'date_of_birth', 'location', 'phone_number')
        widgets = {
            'email': forms.EmailInput(attrs={'class': COMMON_INPUT_CLASSES}),
            'first_name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES}),
            'last_name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES}),
            'user_type': forms.Select(attrs={'class': COMMON_SELECT_CLASSES}),
            'gender': forms.Select(attrs={'class': COMMON_SELECT_CLASSES}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': COMMON_INPUT_CLASSES}),
            'location': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES}),
            'phone_number': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES}),
        }


# User Profile Form (for editing profile)
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = (
            'first_name', 'last_name', 'bio', 'gender', 'date_of_birth', 'profile_picture', 'location',
            'user_type', 'seeking', 'phone_number'
        )
        widgets = {
            'first_name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES}),
            'last_name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES}),
            'bio': forms.Textarea(attrs={'class': f"{COMMON_TEXTAREA_CLASSES} h-24", 'rows': 4}), # Adjusted for height
            'gender': forms.Select(attrs={'class': COMMON_SELECT_CLASSES}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': COMMON_INPUT_CLASSES}),
            'location': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES}),
            'user_type': forms.Select(attrs={'class': COMMON_SELECT_CLASSES}),
            'seeking': forms.Select(attrs={'class': COMMON_SELECT_CLASSES}),
            'phone_number': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES}),
            'profile_picture': forms.ClearableFileInput(attrs={'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-pink-50 file:text-pink-700 hover:file:bg-pink-100'}),
        }


# Form for a single ProfileImage
class ProfileImageForm(forms.ModelForm):
    class Meta:
        model = ProfileImage
        fields = ['image']
        widgets = {
            'image': forms.FileInput(attrs={'class': 'hidden'}) # Keep hidden for custom button in template
        }

# Formset for handling multiple ProfileImages related to a UserProfile
ProfileImageFormSet = inlineformset_factory(
    UserProfile,
    ProfileImage,
    form=ProfileImageForm,
    fields=['image'],
    extra=3, # Number of empty forms to display for new images
    can_delete=True,
    widgets={
        'image': forms.FileInput(attrs={'class': 'hidden'}) # Ensure this is also hidden
    }
)
