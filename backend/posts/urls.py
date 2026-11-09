from django.urls import path

from posts import views

urlpatterns = [
    path("post-images", views.PostImageUploadView.as_view()),
    path("post-images/<int:pk>/content", views.PostImageContentView.as_view()),
    path("posts", views.PostCollectionView.as_view()),
    path("posts/<int:pk>", views.PostDetailView.as_view()),
    path("posts/<int:pk>/withdraw", views.PostWithdrawView.as_view()),
    path("posts/<int:pk>/restore", views.PostRestoreView.as_view()),
    path("posts/<int:pk>/resolve", views.PostResolveView.as_view()),
    path("posts/<int:pk>/reopen", views.PostReopenView.as_view()),
]
