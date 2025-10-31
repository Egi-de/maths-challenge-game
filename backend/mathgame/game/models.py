from django.db import models

class User(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    total_score = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.name} ({self.email})"

class Question(models.Model):
    text = models.CharField(max_length=255)
    answer = models.FloatField()
    difficulty = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[D{self.difficulty}] {self.text}"

class Score(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="scores")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, null=True)
    points = models.IntegerField()
    time_taken = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.name}: +{self.points} pts"
