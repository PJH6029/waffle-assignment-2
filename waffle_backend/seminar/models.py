from django.db import models
from django.contrib.auth.models import User

# Create your models here.


class Seminar(models.Model):
    name = models.CharField(max_length=100, db_index=True)
    capacity = models.PositiveSmallIntegerField()
    count = models.PositiveSmallIntegerField()
    time = models.TimeField()
    online = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True) # TODO db_index=True
    updated_at = models.DateTimeField(auto_now=True)


class UserSeminar(models.Model):
    PARTICIPANT = 'participant'
    INSTRUCTOR = 'instructor'

    ROLE_CHOICES = [
        (PARTICIPANT, PARTICIPANT),
        (INSTRUCTOR, INSTRUCTOR),  # TODO (PARTICIPANT, INSTRUCTOR) ??
    ]

    ROLES = (PARTICIPANT, INSTRUCTOR)

    # related_name: 역참조시 이용(User -> UserSeminar 접근할 때)
    user = models.ForeignKey(User, related_name='user_seminars', on_delete=models.CASCADE)
    seminar = models.ForeignKey(Seminar, related_name='user_seminars', on_delete=models.CASCADE)
    role = models.CharField(max_length=100, choices=ROLE_CHOICES, db_index=True)

    is_active = models.BooleanField(default=True)

    dropped_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (
            ('user', 'seminar')
        )
