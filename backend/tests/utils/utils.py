import random
import string

from fastapi.testclient import TestClient

from app.core.config import settings


def random_lower_string() -> str:
    return "".join(random.choices(string.ascii_lowercase, k=32))


def random_email() -> str:
    return f"{random_lower_string()}@{random_lower_string()}.com"


def random_pci_compliant_password() -> str:
    """
    Generate a random password that meets PCI DSS v4.0.1 requirements:
    - Minimum 12 characters
    - Contains at least one lowercase letter
    - Contains at least one uppercase letter
    - Contains at least one number
    - Contains at least one special character
    """
    lowercase = random.choice(string.ascii_lowercase)
    uppercase = random.choice(string.ascii_uppercase)
    digit = random.choice(string.digits)
    special = random.choice("!@#$%^&*()")

    # Fill the rest with random characters from all sets to reach 12+ chars
    remaining_length = 12 - 4
    all_chars = string.ascii_letters + string.digits + "!@#$%^&*()"
    remaining = "".join(random.choices(all_chars, k=remaining_length))

    # Combine and shuffle
    password = lowercase + uppercase + digit + special + remaining
    password_list = list(password)
    random.shuffle(password_list)
    return "".join(password_list)


def get_superuser_token_headers(client: TestClient) -> dict[str, str]:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers
