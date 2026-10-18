import base64
import json

import pytest

from src.auth.google_auth import AuthenticatedUser
from src.auth.session import (
    SessionError,
    sign_interaction,
    verify_interaction,
)


SECRET = "test-secret-for-unit-tests-only"
CONVERSATION_ID = "550e8400-e29b-41d4-a716-446655440000"
OTHER_CONVERSATION_ID = "550e8400-e29b-41d4-a716-446655440001"
INTERACTION_ID = "interaction-abc123"


def make_user(user_id="google-user-123"):
    return AuthenticatedUser(user_id=user_id)


def test_token_does_not_expose_raw_user_id():
    user = make_user()

    token = sign_interaction(
        user,
        CONVERSATION_ID,
        INTERACTION_ID,
        SECRET,
    )

    encoded_payload = token.split(".")[0]

    decoded = base64.urlsafe_b64decode(
        encoded_payload + "=" * (-len(encoded_payload) % 4)
    )

    payload = json.loads(decoded)

    assert "user_id" not in payload
    assert payload["user"] != user.user_id
    assert user.user_id not in token
    assert payload["interaction_id"] == INTERACTION_ID


def test_token_expires_after_24_hours(monkeypatch):
    from src.auth import session

    user = make_user()

    monkeypatch.setattr(session.time, "time", lambda: 1000)

    token = sign_interaction(
        user,
        CONVERSATION_ID,
        INTERACTION_ID,
        SECRET,
    )

    # Just before expiration: valid
    monkeypatch.setattr(
        session.time,
        "time",
        lambda: 1000 + session.TOKEN_LIFETIME_SECONDS - 1,
    )

    assert verify_interaction(
        token,
        user,
        CONVERSATION_ID,
        SECRET,
    ) == INTERACTION_ID

    # At expiration: rejected
    monkeypatch.setattr(
        session.time,
        "time",
        lambda: 1000 + session.TOKEN_LIFETIME_SECONDS,
    )

    with pytest.raises(SessionError, match="expired"):
        verify_interaction(
            token,
            user,
            CONVERSATION_ID,
            SECRET,
        )


def test_oversized_token_is_rejected():
    from src.auth.session import MAX_TOKEN_LENGTH

    oversized_token = "a" * (MAX_TOKEN_LENGTH + 1)

    with pytest.raises(SessionError, match="Invalid conversation token"):
        verify_interaction(
            oversized_token,
            make_user(),
            CONVERSATION_ID,
            SECRET,
        )


@pytest.mark.parametrize(
    "token",
    [
        "abc!.def",
        "abc.def!",
        "abc..def",
        "abc.def.ghi",
    ],
)
def test_malformed_token_is_rejected(token):
    with pytest.raises(SessionError):
        verify_interaction(
            token,
            make_user(),
            CONVERSATION_ID,
            SECRET,
        )

def test_sign_and_verify_interaction():
    user = make_user()

    token = sign_interaction(
        user,
        CONVERSATION_ID,
        INTERACTION_ID,
        SECRET,
    )

    result = verify_interaction(
        token,
        user,
        CONVERSATION_ID,
        SECRET,
    )

    assert result == INTERACTION_ID


def test_same_inputs_produce_same_token(monkeypatch):
    from src.auth import session

    monkeypatch.setattr(session.time, "time", lambda: 1000)

    user = make_user()

    first = sign_interaction(
        user,
        CONVERSATION_ID,
        INTERACTION_ID,
        SECRET,
    )

    second = sign_interaction(
        user,
        CONVERSATION_ID,
        INTERACTION_ID,
        SECRET,
    )

    assert first == second


def test_different_users_cannot_access_same_interaction():
    user_a = make_user("google-user-a")
    user_b = make_user("google-user-b")

    token = sign_interaction(
        user_a,
        CONVERSATION_ID,
        INTERACTION_ID,
        SECRET,
    )

    with pytest.raises(SessionError):
        verify_interaction(
            token,
            user_b,
            CONVERSATION_ID,
            SECRET,
        )


def test_different_conversation_id_is_rejected():
    user = make_user()

    token = sign_interaction(
        user,
        CONVERSATION_ID,
        INTERACTION_ID,
        SECRET,
    )

    with pytest.raises(SessionError):
        verify_interaction(
            token,
            user,
            OTHER_CONVERSATION_ID,
            SECRET,
        )


def test_modified_token_is_rejected():
    user = make_user()

    token = sign_interaction(
        user,
        CONVERSATION_ID,
        INTERACTION_ID,
        SECRET,
    )

    encoded, signature = token.split(".")

    modified_token = f"{encoded}.{'A' if signature[0] != 'A' else 'B'}{signature[1:]}"

    with pytest.raises(SessionError):
        verify_interaction(
            modified_token,
            user,
            CONVERSATION_ID,
            SECRET,
        )


def test_different_secret_is_rejected():
    user = make_user()

    token = sign_interaction(
        user,
        CONVERSATION_ID,
        INTERACTION_ID,
        SECRET,
    )

    with pytest.raises(SessionError):
        verify_interaction(
            token,
            user,
            CONVERSATION_ID,
            "different-secret",
        )


@pytest.mark.parametrize(
    "token",
    [
        "",
        "invalid-token",
        "abc.def.ghi",
        "not-base64.invalid",
        None,
        123,
    ],
)
def test_invalid_tokens_are_rejected(token):
    with pytest.raises(SessionError):
        verify_interaction(
            token,
            make_user(),
            CONVERSATION_ID,
            SECRET,
        )


@pytest.mark.parametrize(
    "user_id, conversation_id, interaction_id, secret",
    [
        ("", CONVERSATION_ID, INTERACTION_ID, SECRET),
        ("google-user-123", "", INTERACTION_ID, SECRET),
        ("google-user-123", CONVERSATION_ID, "", SECRET),
        ("google-user-123", CONVERSATION_ID, INTERACTION_ID, ""),
    ],
)
def test_sign_rejects_missing_information(
    user_id,
    conversation_id,
    interaction_id,
    secret,
):
    user = make_user(user_id)

    with pytest.raises(ValueError):
        sign_interaction(
            user,
            conversation_id,
            interaction_id,
            secret,
        )