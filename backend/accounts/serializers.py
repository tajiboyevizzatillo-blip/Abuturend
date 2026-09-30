from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.exceptions import APIException

User = get_user_model()


class InvalidCredentials(APIException):
    status_code = 401
    default_detail = "Login yoki parol noto'g'ri."
    default_code = "invalid_credentials"


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "role",
            "phone",
            "first_name",
            "last_name",
            "date_joined",
            "is_staff",
        ]
        read_only_fields = ["id", "date_joined", "is_staff", "role"]


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=User.Role.choices, default=User.Role.STUDENT)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Bu login band.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        requester = request.user if request else None
        can_staff = requester is not None and requester.is_superuser
        if not can_staff and attrs.get("role") != User.Role.STUDENT:
            raise serializers.ValidationError(
                {"role": "Ommaviy ro'yxatdan o'tishda faqat 'abituriyent' roli ruxsat etiladi."}
            )
        # Same policy as ChangePasswordSerializer. Skipping this on registration is
        # what let a one-character password through. Re-key the Django messages
        # onto "password" so the register form can show them next to the field.
        candidate = User(
            username=attrs.get("username", ""),
            email=attrs.get("email", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        try:
            validate_password(attrs.get("password"), candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        try:
            with transaction.atomic():
                user.save()
        except IntegrityError:
            raise serializers.ValidationError(
                {"username": "Bu login band."}
            )
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")
        if not username or not password:
            raise InvalidCredentials()

        user = authenticate(
            request=self.context.get("request"),
            username=username,
            password=password,
        )
        if user is None:
            raise InvalidCredentials()
        if not user.is_active:
            raise InvalidCredentials("Hisob faollashtirilmagan.")

        attrs["user"] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Joriy parol noto'g'ri.")
        return value

    def validate_new_password(self, value):
        # Django raises its own ValidationError, which DRF would not turn into a
        # 400 — re-key it onto the field instead of surfacing a 500.
        try:
            validate_password(value, self.context["request"].user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value