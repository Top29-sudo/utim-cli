import pytest
from utim_cli.server.auth import validate_email_address

def test_validate_email_syntax():
    # Valid emails
    valid, msg = validate_email_address("developer@gmail.com")
    assert valid is True
    assert msg == ""

    valid, msg = validate_email_address("user.name+test@outlook.com")
    assert valid is True

    # Invalid syntax
    valid, msg = validate_email_address("invalid-email")
    assert valid is False
    assert "format" in msg.lower()

    valid, msg = validate_email_address("@domain.com")
    assert valid is False

    valid, msg = validate_email_address("user@")
    assert valid is False


def test_disposable_email_domain_blocked():
    # Disposable domains should be rejected
    disposable_emails = [
        "fakeuser@mailinator.com",
        "random123@dispostable.com",
        "trash@10minutemail.com",
        "temp@trashmail.com",
        "test@yopmail.com",
        "user@asdf.com",
        "fake@fake.com",
        "test@example.com"
    ]
    for email in disposable_emails:
        valid, msg = validate_email_address(email)
        assert valid is False, f"Expected {email} to be blocked as disposable/fake"
        assert "disposable" in msg.lower() or "fake" in msg.lower()


def test_nonexistent_email_domain_dns_check():
    # Non-existent domain should be caught by DNS socket lookup
    valid, msg = validate_email_address("testuser@nonexistentdomain123456789xyz.com")
    assert valid is False
    assert "does not exist" in msg.lower() or "cannot be reached" in msg.lower()
