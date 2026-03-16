"""Feature flag service for gradual traffic routing (Strangler Fig)."""

import hashlib

import structlog

from workflows.services.config_service import ConfigService
from workflows.utils.errors import ValidationError

logger = structlog.get_logger(__name__)


async def is_feature_enabled(user_id: str, feature: str) -> bool:
    """Check if feature is enabled for user via hash-based bucketing.

    Uses MD5 hash of user_id for deterministic, uniform distribution.
    Same user always gets same treatment for same rollout_percentage.

    Args:
        user_id: Unique user identifier (phone number or DB id).
        feature: Feature flag name (e.g., "new_pipeline").

    Returns:
        True if user is in the rollout bucket, False otherwise.
        Returns False on any error (safe default).
    """
    try:
        config = await ConfigService.get(f"feature_flag:{feature}")
    except ValidationError:
        logger.debug("feature_flag_disabled", feature=feature, reason="config_not_found")
        return False
    except Exception:
        logger.warning("feature_flag_error", feature=feature, reason="unexpected_error")
        return False

    if not isinstance(config, dict):
        logger.warning(
            "feature_flag_invalid_config",
            feature=feature,
            config_type=type(config).__name__,
        )
        return False

    rollout_percentage = config.get("rollout_percentage", 0)
    if not isinstance(rollout_percentage, (int, float)):
        logger.warning(
            "feature_flag_invalid_rollout_type",
            feature=feature,
            rollout_type=type(rollout_percentage).__name__,
        )
        return False

    rollout_percentage = int(rollout_percentage)

    if rollout_percentage <= 0:
        logger.debug(
            "feature_flag_evaluated",
            feature=feature,
            rollout_percentage=0,
            enabled=False,
        )
        return False
    if rollout_percentage >= 100:
        logger.debug(
            "feature_flag_evaluated",
            feature=feature,
            rollout_percentage=100,
            enabled=True,
        )
        return True

    # Hash-based bucketing: deterministic, uniform distribution
    hash_hex = hashlib.md5(user_id.encode(), usedforsecurity=False).hexdigest()
    bucket = int(hash_hex, 16) % 100

    enabled = bucket < rollout_percentage
    logger.debug(
        "feature_flag_evaluated",
        feature=feature,
        user_id=user_id,
        bucket=bucket,
        rollout_percentage=rollout_percentage,
        enabled=enabled,
    )
    return enabled
