from django.contrib import admin
from .models import User, Question, Score

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "total_score")
    search_fields = ("name", "email")

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "text", "answer", "difficulty", "created_at")

@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "question", "points", "time_taken", "created_at")
