from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response


from seminar.models import Seminar, UserSeminar
from seminar.serializers import SeminarSerializer
from user.permissions import IsParticipant, IsInstructor

# Create your views here.
class SeminarViewSet(viewsets.GenericViewSet):
    queryset = Seminar.objects.all()
    serializer_class = SeminarSerializer
    permission_classes = (IsAuthenticated, )


    def get_permissions(self):
        if self.action in ('create', 'update'):
            return (IsInstructor(), )
        elif self.action == 'user' and self.request.method == 'DELETE':
            return (IsParticipant(), )
        return super(SeminarViewSet, self).get_permissions()


    # POST api/v1/seminar/
    def create(self, request):
        print("DEBUG: SeminarViewSet.create()")
        user = request.user
        # print(type(user))

        if user.user_seminars.filter(role=UserSeminar.INSTRUCTOR).exists():
            return Response({"error": "You're in charge of another seminar"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        seminar = serializer.save()

        UserSeminar.objects.create(
            user=user,
            seminar=seminar,
            role=UserSeminar.INSTRUCTOR
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # PUT api/v1/seminar/{seminar_id}/
    def update(self, request, pk=None):
        print("DEBUG: SeminarViewSet.update()")
        user = request.user
        seminar = self.get_object()

        if not user.user_seminars.filter(seminar=seminar, role=UserSeminar.INSTRUCTOR).exists():
            return Response({"error": "You're not in charge of this seminar"}, status=status.HTTP_403_FORBIDDEN)

        data = request.data

        serializer = self.get_serializer(seminar, data=data, partial=True)
        serializer.is_valid(raise_exception=True)

        participant_count = seminar.user_seminars.filter(role=UserSeminar.PARTICIPANT, is_active=True).count()
        if data.get('capacity') and int(data.get('capacity')) < participant_count:
            return Response({"error": "Capacity should be bigger than the number of participants"}, status=status.HTTP_400_BAD_REQUEST)

        serializer.update(seminar, serializer.validated_data)
        return Response(serializer.data)

    # GET api/v1/seminar/{seminar_id}/
    def retrieve(self, request, pk=None):
        print("DEBUG: SeminarViewSet.retrieve()")

        seminar = self.get_object()
        return Response(self.get_serializer(seminar).data)

    # GET api/v1/seminar/
    def list(self, request):
        print("DEBUG: SeminarViewSet.list()")

        name = request.query_params.get('name')
        order = request.query_params.get('order')

        seminars = self.get_queryset()
        if name:
            seminars = seminars.filter(name__icontains=name)

        if order == 'earliest':
            seminars = seminars.order_by('created_at')
        else:
            seminars = seminars.order_by('-created_at')

        return Response(self.get_serializer(seminars, many=True).data)

    # POST or DELETE api/v1/seminar/{seminar_id}/user/
    @action(detail=True, methods=['POST', 'DELETE'])
    def user(self, request, pk):
        print("DEBUG: SeminarViewSet.user()")

        seminar = self.get_object()
        if not seminar:
            return Response({"error": "Seminar with that pk does not exist"}, status=status.HTTP_404_NOT_FOUND)

        if self.request.method == 'POST':
            return self._join_seminar(seminar)
        elif self.request.method == 'DELETE':
            return self._drop_seminar(seminar)

    def _join_seminar(self, seminar):
        user = self.request.user
        role = self.request.data.get('role')

        if role not in UserSeminar.ROLES:
            return Response({"error": "Role should be either participant or instructor"}, status=status.HTTP_400_BAD_REQUEST)

        if user.user_seminars.filter(seminar=seminar).exists():
            return Response({"error": "You've joined this seminar"}, status=status.HTTP_400_BAD_REQUEST)

        if role == UserSeminar.PARTICIPANT:
            if not hasattr(user, UserSeminar.PARTICIPANT):
                return Response({"error": "You're not a participant"}, status=status.HTTP_403_FORBIDDEN)
            if not user.participant.accepted:
                return Response({"error": "You're not accepted"}, status=status.HTTP_403_FORBIDDEN)

            with transaction.atomic():
                # 동시에 수행
                participant_count = seminar.user_seminars.select_for_update().filter(
                    role=UserSeminar.PARTICIPANT, is_active=True
                ).count()
                if participant_count >= seminar.capacity:
                    return Response({"error": "This seminar is already full"}, status=status.HTTP_400_BAD_REQUEST)

                UserSeminar.objects.create(
                    user=user,
                    seminar=seminar,
                    role=UserSeminar.PARTICIPANT
                )

        elif role == UserSeminar.INSTRUCTOR:
            if not hasattr(user, UserSeminar.INSTRUCTOR):
                return Response({"error": "You're not a instructor"}, status=status.HTTP_403_FORBIDDEN)
            if user.user_seminars.filter(role=UserSeminar.INSTRUCTOR).exists():
                return Response({"error": "You're in charge of another seminar"}, status=status.HTTP_400_BAD_REQUEST)

            UserSeminar.objects.create(
                user=user,
                seminar=seminar,
                role=UserSeminar.INSTRUCTOR,
            )

        return Response(self.get_serializer(seminar).data, status=status.HTTP_201_CREATED)

    def _drop_seminar(self, seminar):
        user = self.request.user
        role = self.request.get('role')

        if role not in UserSeminar.ROLES:
            return Response({"error": "Role should be either participant or instructor"}, status=status.HTTP_400_BAD_REQUEST)

        if role == UserSeminar.INSTRUCTOR:
            return Response({"error": "Instructor cannot drop the seminar"}, status=status.HTTP_403_FORBIDDEN)

        user_seminar = user.user_seminars.filter(seminar=seminar).last()

        if user_seminar and user_seminar.is_active:
            user_seminar.dropped_at = timezone.now()
            user_seminar.is_active = False
            user_seminar.save()

        seminar.refresh_from_db()
        return Response(self.get_serializer(seminar).data)


