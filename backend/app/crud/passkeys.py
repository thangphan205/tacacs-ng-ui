import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, delete, select

from app.models import WebAuthnChallenge, WebAuthnCredential


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_challenge(
    *,
    session: Session,
    user_id: uuid.UUID | None,
    challenge: bytes,
    ttl_seconds: int = 300,
) -> WebAuthnChallenge:
    expires = _utc_now() + timedelta(seconds=ttl_seconds)
    ch = WebAuthnChallenge(challenge=challenge, user_id=user_id, expires_at=expires)
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return ch


def _purge_expired(session: Session) -> None:
    session.exec(  # type: ignore[call-overload]
        delete(WebAuthnChallenge).where(WebAuthnChallenge.expires_at <= _utc_now())
    )


def consume_challenge_for_user(
    *, session: Session, user_id: uuid.UUID
) -> WebAuthnChallenge | None:
    ch = session.exec(
        select(WebAuthnChallenge)
        .where(
            WebAuthnChallenge.user_id == user_id,
            WebAuthnChallenge.expires_at > _utc_now(),
        )
        .order_by(WebAuthnChallenge.created_at.desc())  # type: ignore[arg-type]
    ).first()
    _purge_expired(session)
    if ch:
        session.delete(ch)
    session.commit()
    return ch


def consume_challenge_by_bytes(
    *, session: Session, challenge: bytes
) -> WebAuthnChallenge | None:
    ch = session.exec(
        select(WebAuthnChallenge).where(
            WebAuthnChallenge.challenge == challenge,
            WebAuthnChallenge.expires_at > _utc_now(),
        )
    ).first()
    _purge_expired(session)
    if ch:
        session.delete(ch)
    session.commit()
    return ch


def get_credentials_for_user(
    *, session: Session, user_id: uuid.UUID
) -> list[WebAuthnCredential]:
    return list(
        session.exec(
            select(WebAuthnCredential).where(WebAuthnCredential.user_id == user_id)
        ).all()
    )


def get_credential_by_id(
    *, session: Session, credential_id: bytes
) -> WebAuthnCredential | None:
    return session.exec(
        select(WebAuthnCredential).where(
            WebAuthnCredential.credential_id == credential_id
        )
    ).first()


def create_credential(
    *,
    session: Session,
    user_id: uuid.UUID,
    credential_id: bytes,
    public_key: bytes,
    sign_count: int,
    name: str | None,
) -> WebAuthnCredential:
    cred = WebAuthnCredential(
        user_id=user_id,
        credential_id=credential_id,
        public_key=public_key,
        sign_count=sign_count,
        name=name,
    )
    session.add(cred)
    session.commit()
    session.refresh(cred)
    return cred


def update_sign_count(
    *, session: Session, cred: WebAuthnCredential, new_count: int
) -> WebAuthnCredential:
    cred.sign_count = new_count
    cred.last_used_at = _utc_now()
    session.add(cred)
    session.commit()
    session.refresh(cred)
    return cred


def delete_credential(*, session: Session, credential: WebAuthnCredential) -> None:
    session.delete(credential)
    session.commit()
