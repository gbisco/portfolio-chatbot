from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from src.auth.google_auth import AuthenticatedUser
from src.chat.rate_limit import (
    RateLimitDenied,
    RateLimitServiceError,
    enforce_rate_limits,
)


class FakeDynamoDB:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def transact_write_items(self, **kwargs):
        self.calls.append(kwargs)

        if self.error:
            raise self.error

        return {}


def make_config():
    return SimpleNamespace(
        dynamodb_table_name="portfolio-usage-test",
        user_daily_limit=10,
        global_hourly_limit=100,
        global_daily_limit=500,
    )


def make_user():
    return AuthenticatedUser(user_id="google-user-123")


def make_transaction_error(failed_index):
    reasons = [{"Code": "None"} for _ in range(4)]

    reasons[failed_index] = {
        "Code": "ConditionalCheckFailed"
    }

    return ClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "Transaction cancelled",
            },
            "CancellationReasons": reasons,
        },
        "TransactWriteItems",
    )


def test_transaction_contains_block_check_and_three_quotas():
    client = FakeDynamoDB()

    enforce_rate_limits(
        make_user(),
        make_config(),
        client=client,
        now=datetime(2026, 10, 17, 14, 30, tzinfo=timezone.utc),
    )

    assert len(client.calls) == 1

    operations = client.calls[0]["TransactItems"]

    assert len(operations) == 4

    assert operations[0]["ConditionCheck"]["Key"]["pk"]["S"] == (
        "BLOCK#google-user-123"
    )

    keys = [
        operation["Update"]["Key"]["pk"]["S"]
        for operation in operations[1:]
    ]

    assert keys == [
        "USER#google-user-123#20261017",
        "GLOBAL#HOUR#2026101714",
        "GLOBAL#DAY#20261017",
    ]


def test_limits_are_included_in_atomic_updates():
    client = FakeDynamoDB()

    enforce_rate_limits(
        make_user(),
        make_config(),
        client=client,
    )

    updates = client.calls[0]["TransactItems"][1:]

    limits = [
        update["Update"]["ExpressionAttributeValues"][":limit"]["N"]
        for update in updates
    ]

    assert limits == ["10", "100", "500"]

    for update in updates:
        assert "ConditionExpression" in update["Update"]


@pytest.mark.parametrize(
    "failed_index, expected_reason",
    [
        (0, "account_blocked"),
        (1, "user_daily_limit"),
        (2, "global_hourly_limit"),
        (3, "global_daily_limit"),
    ],
)
def test_denial_reason_is_identified(failed_index, expected_reason):
    client = FakeDynamoDB(
        error=make_transaction_error(failed_index)
    )

    with pytest.raises(RateLimitDenied) as exc_info:
        enforce_rate_limits(
            make_user(),
            make_config(),
            client=client,
        )

    assert exc_info.value.reason == expected_reason


def test_multiple_failed_conditions_return_first_reason():
    error = ClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "Transaction cancelled",
            },
            "CancellationReasons": [
                {"Code": "None"},
                {"Code": "ConditionalCheckFailed"},
                {"Code": "ConditionalCheckFailed"},
                {"Code": "ConditionalCheckFailed"},
            ],
        },
        "TransactWriteItems",
    )

    with pytest.raises(RateLimitDenied) as exc_info:
        enforce_rate_limits(
            make_user(),
            make_config(),
            client=FakeDynamoDB(error=error),
        )

    assert exc_info.value.reason == "user_daily_limit"


def test_unknown_transaction_failure_is_service_error():
    error = ClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "Transaction cancelled",
            },
            "CancellationReasons": [
                {"Code": "TransactionConflict"},
                {"Code": "None"},
                {"Code": "None"},
                {"Code": "None"},
            ],
        },
        "TransactWriteItems",
    )

    with pytest.raises(RateLimitServiceError):
        enforce_rate_limits(
            make_user(),
            make_config(),
            client=FakeDynamoDB(error=error),
        )


def test_database_failure_fails_closed():
    error = ClientError(
        {
            "Error": {
                "Code": "ProvisionedThroughputExceededException",
                "Message": "Database unavailable",
            }
        },
        "TransactWriteItems",
    )

    with pytest.raises(RateLimitServiceError):
        enforce_rate_limits(
            make_user(),
            make_config(),
            client=FakeDynamoDB(error=error),
        )


def test_missing_verified_user_is_rejected():
    client = FakeDynamoDB()

    with pytest.raises(ValueError):
        enforce_rate_limits(
            None,
            make_config(),
            client=client,
        )

    assert client.calls == []