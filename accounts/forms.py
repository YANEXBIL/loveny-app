from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms import inlineformset_factory 
from .models import UserProfile, ProfileImage, GENDER_CHOICES, SEEKING_CHOICES, LOOKING_FOR_CHOICES # Corrected: USER_TYPE_CHOICES to LOOKING_FOR_CHOICES
from django.core.files.base import ContentFile 
import os 
from django.conf import settings 
from django.db import transaction 

# Define common Tailwind classes for input fields
COMMON_INPUT_CLASSES = 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-pink-500 focus:border-pink-500 sm:text-sm'
COMMON_SELECT_CLASSES = 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-pink-500 focus:border-pink-500 sm:text-sm'
COMMON_TEXTAREA_CLASSES = 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-pink-500 focus:border-pink-500 sm:text-sm'

# Define your custom widget class to remove "Currently:" and "Clear"
class CustomClearableFileInput(forms.ClearableFileInput):
    template_name = 'forms/widgets/custom_clearable_file_input.html'


# Custom User Creation Form (for registration)
class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = UserProfile 
        # Corrected: 'user_type' to 'looking_for'
        fields = ('username', 'email', 'first_name', 'last_name', 'looking_for', 'gender', 'date_of_birth', 'location', 'phone_number')
        widgets = {
            'email': forms.EmailInput(attrs={'class': COMMON_INPUT_CLASSES}),
            'first_name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES}),
            'last_name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES}),
            # Corrected: 'user_type' to 'looking_for' and its choices
            'looking_for': forms.Select(choices=LOOKING_FOR_CHOICES, attrs={'class': COMMON_SELECT_CLASSES}),
            'gender': forms.Select(choices=GENDER_CHOICES, attrs={'class': COMMON_SELECT_CLASSES}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': COMMON_INPUT_CLASSES}),
            'location': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES}),
            'phone_number': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES}),
        }


# User Profile Form (for editing profile)
class UserProfileForm(forms.ModelForm):
    # This field will capture the ID of an existing ProfileImage instance
    # that the user wants to set as their main profile_picture.
    # It's a hidden input, so the user doesn't see it directly.
    # It will be populated by your JavaScript when an existing additional image is chosen.
    main_additional_image_id = forms.IntegerField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = UserProfile
        fields = (
            'first_name', 'last_name', 'bio', 'gender', 'date_of_birth', 'profile_picture', 'location',
            'looking_for', 'seeking', 'phone_number', # Corrected: 'user_type' to 'looking_for'
            # 'interests' # TEMPORARILY COMMENTED OUT FOR MIGRATION
        )
        widgets = {
            'first_name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES}),
            'last_name': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES}),
            'bio': forms.Textarea(attrs={'class': f"{COMMON_TEXTAREA_CLASSES} h-24", 'rows': 4}), 
            'gender': forms.Select(choices=GENDER_CHOICES, attrs={'class': COMMON_SELECT_CLASSES}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': COMMON_INPUT_CLASSES}),
            'location': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES}), 
            # Corrected: 'user_type' to 'looking_for' and its choices
            'looking_for': forms.Select(choices=LOOKING_FOR_CHOICES, attrs={'class': COMMON_SELECT_CLASSES}),
            'seeking': forms.Select(choices=SEEKING_CHOICES, attrs={'class': COMMON_SELECT_CLASSES}),
            'phone_number': forms.TextInput(attrs={'class': COMMON_INPUT_CLASSES}),
            # Use the custom widget here for profile_picture
            'profile_picture': CustomClearableFileInput(attrs={'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-pink-50 file:text-pink-700 hover:file:bg-pink-100'}),
        }

    # Add the __init__ method to accept the 'user' argument
    def __init__(self, *args, **kwargs):
        # Pop the 'user' keyword argument before calling the parent constructor
        self.user = kwargs.pop('user', None) 
        super().__init__(*args, **kwargs)

        # You can now use self.user in your form's logic if needed, for example:
        # if self.user and self.user.is_staff:
        #    self.fields['some_admin_field'].required = True

    def clean_profile_picture(self):
        """
        Custom cleaning method to handle setting the main profile_picture
        from an existing additional image, if main_additional_image_id is provided.
        Prioritizes a direct file upload over selecting from gallery.
        """
        profile_picture = self.cleaned_data.get('profile_picture')
        main_additional_image_id = self.cleaned_data.get('main_additional_image_id')
        user_profile = self.instance # The UserProfile instance being edited

        # 1. Prioritize a newly uploaded profile_picture directly through its field
        if profile_picture:
            return profile_picture

        # 2. If no new profile_picture file, check if an existing additional image was selected
        if main_additional_image_id:
            try:
                # Fetch the ProfileImage instance using the provided ID and ensure it belongs to the current user
                selected_image = ProfileImage.objects.get(id=main_additional_image_id, user_profile=user_profile)
                
                # It's crucial to read the content of the file and wrap it in ContentFile
                # for Django's ImageField to properly save it as a new file object.
                # This makes a copy rather than just linking the path.
                image_path = os.path.join(settings.MEDIA_ROOT, str(selected_image.image))
                
                # Check if the file actually exists on disk before trying to open it
                if os.path.exists(image_path):
                    with open(image_path, 'rb') as f:
                        # Give it a name; you might want to prepend something like 'profile_'
                        # to distinguish it or ensure uniqueness if original name clashes.
                        # For now, using the original basename.
                        content = ContentFile(f.read(), name=os.path.basename(image_path))
                    return content
                else:
                    self.add_error('main_additional_image_id', 'Selected gallery image file is missing on the server.')
                    return None 
            except ProfileImage.DoesNotExist:
                # If the image ID is invalid or doesn't belong to the user, add an error
                self.add_error('main_additional_image_id', 'Selected gallery image is invalid or does not belong to your profile.')
                return None 
            
        # 3. If neither a new file was uploaded nor an existing one selected,
        # return the current profile_picture value (could be None or existing image)
        # This preserves the existing profile picture if no change is intended.
        # If the user explicitly clears the profile picture and doesn't replace it,
        # you might want different logic (e.g., setting it to default).
        return user_profile.profile_picture if user_profile.pk else None


    def clean(self):
        """
        Global clean method for additional validation across fields.
        """
        cleaned_data = super().clean()
        return cleaned_data


# Form for a single ProfileImage
class ProfileImageForm(forms.ModelForm):
    # This field is used to mark an existing image for deletion
    DELETE = forms.BooleanField(required=False, initial=False,
                                  widget=forms.CheckboxInput(attrs={'class': 'form-checkbox h-4 w-4 text-pink-600 border-gray-300 rounded hidden-checkbox'})) 

    class Meta:
        model = ProfileImage
        fields = ['image', 'order'] 
        widgets = {
            'image': forms.FileInput(attrs={'class': 'hidden'}), 
            'order': forms.HiddenInput(), 
        }

# Formset for handling multiple ProfileImages related to a UserProfile
ProfileImageFormSet = inlineformset_factory(
    UserProfile,    
    ProfileImage, 
    form=ProfileImageForm, 
    fields=['image', 'order'], 
    extra=0,        
    can_delete=True, 
    max_num=19,     # Corrected: Max 19 additional images (1 main + 19 gallery = 20 total)
    min_num=0,      
)
