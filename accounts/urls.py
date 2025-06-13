# accounts/urls.py

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views # Import Django's default auth views

urlpatterns = [
    path('', views.homepage_view, name='homepage'), # Landing page
    path('register/', views.SignUpView.as_view(), name='register'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'), # Use custom logout view
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('browse/', views.browse_profiles_view, name='browse_profiles'), # Browse profiles
    path('swipe/', views.swipe_profiles_view, name='swipe_profiles'), # New: Swipe Profiles
    path('profile/<str:username>/', views.view_other_profile, name='view_other_profile'), # View specific profile
    path('like/<str:username>/', views.like_view, name='like_user'), # URL for liking/unliking a user
    path('matches/', views.matches_view, name='matches'), # URL for displaying mutual matches
    path('chat/<str:username>/', views.chat_room_view, name='chat_room'), # URL for individual chat room
    path('message_gate/<str:username>/', views.message_gate_view, name='message_gate'), # Gate for messaging
    path('plans/', views.subscription_plans_view, name='subscription_plans'), # Subscription plans page
    path('plan/pay/<int:plan_id>/', views.initiate_payment_view, name='initiate_payment'), # Initiate payment
    path('paystack_callback/', views.paystack_callback_view, name='paystack_callback'), # Paystack callback URL
]
