
from src.auth.google_auth import AuthenticatedUser
from src.auth.session import derive_cx_session_id


SECRET = "test-secret-for-unit-tests-only"
CONVERSATION_ID = "550e8400-e29b-41d4-a716-446655440000"


def test_same_user_and_conversation_produce_same_session():
    user = AuthenticatedUser(user_id="google-user-123")

    first = derive_cx_session_id(user, CONVERSATION_ID, SECRET)
    second = derive_cx_session_id(user, CONVERSATION_ID, SECRET)

    assert first == second
    assert len(first) == 32


def test_different_users_have_different_sessions():
    user_a = AuthenticatedUser(user_id="google-user-a")
    user_b = AuthenticatedUser(user_id="google-user-b")

    session_a = derive_cx_session_id(user_a, CONVERSATION_ID, SECRET)
    session_b = derive_cx_session_id(user_b, CONVERSATION_ID, SECRET)

    assert session_a != session_b


def test_different_conversations_have_different_sessions():
    user = AuthenticatedUser(user_id="google-user-123")

    first = derive_cx_session_id(user, CONVERSATION_ID, SECRET)
    second = derive_cx_session_id(
        user,
        "550e8400-e29b-41d4-a716-446655440001",
        SECRET,
    )

    assert first != second


def test_changing_secret_changes_session():
    user = AuthenticatedUser(user_id="google-user-123")

    first = derive_cx_session_id(user, CONVERSATION_ID, SECRET)
    second = derive_cx_session_id(user, CONVERSATION_ID, "another-secret")

    assert first != second


def test_session_id_does_not_expose_google_user_id():
    user = AuthenticatedUser(user_id="google-user-123")

    session_id = derive_cx_session_id(user, CONVERSATION_ID, SECRET)

    assert user.user_id not in session_id
    assert CONVERSATION_ID not in session_id
