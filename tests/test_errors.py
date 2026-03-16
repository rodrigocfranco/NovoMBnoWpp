from workflows.utils.errors import (
    AppError,
    AuthenticationError,
    ExternalServiceError,
    GraphNodeError,
    RateLimitError,
    ValidationError,
)


class TestAppError:
    def test_app_error(self):
        err = AppError("something broke")
        assert err.message == "something broke"
        assert err.details == {}
        assert str(err) == "something broke"

    def test_app_error_with_details(self):
        err = AppError("fail", details={"field": "name"})
        assert err.details == {"field": "name"}


class TestValidationError:
    def test_is_app_error(self):
        err = ValidationError("invalid input")
        assert isinstance(err, AppError)
        assert err.message == "invalid input"


class TestAuthenticationError:
    def test_is_app_error(self):
        err = AuthenticationError("not allowed")
        assert isinstance(err, AppError)


class TestRateLimitError:
    def test_retry_after(self):
        err = RateLimitError("too fast", retry_after=60)
        assert err.retry_after == 60
        assert isinstance(err, AppError)


class TestExternalServiceError:
    def test_service_attribute(self):
        err = ExternalServiceError("WhatsApp", "timeout")
        assert err.service == "WhatsApp"
        assert "WhatsApp" in str(err)
        assert isinstance(err, AppError)


class TestGraphNodeError:
    def test_node_attribute(self):
        err = GraphNodeError("identify_user", "user not found")
        assert err.node == "identify_user"
        assert "identify_user" in str(err)
        assert isinstance(err, AppError)
