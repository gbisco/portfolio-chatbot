from datetime import datetime, timezone
from threading import Barrier, Lock, Thread
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from src.auth.google_auth import AuthenticatedUser
from src.chat.rate_limit import (
    RateLimitDenied,
    RateLimitServiceError,
    enforce_rate_limits,
)

# Intended production limits. Unit fixtures use different values on purpose.
INTENDED_PRODUCTION_USAGE_LIMITS = (10, 40, 150)


class FakeDynamoDB:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def transact_write_items(self, **kwargs):
        self.calls.append(kwargs)

        if self.error:
            raise self.error

        return {}


class InMemoryDynamoDB:
    """Stateful TransactWriteItems stand-in for quota tests. No AWS calls."""

    def __init__(self):
        self.items = {}
        self.calls = []
        self._lock = Lock()

    def usage(self, pk):
        item = self.items.get(pk)
        return None if item is None else item.get("usage")

    def transact_write_items(self, **kwargs):
        operations = kwargs["TransactItems"]
        self.calls.append(kwargs)

        with self._lock:
            reasons = []
            planned = []

            for operation in operations:
                if "ConditionCheck" in operation:
                    passed = self._block_check_passes(operation["ConditionCheck"])
                    reasons.append(
                        {"Code": "None"} if passed else {"Code": "ConditionalCheckFailed"}
                    )
                    continue

                update = operation["Update"]
                pk = update["Key"]["pk"]["S"]
                limit = int(update["ExpressionAttributeValues"][":limit"]["N"])
                increment = int(update["ExpressionAttributeValues"][":one"]["N"])
                current = self.usage(pk)

                if current is None or current < limit:
                    reasons.append({"Code": "None"})
                    next_usage = increment if current is None else current + increment
                    planned.append((pk, next_usage))
                else:
                    reasons.append({"Code": "ConditionalCheckFailed"})
                    planned.append(None)

            if any(reason["Code"] != "None" for reason in reasons):
                raise ClientError(
                    {
                        "Error": {
                            "Code": "TransactionCanceledException",
                            "Message": "Transaction cancelled",
                        },
                        "CancellationReasons": reasons,
                    },
                    "TransactWriteItems",
                )

            for item in planned:
                if item is None:
                    continue

                pk, next_usage = item
                self.items[pk] = {**self.items.get(pk, {}), "usage": next_usage}

        return {}

    def _block_check_passes(self, condition_check):
        pk = condition_check["Key"]["pk"]["S"]
        item = self.items.get(pk)

        if item is None:
            return True

        return item.get("blocked") is not True


def make_config(**overrides):
    values = {
        "dynamodb_table_name": "portfolio-usage-test",
        "user_daily_limit": 10,
        "global_hourly_limit": 100,
        "global_daily_limit": 500,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def stateful_config():
    config = make_config(
        user_daily_limit=2,
        global_hourly_limit=3,
        global_daily_limit=5,
    )
    assert (
        config.user_daily_limit,
        config.global_hourly_limit,
        config.global_daily_limit,
    ) != INTENDED_PRODUCTION_USAGE_LIMITS
    return config


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


def test_requests_succeed_until_user_quota_is_reached():
    client = InMemoryDynamoDB()
    config = stateful_config()
    user = make_user()
    now = datetime(2026, 10, 17, 14, 30, tzinfo=timezone.utc)

    enforce_rate_limits(user, config, client=client, now=now)
    enforce_rate_limits(user, config, client=client, now=now)

    assert client.usage("USER#google-user-123#20261017") == 2

    with pytest.raises(RateLimitDenied) as exc_info:
        enforce_rate_limits(user, config, client=client, now=now)

    assert exc_info.value.reason == "user_daily_limit"
    assert client.usage("USER#google-user-123#20261017") == 2
    assert client.usage("GLOBAL#HOUR#2026101714") == 2
    assert client.usage("GLOBAL#DAY#20261017") == 2


def test_blocked_user_cannot_consume_quota():
    client = InMemoryDynamoDB()
    config = stateful_config()
    user = make_user()
    now = datetime(2026, 10, 17, 14, 30, tzinfo=timezone.utc)

    client.items["BLOCK#google-user-123"] = {"blocked": True}

    with pytest.raises(RateLimitDenied) as exc_info:
        enforce_rate_limits(user, config, client=client, now=now)

    assert exc_info.value.reason == "account_blocked"
    assert client.usage("USER#google-user-123#20261017") is None
    assert client.usage("GLOBAL#HOUR#2026101714") is None
    assert client.usage("GLOBAL#DAY#20261017") is None


def test_users_have_separate_limits_and_share_global_limits():
    client = InMemoryDynamoDB()
    config = stateful_config()
    now = datetime(2026, 10, 17, 14, 30, tzinfo=timezone.utc)
    user_a = AuthenticatedUser(user_id="google-user-a")
    user_b = AuthenticatedUser(user_id="google-user-b")

    enforce_rate_limits(user_a, config, client=client, now=now)
    enforce_rate_limits(user_a, config, client=client, now=now)

    with pytest.raises(RateLimitDenied) as user_limit:
        enforce_rate_limits(user_a, config, client=client, now=now)

    assert user_limit.value.reason == "user_daily_limit"

    enforce_rate_limits(user_b, config, client=client, now=now)

    with pytest.raises(RateLimitDenied) as global_limit:
        enforce_rate_limits(user_b, config, client=client, now=now)

    assert global_limit.value.reason == "global_hourly_limit"
    assert client.usage("USER#google-user-a#20261017") == 2
    assert client.usage("USER#google-user-b#20261017") == 1
    assert client.usage("GLOBAL#HOUR#2026101714") == 3
    assert client.usage("GLOBAL#DAY#20261017") == 3


def test_concurrent_requests_cannot_both_consume_the_final_slot():
    client = InMemoryDynamoDB()
    config = make_config(
        user_daily_limit=1,
        global_hourly_limit=10,
        global_daily_limit=10,
    )
    now = datetime(2026, 10, 17, 14, 30, tzinfo=timezone.utc)
    barrier = Barrier(2)
    outcomes = []

    def attempt():
        barrier.wait()

        try:
            enforce_rate_limits(make_user(), config, client=client, now=now)
            outcomes.append("allowed")
        except RateLimitDenied as exc:
            outcomes.append(exc.reason)

    threads = [Thread(target=attempt), Thread(target=attempt)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert outcomes.count("allowed") == 1
    assert outcomes.count("user_daily_limit") == 1
    assert client.usage("USER#google-user-123#20261017") == 1