# accounts/urls.py
from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views
from .views import CustomLoginView, CustomLogoutView, SignUpView # Explicitly import class-based views

app_name = 'accounts' # CRITICAL: Defines the namespace for this app's URLs

urlpatterns = [
    # Basic User Authentication Views
    path('signup/', SignUpView.as_view(), name='signup'), # Using explicitly imported SignUpView
    path('login/', CustomLoginView.as_view(), name='login'), # Using explicitly imported CustomLoginView
    path('logout/', CustomLogoutView.as_view(), name='logout'), # Fixed typo: as_as_view() to as_view()
    
    # User Profile Views
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('profile/', views.profile_view, name='profile'), # General user profile view
    path('browse/', views.browse_profiles_view, name='browse_profiles'),
    # Changed path parameter from uuid:user_id to str:username to match views.py
    path('profile/<str:username>/', views.view_other_profile, name='view_user_profile'), 
    path('matches/', views.matches_view, name='matches_view'), # Make sure 'name' is defined
    path('like/<str:username>/', views.like_view, name='like_view'), # Added like_view with username parameter
    path('swipe/', views.swipe_profiles_view, name='swipe_profiles'), # Added swipe view

    # Subscription Plans View
    path('subscription-plans/', views.subscription_plans_view, name='subscription_plans'),

    # Payment Views
    # Added plan_id parameter to match initiate_payment_view in views.py
    path('initiate-payment/<int:plan_id>/', views.initiate_payment_view, name='initiate_payment'), 
    # CORRECTED: Changed path and view to reflect Paystack callback mechanism
    path('paystack-callback/', views.paystack_callback_view, name='paystack_callback'),

    # Homepage View
    path('', views.homepage_view, name='homepage'), # Root path for accounts app

    # Password Reset Views
    # Step 1: Request password reset link
    path('password_reset/',
         auth_views.PasswordResetView.as_view(
             template_name='accounts/password_reset/password_reset_form.html',
             email_template_name='accounts/password_reset/password_reset_email.html',
             subject_template_name='accounts/password_reset/password_reset_subject.txt',
             success_url=reverse_lazy('accounts:password_reset_done')
         ),
         name='password_reset'),

    # Step 2: Confirmation that email has been sent
    path('password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password_reset/password_reset_done.html'
         ),
         name='password_reset_done'),

    # Step 3: Enter new password (link in email)
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset/password_reset_confirm.html',
             success_url=reverse_lazy('accounts:password_reset_complete')
         ),
         name='password_reset_confirm'),

    # Step 4: Password has been successfully reset
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password_reset/password_reset_complete.html'
         ),
         name='password_reset_complete'),

    # AJAX URL for saving profile edits and images
    path('ajax/profile/save/', views.ajax_profile_save, name='ajax_profile_save'), # Added this path
]
