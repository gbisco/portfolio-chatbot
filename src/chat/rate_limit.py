from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from src.auth.google_auth import AuthenticatedUser
from src.config import Config


class RateLimitDenied(Exception):
    """Raised when an account is blocked or a usage quota is exceeded."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class RateLimitServiceError(Exception):
    """Raised when usage enforcement cannot be completed safely."""


DENIAL_REASONS = (
    "account_blocked",
    "user_daily_limit",
    "global_hourly_limit",
    "global_daily_limit",
)


def enforce_rate_limits(
    user: AuthenticatedUser,
    config: Config,
    *,
    client=None,
    now: datetime | None = None,
) -> None:
    """Atomically authorize and count one chat request."""

    if not isinstance(user, AuthenticatedUser) or not user.user_id:
        raise ValueError("A verified user is required")

    if now is None:
        now = datetime.now(timezone.utc)

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    if client is None:
        client = boto3.client("dynamodb")

    now = now.astimezone(timezone.utc)

    day = now.strftime("%Y%m%d")
    hour = now.strftime("%Y%m%d%H")

    quotas = (
        (f"USER#{user.user_id}#{day}", config.user_daily_limit),
        (f"GLOBAL#HOUR#{hour}", config.global_hourly_limit),
        (f"GLOBAL#DAY#{day}", config.global_daily_limit),
    )

    operations = [
        {
            "ConditionCheck": {
                "TableName": config.dynamodb_table_name,
                "Key": {
                    "pk": {"S": f"BLOCK#{user.user_id}"},
                },
                "ConditionExpression": (
                    "attribute_not_exists(#blocked) OR #blocked = :false"
                ),
                "ExpressionAttributeNames": {
                    "#blocked": "blocked",
                },
                "ExpressionAttributeValues": {
                    ":false": {"BOOL": False},
                },
            }
        }
    ]

    for key, limit in quotas:
        operations.append(
            {
                "Update": {
                    "TableName": config.dynamodb_table_name,
                    "Key": {"pk": {"S": key}},
                    "UpdateExpression": (
                        "SET #usage = if_not_exists(#usage, :zero) + :one"
                    ),
                    "ConditionExpression": (
                        "attribute_not_exists(#usage) OR #usage < :limit"
                    ),
                    "ExpressionAttributeNames": {
                        "#usage": "usage",
                    },
                    "ExpressionAttributeValues": {
                        ":zero": {"N": "0"},
                        ":one": {"N": "1"},
                        ":limit": {"N": str(limit)},
                    },
                }
            }
        )

    try:
        client.transact_write_items(TransactItems=operations)

    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")

        if code == "TransactionCanceledException":
            reasons = exc.response.get("CancellationReasons", [])

            for index, reason in enumerate(DENIAL_REASONS):
                if (
                    index < len(reasons)
                    and reasons[index].get("Code") == "ConditionalCheckFailed"
                ):
                    raise RateLimitDenied(reason) from exc

        raise RateLimitServiceError(
            "Unable to enforce usage limits"
        ) from exc

    except BotoCoreError as exc:
        raise RateLimitServiceError(
            "Unable to enforce usage limits"
        ) from exc