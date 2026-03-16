"""Tests for ErrorLog model and ErrorLogAdmin (Story 7.3, AC #1, #3)."""

import pytest
from django.contrib.admin.sites import AdminSite

from workflows.admin import ErrorLogAdmin
from workflows.models import ErrorLog, User


@pytest.mark.django_db
class TestErrorLogModel:
    """Tests for ErrorLog model."""

    @pytest.fixture
    def user(self):
        return User.objects.create(phone="5511999999999")

    def test_create_error_log(self, user):
        """ErrorLog pode ser criado com todos os campos."""
        error_log = ErrorLog.objects.create(
            user=user,
            node="orchestrate_llm",
            error_type="GraphNodeError",
            error_message="LLM timeout",
            trace_id="abc-123",
        )
        assert error_log.pk is not None
        assert error_log.node == "orchestrate_llm"
        assert error_log.error_type == "GraphNodeError"
        assert error_log.error_message == "LLM timeout"
        assert error_log.trace_id == "abc-123"
        assert error_log.created_at is not None

    def test_create_error_log_without_user(self):
        """ErrorLog pode ser criado sem user (erro antes de identificação)."""
        error_log = ErrorLog.objects.create(
            user=None,
            node="identify_user",
            error_type="Exception",
            error_message="Phone not found",
            trace_id="def-456",
        )
        assert error_log.pk is not None
        assert error_log.user is None

    def test_create_error_log_empty_trace_id(self, user):
        """ErrorLog aceita trace_id vazio (default)."""
        error_log = ErrorLog.objects.create(
            user=user,
            node="send_whatsapp",
            error_type="TimeoutError",
            error_message="Request timeout",
        )
        assert error_log.trace_id == ""

    def test_str_representation(self, user):
        """ErrorLog __str__ retorna representação legível."""
        error_log = ErrorLog.objects.create(
            user=user,
            node="orchestrate_llm",
            error_type="GraphNodeError",
            error_message="test",
        )
        assert str(error_log) == "ErrorLog(orchestrate_llm, GraphNodeError)"

    def test_db_table(self):
        """Model usa db_table='error_logs'."""
        assert ErrorLog._meta.db_table == "error_logs"

    def test_indexes(self):
        """Indexes existem em node e -created_at."""
        index_fields = [tuple(idx.fields) for idx in ErrorLog._meta.indexes]
        assert ("node",) in index_fields
        assert ("-created_at",) in index_fields

    def test_user_set_null_on_delete(self, user):
        """User deletion sets ErrorLog.user to NULL (não deleta o log)."""
        ErrorLog.objects.create(
            user=user,
            node="test",
            error_type="Test",
            error_message="test",
        )
        user.delete()
        error_log = ErrorLog.objects.first()
        assert error_log is not None
        assert error_log.user is None

    def test_related_name(self, user):
        """FK user com related_name='error_logs'."""
        ErrorLog.objects.create(
            user=user,
            node="test",
            error_type="Test",
            error_message="test",
        )
        assert user.error_logs.count() == 1


@pytest.mark.django_db
class TestErrorLogAdmin:
    """Tests for ErrorLogAdmin registration."""

    def test_admin_registered(self):
        """ErrorLog registrado no Django Admin."""
        from django.contrib.admin import site

        assert ErrorLog in site._registry

    def test_list_display(self):
        admin_obj = ErrorLogAdmin(ErrorLog, AdminSite())
        assert "node" in admin_obj.list_display
        assert "error_type" in admin_obj.list_display
        assert "user" in admin_obj.list_display
        assert "trace_id" in admin_obj.list_display
        assert "created_at" in admin_obj.list_display

    def test_list_filter(self):
        admin_obj = ErrorLogAdmin(ErrorLog, AdminSite())
        assert "node" in admin_obj.list_filter
        assert "error_type" in admin_obj.list_filter
        assert "created_at" in admin_obj.list_filter

    def test_date_hierarchy(self):
        admin_obj = ErrorLogAdmin(ErrorLog, AdminSite())
        assert admin_obj.date_hierarchy == "created_at"

    def test_search_fields(self):
        admin_obj = ErrorLogAdmin(ErrorLog, AdminSite())
        assert "trace_id" in admin_obj.search_fields
        assert "error_message" in admin_obj.search_fields

    def test_raw_id_fields(self):
        admin_obj = ErrorLogAdmin(ErrorLog, AdminSite())
        assert "user" in admin_obj.raw_id_fields

    def test_readonly_fields(self):
        admin_obj = ErrorLogAdmin(ErrorLog, AdminSite())
        expected = ("user", "node", "error_type", "error_message", "trace_id", "created_at")
        for field in expected:
            assert field in admin_obj.readonly_fields
