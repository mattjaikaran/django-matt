"""
Password utilities using Django's built-in hashers.

Replaces passlib and argon2-cffi dependencies with Django's native support.
Django supports: Argon2, bcrypt, PBKDF2, scrypt.

Usage:
    from django_matt.auth.passwords import (
        hash_password,
        verify_password,
        check_password_strength,
    )

    # Hash a password
    hashed = hash_password("mysecretpassword")

    # Verify a password
    is_valid = verify_password("mysecretpassword", hashed)

    # Check password strength
    result = check_password_strength("weak")
    if not result.is_valid:
        print(result.errors)
"""

import re
import secrets
import string
from dataclasses import dataclass, field
from typing import List, Optional

from django.contrib.auth.hashers import (
    check_password,
    make_password,
    is_password_usable,
    get_hasher,
    identify_hasher,
    UNUSABLE_PASSWORD_PREFIX,
)
from django.contrib.auth.password_validation import (
    validate_password,
    get_default_password_validators,
    password_validators_help_texts,
)
from django.core.exceptions import ValidationError


def hash_password(
    password: str,
    salt: Optional[str] = None,
    hasher: str = "default",
) -> str:
    """
    Hash a password using Django's password hashing system.

    By default uses the first hasher in PASSWORD_HASHERS setting,
    which should be Argon2 or bcrypt for production.

    Args:
        password: The plaintext password to hash
        salt: Optional salt (auto-generated if not provided)
        hasher: Hasher algorithm ("default", "argon2", "bcrypt", "pbkdf2_sha256")

    Returns:
        The hashed password string

    Example:
        >>> hashed = hash_password("mysecretpassword")
        >>> hashed.startswith("argon2")  # or bcrypt, pbkdf2, etc.
        True
    """
    return make_password(password, salt=salt, hasher=hasher)


def verify_password(password: str, encoded: str) -> bool:
    """
    Verify a password against a hash.

    Args:
        password: The plaintext password to check
        encoded: The hashed password to check against

    Returns:
        True if password matches, False otherwise

    Example:
        >>> hashed = hash_password("secret")
        >>> verify_password("secret", hashed)
        True
        >>> verify_password("wrong", hashed)
        False
    """
    return check_password(password, encoded)


def is_valid_hash(encoded: str) -> bool:
    """
    Check if a string is a valid password hash.

    Args:
        encoded: The string to check

    Returns:
        True if it's a usable password hash

    Example:
        >>> is_valid_hash(hash_password("test"))
        True
        >>> is_valid_hash("not a hash")
        False
    """
    return is_password_usable(encoded)


def needs_rehash(encoded: str, preferred_hasher: str = "default") -> bool:
    """
    Check if a password hash needs to be upgraded.

    This is useful when migrating between hashers or when
    hasher parameters (like iterations) have been increased.

    Args:
        encoded: The hashed password
        preferred_hasher: The preferred hasher algorithm

    Returns:
        True if the hash should be regenerated

    Example:
        >>> old_hash = make_password("test", hasher="md5")  # Weak hasher
        >>> needs_rehash(old_hash, "argon2")
        True
    """
    if not is_password_usable(encoded):
        return True

    try:
        current_hasher = identify_hasher(encoded)
        preferred = get_hasher(preferred_hasher)

        # Different hasher type
        if current_hasher.algorithm != preferred.algorithm:
            return True

        # Check if hasher needs upgrade (iterations increased, etc.)
        return current_hasher.must_update(encoded)
    except ValueError:
        return True


def get_unusable_password() -> str:
    """
    Get an unusable password marker.

    Useful for accounts that shouldn't use password auth
    (e.g., OAuth-only accounts).

    Returns:
        An unusable password string
    """
    return make_password(None)


def is_unusable_password(encoded: str) -> bool:
    """
    Check if a password is marked as unusable.

    Args:
        encoded: The password hash to check

    Returns:
        True if this is an unusable password marker
    """
    return not is_password_usable(encoded)


@dataclass
class PasswordStrengthResult:
    """Result of password strength validation."""

    is_valid: bool
    score: int  # 0-4 strength score
    errors: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    @property
    def strength_label(self) -> str:
        """Get human-readable strength label."""
        labels = ["Very Weak", "Weak", "Fair", "Strong", "Very Strong"]
        return labels[min(self.score, 4)]


def check_password_strength(
    password: str,
    user=None,
    min_length: int = 8,
    require_uppercase: bool = True,
    require_lowercase: bool = True,
    require_digit: bool = True,
    require_special: bool = False,
    use_django_validators: bool = True,
) -> PasswordStrengthResult:
    """
    Check password strength with configurable requirements.

    Args:
        password: The password to check
        user: Optional user for context-aware validation
        min_length: Minimum password length
        require_uppercase: Require at least one uppercase letter
        require_lowercase: Require at least one lowercase letter
        require_digit: Require at least one digit
        require_special: Require at least one special character
        use_django_validators: Also run Django's password validators

    Returns:
        PasswordStrengthResult with validation details

    Example:
        >>> result = check_password_strength("weak")
        >>> result.is_valid
        False
        >>> result.errors
        ['Password must be at least 8 characters long', ...]
    """
    errors = []
    suggestions = []
    score = 0

    # Length check
    if len(password) < min_length:
        errors.append(f"Password must be at least {min_length} characters long")
    else:
        score += 1
        if len(password) >= 12:
            score += 1

    # Character class checks
    has_upper = bool(re.search(r"[A-Z]", password))
    has_lower = bool(re.search(r"[a-z]", password))
    has_digit = bool(re.search(r"\d", password))
    has_special = bool(re.search(r"[!@#$%^&*(),.?\":{}|<>]", password))

    if require_uppercase and not has_upper:
        errors.append("Password must contain at least one uppercase letter")
    elif has_upper:
        score += 0.5

    if require_lowercase and not has_lower:
        errors.append("Password must contain at least one lowercase letter")
    elif has_lower:
        score += 0.5

    if require_digit and not has_digit:
        errors.append("Password must contain at least one digit")
    elif has_digit:
        score += 0.5

    if require_special and not has_special:
        errors.append("Password must contain at least one special character")
    elif has_special:
        score += 0.5

    # Common password patterns
    common_patterns = [
        r"^123",
        r"password",
        r"qwerty",
        r"abc123",
        r"letmein",
        r"admin",
        r"welcome",
    ]
    for pattern in common_patterns:
        if re.search(pattern, password.lower()):
            errors.append("Password is too common")
            score = max(0, score - 1)
            break

    # Django validators
    if use_django_validators:
        try:
            validate_password(password, user=user)
        except ValidationError as e:
            errors.extend(e.messages)

    # Generate suggestions
    if not has_upper:
        suggestions.append("Add uppercase letters")
    if not has_lower:
        suggestions.append("Add lowercase letters")
    if not has_digit:
        suggestions.append("Add numbers")
    if not has_special:
        suggestions.append("Add special characters (!@#$%^&*)")
    if len(password) < 12:
        suggestions.append("Use a longer password (12+ characters)")

    return PasswordStrengthResult(
        is_valid=len(errors) == 0,
        score=int(min(score, 4)),
        errors=errors,
        suggestions=suggestions if errors else [],
    )


def generate_password(
    length: int = 16,
    include_uppercase: bool = True,
    include_lowercase: bool = True,
    include_digits: bool = True,
    include_special: bool = True,
    exclude_ambiguous: bool = True,
) -> str:
    """
    Generate a secure random password.

    Args:
        length: Password length (default 16)
        include_uppercase: Include uppercase letters
        include_lowercase: Include lowercase letters
        include_digits: Include digits
        include_special: Include special characters
        exclude_ambiguous: Exclude ambiguous characters (0, O, l, 1, I)

    Returns:
        A secure random password

    Example:
        >>> password = generate_password(length=20)
        >>> len(password)
        20
    """
    chars = ""

    if include_lowercase:
        chars += string.ascii_lowercase
    if include_uppercase:
        chars += string.ascii_uppercase
    if include_digits:
        chars += string.digits
    if include_special:
        chars += "!@#$%^&*()_+-=[]{}|;:,.<>?"

    if exclude_ambiguous:
        ambiguous = "0O1lI"
        chars = "".join(c for c in chars if c not in ambiguous)

    if not chars:
        chars = string.ascii_letters + string.digits

    # Generate password ensuring at least one char from each category
    password_chars = []

    if include_lowercase:
        lowercase = string.ascii_lowercase
        if exclude_ambiguous:
            lowercase = "".join(c for c in lowercase if c not in "l")
        password_chars.append(secrets.choice(lowercase))

    if include_uppercase:
        uppercase = string.ascii_uppercase
        if exclude_ambiguous:
            uppercase = "".join(c for c in uppercase if c not in "OI")
        password_chars.append(secrets.choice(uppercase))

    if include_digits:
        digits = string.digits
        if exclude_ambiguous:
            digits = "".join(c for c in digits if c not in "01")
        password_chars.append(secrets.choice(digits))

    if include_special:
        password_chars.append(secrets.choice("!@#$%^&*()_+-=[]{}|;:,.<>?"))

    # Fill remaining length
    remaining = length - len(password_chars)
    password_chars.extend(secrets.choice(chars) for _ in range(remaining))

    # Shuffle
    password_list = list(password_chars)
    secrets.SystemRandom().shuffle(password_list)

    return "".join(password_list)


def generate_passphrase(
    num_words: int = 4,
    separator: str = "-",
    capitalize: bool = True,
) -> str:
    """
    Generate a memorable passphrase using random words.

    Args:
        num_words: Number of words in passphrase
        separator: Character to separate words
        capitalize: Capitalize each word

    Returns:
        A passphrase like "Correct-Horse-Battery-Staple"

    Example:
        >>> passphrase = generate_passphrase(4)
        >>> len(passphrase.split("-"))
        4
    """
    # Common English words (subset for demo - in production use a larger wordlist)
    words = [
        "apple", "banana", "cherry", "dragon", "eagle", "falcon", "garden",
        "harbor", "island", "jungle", "kitten", "lemon", "mango", "nectar",
        "orange", "purple", "quartz", "river", "sunset", "thunder", "umbrella",
        "violet", "winter", "yellow", "zebra", "ancient", "bright", "castle",
        "diamond", "empire", "forest", "golden", "hollow", "ivory", "journey",
        "kingdom", "lantern", "meadow", "noble", "oracle", "phoenix", "quantum",
        "radiant", "silver", "temple", "unique", "velvet", "whisper", "crystal",
        "zenith", "aurora", "beacon", "cosmic", "dazzle", "emerald", "flicker",
        "glacier", "harmony", "inferno", "jubilee", "kinetic", "legend", "mystic",
    ]

    selected = [secrets.choice(words) for _ in range(num_words)]

    if capitalize:
        selected = [word.capitalize() for word in selected]

    return separator.join(selected)


def get_password_help_text() -> List[str]:
    """
    Get help text describing password requirements.

    Returns list of requirement descriptions from Django validators.
    """
    return password_validators_help_texts()


# Aliases for compatibility
make_hash = hash_password
check_hash = verify_password
