# accounts/urls.py

from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views # Import Django's default auth views

app_name = 'accounts' # This defines the namespace for all URLs in this file

urlpatterns = [
    # Authentication URLs
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('signup/', views.SignUpView.as_view(), name='signup'),

    # Password Reset URLs (Django's built-in views)
    # Corrected 'as_as_view' to 'as_view' for robustness
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='accounts/password_reset/password_reset_form.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='accounts/password_reset/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset/password_reset_complete.html'), name='password_reset_complete'),

    # Profile Management
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('profile/ajax-save/', views.ajax_profile_save, name='ajax_profile_save'), # For AJAX profile updates
    path('profile/delete/', views.account_delete, name='account_delete'), # Account deletion confirmation page

    # Other User Profiles
    path('profile/<str:username>/', views.view_other_profile, name='view_user_profile'),

    # Core App Functionality
    path('', views.homepage_view, name='home'), # This is the homepage for the 'accounts' app
    path('browse/', views.browse_profiles_view, name='browse_profiles'), # Main browsing view
    path('swipe/', views.swipe_profiles_view, name='swipe_profiles'), # Separate swipe view
    path('like/<str:username>/', views.like_view, name='like_user'),
    path('matches/', views.matches_view, name='matches_view'), # URL name for matches view

    # Subscription Plans & Payments (as they were likely on June 29th)
    path('subscription-plans/', views.choose_plan_view, name='choose_plan'),
    path('initiate-payment/<int:plan_id>/', views.initiate_payment_view, name='initiate_payment'),
    path('verify-payment/', views.verify_payment_view, name='verify_payment'),
    path('payment-success/', views.payment_success_view, name='payment_success'),
    path('payment-failed/', views.payment_failed_view, name='payment_failed'),
]
