from workflows.utils.sanitization import sanitize_pii


class TestSanitizePII:
    def test_redacts_phone(self):
        event = {"phone": "+5511999999999", "msg": "hello"}
        result = sanitize_pii(None, "info", event)
        assert result["phone"] == "***REDACTED***"
        assert result["msg"] == "hello"

    def test_redacts_email(self):
        event = {"email": "user@example.com"}
        result = sanitize_pii(None, "info", event)
        assert result["email"] == "***REDACTED***"

    def test_redacts_name(self):
        event = {"name": "Rodrigo Franco"}
        result = sanitize_pii(None, "info", event)
        assert result["name"] == "***REDACTED***"

    def test_redacts_cpf(self):
        event = {"cpf": "123.456.789-00"}
        result = sanitize_pii(None, "info", event)
        assert result["cpf"] == "***REDACTED***"

    def test_redacts_api_key(self):
        event = {"api_key": "sk-secret"}
        result = sanitize_pii(None, "info", event)
        assert result["api_key"] == "***REDACTED***"

    def test_redacts_nested_dict(self):
        event = {"user_data": {"phone": "+5511999999999", "age": 25}}
        result = sanitize_pii(None, "info", event)
        assert result["user_data"]["phone"] == "***REDACTED***"
        assert result["user_data"]["age"] == 25

    def test_redacts_deeply_nested_dict(self):
        event = {"data": {"user": {"phone": "+5511999999999", "age": 25}}}
        result = sanitize_pii(None, "info", event)
        assert result["data"]["user"]["phone"] == "***REDACTED***"
        assert result["data"]["user"]["age"] == 25

    def test_redacts_list_of_dicts(self):
        event = {"users": [{"phone": "123", "id": 1}, {"email": "a@b.com", "id": 2}]}
        result = sanitize_pii(None, "info", event)
        assert result["users"][0]["phone"] == "***REDACTED***"
        assert result["users"][0]["id"] == 1
        assert result["users"][1]["email"] == "***REDACTED***"
        assert result["users"][1]["id"] == 2

    def test_preserves_non_sensitive(self):
        event = {"action": "login", "status": "success"}
        result = sanitize_pii(None, "info", event)
        assert result == {"action": "login", "status": "success"}
