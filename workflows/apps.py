import atexit

import structlog
from django.apps import AppConfig

from workflows.providers.langfuse import is_langfuse_enabled, shutdown_langfuse

_langfuse_atexit_registered = False


class WorkflowsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "workflows"

    def ready(self) -> None:
        global _langfuse_atexit_registered

        from workflows.utils.sanitization import sanitize_pii

        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                sanitize_pii,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

        # Story 7.2 (AC6): Graceful Langfuse shutdown on Cloud Run SIGTERM
        if is_langfuse_enabled() and not _langfuse_atexit_registered:
            atexit.register(shutdown_langfuse)
            _langfuse_atexit_registered = True
