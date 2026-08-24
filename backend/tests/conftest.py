from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.crud import api_keys, users
from app.main import app
from app.models import ApiKeyCreate, Item, User
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        init_db(session)
        yield session
        statement = delete(Item)
        session.execute(statement)
        statement = delete(User)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    # Session-scoped, not module-scoped: entering the app lifespan once per test
    # module would call StreamableHTTPSessionManager.run() more than once (it
    # raises on the second call), and would respawn the background asyncio loops
    # for every module.
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )


@pytest.fixture
def mcp_api_key(db: Session) -> str:
    """Mint a superuser-bound API key with every MCP scope; return the plaintext."""
    user = users.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert user is not None
    _, plaintext = api_keys.create_api_key(
        session=db,
        api_key_create=ApiKeyCreate(
            name="pytest-mcp",
            scopes="mcp:read,mcp:generate,mcp:validate,mcp:secrets",
        ),
        owner_id=user.id,
        created_by_id=user.id,
    )
    return plaintext


@pytest.fixture
def mcp_headers(mcp_api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {mcp_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
