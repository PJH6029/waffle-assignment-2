from rest_framework import serializers

from seminar.models import UserSeminar, Seminar

class SeminarSerializer(serializers.ModelSerializer):
    time = serializers.TimeField(format="%H:%M", input_formats=['%H:%M'])
    online = serializers.BooleanField(default=True)
    instructors = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()

    class Meta:
        model = Seminar
        fields = (
            'id',
            'name',
            'capacity',
            'count',
            'time',
            'online',
            'instructors',
            'participants',
        )



    def get_instructors(self, seminar):
        instructors_seminars = seminar.user_seminars.filter(role=UserSeminar.INSTRUCTOR)

        return InstructorOfSeminarSerializer(instructors_seminars, many=True, context=self.context).data

    def get_participants(self, seminar):
        participants_seminars = seminar.user_seminars.filter(role=UserSeminar.PARTICIPANT)

        return ParticipantOfSeminarSerializer(participants_seminars, many=True, context=self.context).data

    # TODO validation?



class SeminarAsParticipantSerializer(serializers.ModelSerializer):
    # source: 값을 가져올 위치 : 접근위치는 UserSeminar의 attribute부터
    joined_at = serializers.DateTimeField(source='created_at')
    id = serializers.IntegerField(source='seminar.id')
    name = serializers.CharField(source='seminar.name')

    '''
    id 접근 등과 관련해서, 아래 코드와 동일
    id = serializers.SerializerMethodField()
    
    def get_id(self, user_seminar):
        return user_seminar.seminar.id
    '''

    class Meta:
        # 특정 user가 담당하고있는(즉, 그 user가 포함된) UserSeminar의 row들을 모두 모아놓음(many=True) 또는 그 row
        model = UserSeminar
        fields = (
            'id',
            'name',
            'joined_at',
            'is_active',
            'dropped_at',
        )


class SeminarAsInstructorSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='seminar.id')
    name = serializers.CharField(source='seminar.name')
    joined_at = serializers.DateTimeField(source='created_at')

    class Meta:
        model = UserSeminar
        fields = (
            'id',
            'name',
            'joined_at',
        )


class InstructorOfSeminarSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='user.id')
    username = serializers.CharField(source='user.username')
    email = serializers.EmailField(source='user.email')
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')

    joined_at = serializers.DateTimeField(source='created_at')

    class Meta:
        model = UserSeminar
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'joined_at',
        )


class ParticipantOfSeminarSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='user.id')
    username = serializers.CharField(source='user.username')
    email = serializers.EmailField(source='user.email')
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')

    joined_at = serializers.DateTimeField(source='created_at')
    # is_active = serializers.BooleanField()

    class Meta:
        model = UserSeminar
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'joined_at',
            'is_active',
            'dropped_at',
        )
