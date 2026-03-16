"""Tests for Feedback model and FeedbackAdmin (Story 6.1, AC #2, #4)."""

import pytest
from django.contrib.admin.sites import AdminSite

from workflows.admin import FeedbackAdmin
from workflows.models import Feedback, Message, User


@pytest.mark.django_db
class TestFeedbackModel:
    """Tests for Feedback model."""

    @pytest.fixture
    def user(self):
        return User.objects.create(phone="5511999999999")

    @pytest.fixture
    def message(self, user):
        return Message.objects.create(user=user, content="Resposta teste", role="assistant")

    def test_create_positive_feedback(self, user, message):
        """AC2: Feedback positivo pode ser salvo no banco."""
        feedback = Feedback.objects.create(
            message=message,
            user=user,
            rating="positive",
        )
        assert feedback.pk is not None
        assert feedback.rating == "positive"
        assert feedback.comment is None
        assert feedback.created_at is not None

    def test_create_negative_feedback(self, user, message):
        """AC2: Feedback negativo pode ser salvo no banco."""
        feedback = Feedback.objects.create(
            message=message,
            user=user,
            rating="negative",
        )
        assert feedback.rating == "negative"

    def test_create_feedback_with_comment(self, user, message):
        """AC3: Feedback com comentário pode ser salvo."""
        feedback = Feedback.objects.create(
            message=message,
            user=user,
            rating="negative",
            comment="Resposta incompleta",
        )
        assert feedback.comment == "Resposta incompleta"

    def test_feedback_str(self, user, message):
        """Feedback __str__ retorna representação legível."""
        feedback = Feedback.objects.create(
            message=message,
            user=user,
            rating="positive",
        )
        assert "Feedback" in str(feedback)

    def test_feedback_db_table(self):
        """AC4: Model usa db_table='feedbacks'."""
        assert Feedback._meta.db_table == "feedbacks"

    def test_feedback_indexes(self):
        """Indexes existem para user, created_at e rating."""
        index_fields = [tuple(idx.fields) for idx in Feedback._meta.indexes]
        assert ("user",) in index_fields
        assert ("-created_at",) in index_fields
        assert ("rating",) in index_fields

    def test_feedback_related_name_on_message(self, user, message):
        """FK message com related_name='feedbacks'."""
        Feedback.objects.create(message=message, user=user, rating="positive")
        assert message.feedbacks.count() == 1

    def test_feedback_related_name_on_user(self, user, message):
        """FK user com related_name='feedbacks'."""
        Feedback.objects.create(message=message, user=user, rating="positive")
        assert user.feedbacks.count() == 1

    def test_rating_choices(self):
        """Rating choices são positive, negative e comment."""
        choices = dict(Feedback.RATING_CHOICES)
        assert "positive" in choices
        assert "negative" in choices
        assert "comment" in choices
        assert len(choices) == 3


@pytest.mark.django_db
class TestFeedbackAdmin:
    """Tests for FeedbackAdmin registration (AC #4)."""

    def test_admin_registered(self):
        """AC4: Feedback registrado no Django Admin."""
        from django.contrib.admin import site

        assert Feedback in site._registry

    def test_list_display(self):
        admin = FeedbackAdmin(Feedback, AdminSite())
        assert "user" in admin.list_display
        assert "rating" in admin.list_display
        assert "has_comment" in admin.list_display
        assert "created_at" in admin.list_display

    def test_list_filter(self):
        admin = FeedbackAdmin(Feedback, AdminSite())
        assert "rating" in admin.list_filter

    def test_date_hierarchy(self):
        admin = FeedbackAdmin(Feedback, AdminSite())
        assert admin.date_hierarchy == "created_at"

    def test_search_fields(self):
        admin = FeedbackAdmin(Feedback, AdminSite())
        assert "user__phone" in admin.search_fields
        assert "comment" in admin.search_fields

    def test_raw_id_fields(self):
        admin = FeedbackAdmin(Feedback, AdminSite())
        assert "user" in admin.raw_id_fields
        assert "message" in admin.raw_id_fields

    def test_has_comment_display_true(self):
        """has_comment retorna True quando comment existe."""
        admin = FeedbackAdmin(Feedback, AdminSite())
        obj = Feedback(comment="Um comentário")
        assert admin.has_comment(obj) is True

    def test_has_comment_display_false(self):
        """has_comment retorna False quando comment é None."""
        admin = FeedbackAdmin(Feedback, AdminSite())
        obj = Feedback(comment=None)
        assert admin.has_comment(obj) is False

    def test_has_comment_display_empty(self):
        """has_comment retorna False quando comment é string vazia."""
        admin = FeedbackAdmin(Feedback, AdminSite())
        obj = Feedback(comment="")
        assert admin.has_comment(obj) is False
