import json
import logging
import secrets
import uuid
from datetime import timedelta
from typing import Any

import webauthn
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from webauthn.helpers.base64url_to_bytes import base64url_to_bytes
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticationCredential,
    AuthenticatorAssertionResponse,
    AuthenticatorAttestationResponse,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    RegistrationCredential,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.security import create_access_token
from app.crud import passkeys as passkeys_crud
from app.models import (
    Message,
    PasskeyAuthenticateCompleteRequest,
    PasskeyRegisterCompleteRequest,
    Token,
    User,
    WebAuthnCredentialPublic,
    WebAuthnCredentialsPublic,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/passkeys", tags=["passkeys"])


def _to_public(cred: Any) -> WebAuthnCredentialPublic:
    import base64
    return WebAuthnCredentialPublic(
        id=cred.id,
        credential_id=base64.urlsafe_b64encode(cred.credential_id).rstrip(b"=").decode(),
        name=cred.name,
        created_at=cred.created_at,
        last_used_at=cred.last_used_at,
    )


def _parse_registration_credential(data: dict) -> RegistrationCredential:  # type: ignore[type-arg]
    resp = data["response"]
    return RegistrationCredential(
        id=data["id"],
        raw_id=base64url_to_bytes(data["rawId"]),
        response=AuthenticatorAttestationResponse(
            client_data_json=base64url_to_bytes(resp["clientDataJSON"]),
            attestation_object=base64url_to_bytes(resp["attestationObject"]),
            transports=resp.get("transports"),
        ),
    )


def _parse_authentication_credential(data: dict) -> AuthenticationCredential:  # type: ignore[type-arg]
    resp = data["response"]
    return AuthenticationCredential(
        id=data["id"],
        raw_id=base64url_to_bytes(data["rawId"]),
        response=AuthenticatorAssertionResponse(
            client_data_json=base64url_to_bytes(resp["clientDataJSON"]),
            authenticator_data=base64url_to_bytes(resp["authenticatorData"]),
            signature=base64url_to_bytes(resp["signature"]),
            user_handle=base64url_to_bytes(resp["userHandle"]) if resp.get("userHandle") else None,
        ),
    )


@router.post("/register/begin")
def register_begin(session: SessionDep, current_user: CurrentUser) -> JSONResponse:
    existing = passkeys_crud.get_credentials_for_user(
        session=session, user_id=current_user.id
    )
    challenge_bytes = secrets.token_bytes(32)
    passkeys_crud.create_challenge(
        session=session, user_id=current_user.id, challenge=challenge_bytes
    )
    options = webauthn.generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=str(current_user.id).encode(),
        user_name=current_user.email,
        user_display_name=current_user.full_name or current_user.email,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=c.credential_id) for c in existing
        ],
        challenge=challenge_bytes,
        timeout=60000,
    )
    return JSONResponse(content=json.loads(webauthn.options_to_json(options)))


@router.post("/register/complete", response_model=WebAuthnCredentialPublic)
def register_complete(
    session: SessionDep,
    current_user: CurrentUser,
    body: PasskeyRegisterCompleteRequest,
) -> Any:
    challenge_record = passkeys_crud.consume_challenge_for_user(
        session=session, user_id=current_user.id
    )
    if not challenge_record:
        raise HTTPException(status_code=400, detail="Challenge expired or not found")

    try:
        reg_cred = _parse_registration_credential(body.credential)
        verified = webauthn.verify_registration_response(
            credential=reg_cred,
            expected_challenge=challenge_record.challenge,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGIN,
            require_user_verification=False,
        )
    except Exception as exc:
        logger.exception("Passkey registration failed")
        raise HTTPException(status_code=400, detail=f"Registration failed: {exc}") from exc

    cred = passkeys_crud.create_credential(
        session=session,
        user_id=current_user.id,
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        name=body.name,
    )
    return _to_public(cred)


@router.get("/", response_model=WebAuthnCredentialsPublic)
def list_credentials(session: SessionDep, current_user: CurrentUser) -> Any:
    creds = passkeys_crud.get_credentials_for_user(
        session=session, user_id=current_user.id
    )
    return WebAuthnCredentialsPublic(
        data=[_to_public(c) for c in creds], count=len(creds)
    )


@router.delete("/{credential_id}", response_model=Message)
def delete_credential(
    session: SessionDep, current_user: CurrentUser, credential_id: uuid.UUID
) -> Any:
    from app.models import WebAuthnCredential

    cred = session.get(WebAuthnCredential, credential_id)
    if not cred or cred.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Passkey not found")
    passkeys_crud.delete_credential(session=session, credential=cred)
    return Message(message="Passkey deleted successfully")


@router.post("/authenticate/begin")
def authenticate_begin(session: SessionDep) -> JSONResponse:
    challenge_bytes = secrets.token_bytes(32)
    passkeys_crud.create_challenge(
        session=session, user_id=None, challenge=challenge_bytes
    )
    options = webauthn.generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        allow_credentials=[],
        user_verification=UserVerificationRequirement.PREFERRED,
        challenge=challenge_bytes,
        timeout=60000,
    )
    return JSONResponse(content=json.loads(webauthn.options_to_json(options)))


@router.post("/authenticate/complete", response_model=Token)
def authenticate_complete(
    session: SessionDep,
    body: PasskeyAuthenticateCompleteRequest,
) -> Any:
    try:
        auth_cred = _parse_authentication_credential(body.credential)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid credential format") from exc

    # client_data_json is already decoded bytes — parse directly
    client_data = json.loads(auth_cred.response.client_data_json)
    expected_challenge = base64url_to_bytes(client_data["challenge"])

    challenge_record = passkeys_crud.consume_challenge_by_bytes(
        session=session, challenge=expected_challenge
    )
    if not challenge_record:
        raise HTTPException(status_code=400, detail="Invalid or expired challenge")

    db_cred = passkeys_crud.get_credential_by_id(
        session=session, credential_id=auth_cred.raw_id
    )
    if not db_cred:
        raise HTTPException(status_code=404, detail="Passkey not registered")

    try:
        verified = webauthn.verify_authentication_response(
            credential=auth_cred,
            expected_challenge=expected_challenge,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGIN,
            credential_public_key=db_cred.public_key,
            credential_current_sign_count=db_cred.sign_count,
            require_user_verification=False,
        )
    except Exception as exc:
        logger.exception("Passkey authentication failed")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {exc}") from exc

    passkeys_crud.update_sign_count(
        session=session, cred=db_cred, new_count=verified.new_sign_count
    )

    user = session.get(User, db_cred.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive or deleted user")

    return Token(
        access_token=create_access_token(
            subject=str(user.id),
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
    )
