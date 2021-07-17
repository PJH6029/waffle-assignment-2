from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from user.models import ParticipantProfile, InstructorProfile
from seminar.models import UserSeminar
from seminar.serializers import SeminarAsParticipantSerializer, SeminarAsInstructorSerializer


class UserSerializer(serializers.ModelSerializer):
    # TODO required: deserialize할 때만 확인??

    # read한다: db를 read한다 -> response를 준다
    # write한다: db에 write한다(create, update) -> request를 deserialize한다

    email = serializers.EmailField(allow_blank=False)
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    # read_only 친구들은 create, update 과정에서 사용되지 x (외부에 의해 db에 write되지 않음)
    last_login = serializers.DateTimeField(read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)

    participant = serializers.SerializerMethodField()
    instructor = serializers.SerializerMethodField()
    # write_only 친구들은 read할때 신경쓰지 x (즉, serialize할 때 이용되지 x == db에서 read해오지 x)
    role = serializers.ChoiceField(write_only=True, choices=UserSeminar.ROLES)

    # participant
    university = serializers.CharField(write_only=True, allow_blank=True, required=False)
    accepted = serializers.BooleanField(write_only=True, default=True, required=False)

    # instructor
    company = serializers.CharField(write_only=True, allow_blank=True, required=False)
    year = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = User
        # TODO deserialize할 때 들어올 수 있는 fields?

        # TODO request 받으면, deserialize해서 처리한 후 response에 넘길 정보를 serialize해서 보냄
        fields = (
            'id',
            'username',
            'email',
            'password',
            'first_name',
            'last_name',
            'last_login',
            'date_joined',

            'participant',
            'instructor',
            'role',
            'university',
            'accepted',
            'company',
            'year',
        )

    def get_participant(self, user):
        if hasattr(user, 'participant'):
            return ParticipantProfileSerializer(user.participant, context=self.context).data
        return None

    def get_instructor(self, user):
        if hasattr(user, 'instructor'):
            return InstructorProfileSerializer(user.instructor, context=self.context).data
        return None

    # 여기서 password라는 field를 hash
    def validate_password(self, value):
        return make_password(value)

    def validate(self, data):
        print("DEBUG: UserSerializer.validate()")
        # validate name fields
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        if bool(first_name) ^ bool(last_name):
            raise serializers.ValidationError("First name and last name should appear together.")
        if first_name and last_name and not (first_name.isalpha() and last_name.isalpha()):
            raise serializers.ValidationError("First name or last name should not have number.")

        # validate year
        # TODO unnecessary?

        year = data.get('year')
        if year and year <= 0:
            raise serializers.ValidationError("Year should be a positive number")


        # validate role
        role = data.get('role')
        if role == UserSeminar.PARTICIPANT:
            profile_serializer = ParticipantProfileSerializer(data=data, context=self.context)
            profile_serializer.is_valid(raise_exception=True)
        elif role == UserSeminar.INSTRUCTOR:
            # 사실, role의 field가 choicefield이므로, 마지막 else문은 절대로 도달하지 못함
            profile_serializer = InstructorProfileSerializer(data=data, context=self.context)
            profile_serializer.is_valid(raise_exception=True)
        # TODO role field는 required=True일텐데, data에 role없어도 그대로 넘어감??
        '''
        else:
            raise serializers.ValidationError("A role should be either participant or instructor")
        '''

        return data

    @transaction.atomic
    def create(self, validated_data):
        print("DEBUG: UserSerializer.create()")
        role = validated_data.pop('role')

        university = validated_data.pop('university', '')
        accepted = validated_data.pop('accepted', None)

        company = validated_data.pop('company', '')
        year = validated_data.pop('year', None)

        user = super(UserSerializer, self).create(validated_data)
        # 여기서 token이라는 attribute를 추가로 만들어줌
        # token을 기준으로 user의 authentication 진행
        Token.objects.create(user=user)

        if role == UserSeminar.PARTICIPANT:
            ParticipantProfile.objects.create(
                user=user,
                university=university,
                accepted=accepted
            )
        else:
            InstructorProfile.objects.create(
                user=user,
                company=company,
                year=year
            )
        return user

    @transaction.atomic
    def update(self, user, validated_data):
        print("DEBUG: UserSerializer.update()")

        # update할 때는 'participant' or 'instructor'라는 이름의 json 형식의 정보 자체가 있어야함
        if hasattr(user, UserSeminar.PARTICIPANT):
            # participant
            participant_profile = user.participant
            university = validated_data.pop('university')
            if university is not None:
                # 빈 스트링도 수정가능
                participant_profile.university = university
                participant_profile.save()
        if hasattr(user, UserSeminar.INSTRUCTOR):
            # instructor
            instructor_profile = user.instructor
            company = validated_data.pop('company')
            year = validated_data.pop('year')
            if company is not None or year:
                if company is not None:
                    instructor_profile.company = company
                if year:
                    instructor_profile.year = year
                instructor_profile.save()
        return super(UserSerializer, self).update(user, validated_data)


class ParticipantProfileSerializer(serializers.ModelSerializer):
    # default = True가 필요함. objects.create()에 accepted를 안주면 models.py에 의해 기본이 True이지만,
    # Serializer에서 accepted를 주므로 이 값으로 덮어씌워짐. 그런데, 이 Field의 기본값이 False이면 결국 db엔 False가 들어감
    accepted = serializers.BooleanField(default=True, required=False)
    seminars = serializers.SerializerMethodField(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = ParticipantProfile
        fields = (
            'id',
            'university',
            'accepted',
            'seminars',
            'user_id',  # write 용도?
        )

    def get_seminars(self, participant_profile):
        # participant profile에서 user로 넘어온 다음, user seminar 부르고, 거기서 filter
        # 즉, UserSeminar.objects.filter(user=participant_profile.user, role=UserSeminar.PARTICIPANT)와 같음
        participant_seminars = participant_profile.user.user_seminars.filter(role=UserSeminar.PARTICIPANT)

        # 여기는 존재 체크를 하면, return None에 의해, 빈 리스트조차 넘겨주지 않음 -> many=True에서는 그냥 이렇게
        return SeminarAsParticipantSerializer(participant_seminars, many=True, context=self.context).data


class InstructorProfileSerializer(serializers.ModelSerializer):
    # TODO 언제 Field 생성??
    charge = serializers.SerializerMethodField()

    class Meta:
        model = InstructorProfile
        fields = (
            'id',
            'company',
            'year',
            'charge',
        )

    def get_charge(self, instructor_profile):
        # last() 어차피 0개 아니면 1개일텐데, try handle하는 것 보단, last() 이용 -> 없으면 None 반환
        instructor_seminar = instructor_profile.user.user_seminars.filter(role=UserSeminar.INSTRUCTOR).last()
        if instructor_seminar:
            return SeminarAsInstructorSerializer(instructor_seminar, context=self.context).data
        return None
