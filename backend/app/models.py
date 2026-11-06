import re
import uuid
from datetime import date, datetime, timezone
from ipaddress import ip_network
from typing import Literal

import sqlalchemy as sa
from pydantic import EmailStr, TypeAdapter, field_validator, model_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import Column, Field, Relationship, SQLModel

from app.core.config import settings
from app.core.raw_script import normalize_raw_script


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampModel(SQLModel):
    created_at: datetime = Field(default_factory=_utc_now, nullable=False)
    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_column_kwargs={"onupdate": _utc_now},
    )


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)
    password_login_disabled: bool = False


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)
    password_login_disabled: bool | None = Field(default=None)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    password_login_disabled: bool | None = Field(default=None)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    google_id: str | None = Field(default=None, index=True, unique=True)
    keycloak_id: str | None = Field(default=None, index=True, unique=True)
    microsoft_id: str | None = Field(default=None, index=True, unique=True)
    password_login_disabled: bool = Field(default=False)
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)
    webauthn_credentials: list["WebAuthnCredential"] = Relationship(
        back_populates="user",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    @property
    def login_methods(self) -> list[str]:
        methods = []
        if not self.password_login_disabled:
            methods.append("Password")
        if self.google_id:
            methods.append("Google")
        if self.keycloak_id:
            methods.append("Keycloak")
        if self.microsoft_id:
            methods.append("Microsoft")
        if self.webauthn_credentials:
            methods.append("Passkeys")
        return methods


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    password_login_disabled: bool
    login_methods: list[str] = Field(default_factory=list)


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)


# --- TACACS+ Configuration Tables ---


class TacacsNgSettingBase(SQLModel):
    ipv4_enabled: bool = Field(default=True)
    ipv4_address: str = Field(default="0.0.0.0")
    ipv4_port: int = Field(default=49)
    ipv6_enabled: bool = Field(default=False)
    ipv6_address: str = Field(default="::")
    ipv6_port: int = Field(default=49)
    instances_min: int = Field(default=1)
    instances_max: int = Field(default=10)
    background: str = Field(default="no")
    access_logfile_destination: str = Field(
        default=settings.TACACS_LOG_DIRECTORY + "%Y/%m/access-%Y-%m-%d.log"
    )
    authentication_logfile_destination: str = Field(
        default=settings.TACACS_LOG_DIRECTORY + "%Y/%m/authentication-%Y-%m-%d.log"
    )
    authorization_logfile_destination: str = Field(
        default=settings.TACACS_LOG_DIRECTORY + "%Y/%m/authorization-%Y-%m-%d.log"
    )
    accounting_logfile_destination: str = Field(
        default=settings.TACACS_LOG_DIRECTORY + "%Y/%m/accounting-%Y-%m-%d.log"
    )
    login_backend: str = Field(default="mavis")
    user_backend: str = Field(default="mavis")
    pap_backend: str = Field(default="mavis")
    timezone: str = Field(default="UTC")


class TacacsNgSettingCreate(TacacsNgSettingBase):
    pass


class TacacsNgSettingUpdate(TacacsNgSettingBase):
    pass


# Database model, database table inferred from class name
class TacacsNgSetting(TacacsNgSettingBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


# Properties to return via API, id is always required
class TacacsNgSettingPublic(TacacsNgSettingBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TacacsNgSettingsPublic(SQLModel):
    data: list[TacacsNgSettingPublic]
    count: int


class MavisBase(SQLModel):
    mavis_key: str = Field(index=True, unique=True, max_length=255)
    mavis_value: str = Field(max_length=255)


class MavisCreate(MavisBase):
    pass


class MavisUpdate(MavisBase):
    pass


# Database model, database table inferred from class name
class Mavis(MavisBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


# Properties to return via API, id is always required
class MavisPublic(MavisBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class MavisesPublic(SQLModel):
    data: list[MavisPublic]
    count: int


class MavisPreviewPublic(SQLModel):
    data: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class HostBase(SQLModel):
    name: str = Field(index=True, unique=True, max_length=255)
    ipv4_address: str | None = None
    ipv6_address: str | None = None
    secret_key: str | None = Field(default=None, max_length=255)
    welcome_banner: str | None = None
    reject_banner: str | None = None
    motd_banner: str | None = None
    failed_authentication_banner: str | None = None
    parent: str | None = None
    generate_config: bool = Field(default=True)
    description: str | None = None


def _require_key_or_parent(host: "HostBase") -> "HostBase":
    # A host without a parent has nothing to inherit its key from.
    if not host.secret_key and not host.parent:
        raise ValueError("secret_key is required unless a parent host is set")
    return host


class HostCreate(HostBase):
    @model_validator(mode="after")
    def _check_key_or_parent(self) -> "HostCreate":
        _require_key_or_parent(self)
        return self


class HostUpdate(HostBase):
    @model_validator(mode="after")
    def _check_key_or_parent(self) -> "HostUpdate":
        _require_key_or_parent(self)
        return self


# Database model, database table inferred from class name
class Host(HostBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


# Properties to return via API, id is always required
class HostPublic(HostBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class HostsPublic(SQLModel):
    data: list[HostPublic]
    count: int


class TacacsGroupBase(SQLModel):
    group_name: str = Field(index=True, unique=True, max_length=255)
    generate_config: bool = Field(default=True)
    description: str | None = None


class TacacsGroupCreate(TacacsGroupBase):
    pass


class TacacsGroupUpdate(TacacsGroupBase):
    pass


# Database model, database table inferred from class name
class TacacsGroup(TacacsGroupBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


# Properties to return via API, id is always required
class TacacsGroupPublic(TacacsGroupBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TacacsGroupsPublic(SQLModel):
    data: list[TacacsGroupPublic]
    count: int


# -- Tacacs User Table ---
class TacacsUserBase(SQLModel):
    username: str = Field(index=True, unique=True, max_length=255)
    password_type: str = Field(index=True, max_length=255)
    member: str = Field(index=True, max_length=255)
    generate_config: bool = Field(default=True)
    description: str | None = None
    password: str | None = None
    email: str | None = Field(default=None, max_length=255)
    # Last day the account may log in. Past this date the user is left out of the
    # generated config (takes effect on the next Generate + Activate).
    account_expires_at: date | None = None


_email_adapter: TypeAdapter[EmailStr] = TypeAdapter(EmailStr)


def _normalise_email(value: str | None) -> str | None:
    """Blank -> None; anything else must be a syntactically valid address.

    Applied on Create/Update only, not on Base: the table and Public models also
    inherit Base, and validating there would make a row with a malformed stored
    address unreadable.
    """
    if value is None or not value.strip():
        return None
    return str(_email_adapter.validate_python(value.strip()))


class TacacsUserCreate(TacacsUserBase):
    password: str | None = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str | None) -> str | None:
        return _normalise_email(value)


class TacacsUserUpdate(SQLModel):
    username: str | None = Field(default=None, max_length=255)
    password_type: str | None = Field(default=None, max_length=255)
    member: str | None = Field(default=None, max_length=255)
    description: str | None = None
    generate_config: bool | None = Field(default=None)
    password: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    account_expires_at: date | None = None

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str | None) -> str | None:
        return _normalise_email(value)


# Database model, database table inferred from class name
class TacacsUser(TacacsUserBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    password: str | None = Field(default=None, max_length=255)


# Properties to return via API — password is explicitly excluded
class TacacsUserPublic(SQLModel):
    id: uuid.UUID
    username: str
    password_type: str
    member: str
    generate_config: bool = True
    description: str | None = None
    email: str | None = None
    account_expires_at: date | None = None
    created_at: datetime
    updated_at: datetime


class TacacsUsersPublic(SQLModel):
    data: list[TacacsUserPublic]
    count: int


# -- TacacsService Table ---
class TacacsServiceBase(SQLModel):
    name: str = Field(index=True, unique=True, max_length=255)
    generate_config: bool = Field(default=True)
    description: str | None = None


class TacacsServiceCreate(TacacsServiceBase):
    pass


class TacacsServiceUpdate(TacacsServiceBase):
    pass


# Database model, database table inferred from class name
class TacacsService(TacacsServiceBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


# Properties to return via API, id is always required
class TacacsServicePublic(TacacsServiceBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TacacsServicesPublic(SQLModel):
    data: list[TacacsServicePublic]
    count: int


# -- Begin Profile and Profile Script Tables --
# -- Profile Table ---
class ProfileBase(SQLModel):
    name: str = Field(index=True, unique=True, max_length=255)
    # Fallback action after the structured scripts; not emitted for a raw
    # script, which ends with its own permit/deny.
    action: str = Field(index=True, max_length=255)
    generate_config: bool = Field(default=True)
    description: str | None = None
    # Raw tac_plus-ng text for the profile's `script { }` body (#359). Set =
    # raw mode: emitted verbatim in place of Profile Scripts, which a raw
    # profile may not have.
    raw_script: str | None = Field(
        default=None, sa_column=Column(sa.Text, nullable=True)
    )


class ProfileCreate(ProfileBase):
    # Checked here for new text only, never on Base, so a stored row that an
    # older or newer check would reject stays readable.
    @model_validator(mode="after")
    def _check_raw_script(self) -> "ProfileCreate":
        self.raw_script = normalize_raw_script(self.raw_script)
        return self


class ProfileUpdate(ProfileBase):
    # Only cleaned here. crud.profiles.update_profile checks the text when it
    # differs from what is stored, so a partial update (MCP update_entity
    # merges the stored row) can still rename or disable a profile whose
    # stored text a newer check would reject.
    @model_validator(mode="after")
    def _clean_raw_script(self) -> "ProfileUpdate":
        text = self.raw_script
        if text is not None:
            text = text.strip("\n").rstrip()
            self.raw_script = text if text.strip() else None
        return self


# Database model, database table inferred from class name
class Profile(ProfileBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    profile_scripts: list["ProfileScript"] = Relationship(
        back_populates="profile", cascade_delete=True
    )


# Properties to return via API, id is always required
class ProfilePreviewPublic(SQLModel):
    data: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProfileRawCheck(SQLModel):
    """A raw script to syntax-check in the full config before saving it."""

    id: uuid.UUID | None = None  # the profile being edited; None for a new one
    name: str = Field(min_length=1, max_length=255)
    raw_script: str


class ProfileRawCheckResult(SQLModel):
    status: str  # success / error
    message: str
    line: int  # line in the full candidate config, 0 when unknown
    script_line: int | None = None  # the same line within the raw script


class ProfilePublic(ProfileBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ProfilesPublic(SQLModel):
    data: list[ProfilePublic]
    count: int


# -- Profile Script  Table ---
class ProfileScriptBase(SQLModel):
    condition: str = Field(index=True, max_length=255)
    key: str = Field(index=True, max_length=255)
    value: str = Field(index=True, max_length=255)
    action: str = Field(index=True, max_length=255)
    description: str | None = None
    profile_id: uuid.UUID | None = None


class ProfileScriptCreate(ProfileScriptBase):
    # 0-based index among siblings. Omit on create to append at the end; on
    # update, omit to keep the current place.
    position: int | None = Field(default=None, ge=0)


class ProfileScriptUpdate(ProfileScriptBase):
    # 0-based index among siblings. Omit on create to append at the end; on
    # update, omit to keep the current place.
    position: int | None = Field(default=None, ge=0)


# Database model, database table inferred from class name
class ProfileScript(ProfileScriptBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Evaluation order: tac_plus-ng stops at the first matching permit/deny.
    position: int = Field(
        default=0, nullable=False, sa_column_kwargs={"server_default": "0"}
    )
    profile_id: uuid.UUID = Field(
        foreign_key="profile.id", nullable=False, ondelete="CASCADE"
    )
    profile: Profile | None = Relationship(back_populates="profile_scripts")

    profile_script_sets: list["ProfileScriptSet"] = Relationship(
        back_populates="profile_script",
        cascade_delete=True,
    )


# Properties to return via API, id is always required
class ProfileScriptPublic(ProfileScriptBase):
    id: uuid.UUID
    position: int
    profile_id: uuid.UUID
    profile_name: str | None = None
    created_at: datetime
    updated_at: datetime


class ProfileScriptsPublic(SQLModel):
    data: list[ProfileScriptPublic]
    count: int


# -- Profile Script Set Table ---
class ProfileScriptSetBase(SQLModel):
    key: str = Field(index=True, max_length=255)
    value: str
    description: str | None = None
    profilescript_id: uuid.UUID


class ProfileScriptSetCreate(ProfileScriptSetBase):
    pass


class ProfileScriptSetUpdate(ProfileScriptSetBase):
    pass


# Database model, database table inferred from class name
class ProfileScriptSet(ProfileScriptSetBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    profilescript_id: uuid.UUID = Field(
        foreign_key="profilescript.id",
        nullable=False,
        ondelete="CASCADE",
    )
    profile_script: "ProfileScript" = Relationship(back_populates="profile_script_sets")


# Properties to return via API, id is always required
class ProfileScriptSetPublic(ProfileScriptSetBase):
    id: uuid.UUID
    profile_id: uuid.UUID | None = None
    profile_name: str | None = None
    profilescript_block: str | None = None
    created_at: datetime
    updated_at: datetime


class ProfileScriptSetsPublic(SQLModel):
    data: list[ProfileScriptSetPublic]
    count: int


# -- End Profile and Profile Script Tables --


# -- Begin Ruleset Table --
# -- Ruleset Table ---
class RulesetBase(SQLModel):
    name: str = Field(index=True, unique=True, max_length=255)
    enabled: str = Field(default="yes")
    action: str = Field(index=True, max_length=255)
    generate_config: bool = Field(default=True)
    description: str | None = None


class RulesetCreate(RulesetBase):
    # 0-based index among siblings. Omit on create to append at the end; on
    # update, omit to keep the current place.
    position: int | None = Field(default=None, ge=0)


class RulesetUpdate(RulesetBase):
    # 0-based index among siblings. Omit on create to append at the end; on
    # update, omit to keep the current place.
    position: int | None = Field(default=None, ge=0)


# Database model, database table inferred from class name
class Ruleset(RulesetBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Evaluation order: tac_plus-ng stops at the first matching permit/deny.
    position: int = Field(
        default=0, nullable=False, sa_column_kwargs={"server_default": "0"}
    )
    ruleset_scripts: list["RulesetScript"] = Relationship(
        back_populates="ruleset", cascade_delete=True
    )


# Properties to return via API, id is always required
class RulesetPreviewPublic(SQLModel):
    data: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RulesetPublic(RulesetBase):
    id: uuid.UUID
    position: int
    created_at: datetime
    updated_at: datetime


class RulesetsPublic(SQLModel):
    data: list[RulesetPublic]
    count: int


# -- Ruleset Script  Table ---
class RulesetScriptBase(SQLModel):
    condition: str = Field(index=True, max_length=255)
    key: str = Field(index=True, max_length=255)
    value: str = Field(index=True, max_length=255)
    action: str = Field(index=True, max_length=255)
    description: str | None = None
    ruleset_id: uuid.UUID = Field(nullable=False)


class RulesetScriptCreate(RulesetScriptBase):
    # 0-based index among siblings. Omit on create to append at the end; on
    # update, omit to keep the current place.
    position: int | None = Field(default=None, ge=0)


class RulesetScriptUpdate(RulesetScriptBase):
    # 0-based index among siblings. Omit on create to append at the end; on
    # update, omit to keep the current place.
    position: int | None = Field(default=None, ge=0)


# Database model, database table inferred from class name
class RulesetScript(RulesetScriptBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Evaluation order: tac_plus-ng stops at the first matching permit/deny.
    position: int = Field(
        default=0, nullable=False, sa_column_kwargs={"server_default": "0"}
    )
    ruleset_id: uuid.UUID = Field(
        foreign_key="ruleset.id", nullable=False, ondelete="CASCADE"
    )
    ruleset: Ruleset | None = Relationship(back_populates="ruleset_scripts")

    ruleset_script_sets: list["RulesetScriptSet"] = Relationship(
        back_populates="ruleset_script", cascade_delete=True
    )


# Properties to return via API, id is always required
class RulesetScriptPublic(RulesetScriptBase):
    id: uuid.UUID
    position: int
    ruleset_name: str | None = None
    created_at: datetime
    updated_at: datetime


class RulesetScriptsPublic(SQLModel):
    data: list[RulesetScriptPublic]
    count: int


# -- Ruleset Script Set  Table ---
class RulesetScriptSetBase(SQLModel):
    key: str = Field(index=True, max_length=255)
    value: str = Field(index=True, max_length=255)
    description: str | None = None
    rulesetscript_id: uuid.UUID


class RulesetScriptSetCreate(RulesetScriptSetBase):
    pass


class RulesetScriptSetUpdate(RulesetScriptSetBase):
    pass


# Database model, database table inferred from class name
class RulesetScriptSet(RulesetScriptSetBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    rulesetscript_id: uuid.UUID = Field(
        foreign_key="rulesetscript.id",
        nullable=False,
        ondelete="CASCADE",
    )
    ruleset_script: RulesetScript | None = Relationship(
        back_populates="ruleset_script_sets"
    )


# Properties to return via API, id is always required
class RulesetScriptSetPublic(RulesetScriptSetBase):
    id: uuid.UUID
    ruleset_id: uuid.UUID | None = None
    ruleset_name: str | None = None
    rulesetscript_block: str | None = None
    created_at: datetime
    updated_at: datetime


class RulesetScriptSetsPublic(SQLModel):
    data: list[RulesetScriptSetPublic]
    count: int


class PositionMove(SQLModel):
    """Target of a reorder: the 0-based index among siblings, clamped to bounds."""

    position: int = Field(ge=0)


# --- End of TACACS+ Configuration Tables ---


# -- Tacacs Config File Table ---
class TacacsConfigBase(SQLModel):
    filename: str = Field(index=True, unique=True, max_length=255)
    description: str | None = None


class TacacsConfigCreate(TacacsConfigBase):
    filename: str = Field(index=True, unique=True, max_length=30)


class TacacsConfigUpdate(TacacsConfigBase):
    filename: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None)
    data: str | None = Field(default=None)
    active: bool | None = Field(default=None)


# Database model, database table inferred from class name
class TacacsConfig(TacacsConfigBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    active: bool = Field(default=False)
    # The saved config text, replicated with the row so an HA standby can run
    # exactly what was activated instead of regenerating from the live DB.
    # NULL for configs saved before this column existed.
    config_text: str | None = Field(
        default=None, sa_column=Column(sa.Text, nullable=True)
    )


# Properties to return via API, id is always required
class TacacsConfigPreviewPublic(SQLModel):
    created_at: datetime
    data: str | None = None
    updated_at: datetime


class DefaultCredentialFinding(SQLModel):
    """A TACACS+ user or host that still uses the public demo secret."""

    kind: Literal["tacacs_user", "host"]
    id: uuid.UUID
    name: str


class DefaultCredentialsPublic(SQLModel):
    data: list[DefaultCredentialFinding]
    count: int


class TacacsConfigPublic(TacacsConfigBase):
    id: uuid.UUID
    active: bool
    created_at: datetime
    updated_at: datetime
    data: str | None = None


class TacacsConfigsPublic(SQLModel):
    data: list[TacacsConfigPublic]
    count: int


# -- Tacacs Log File Table ---
class TacacsLogBase(SQLModel):
    filename: str = Field(index=True, max_length=255)
    filepath: str = Field(index=True, max_length=1024)
    created_at: datetime = Field(default_factory=_utc_now)


class TacacsLogCreate(TacacsLogBase):
    pass


class TacacsLogUpdate(TacacsLogBase):
    pass


# Database model, database table inferred from class name
class TacacsLog(TacacsLogBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    updated_at: datetime = Field(
        default_factory=_utc_now, sa_column_kwargs={"onupdate": _utc_now}
    )


# Properties to return via API, id is always required
class TacacsLogPublic(TacacsLogBase):
    id: uuid.UUID
    updated_at: datetime
    data: str | None = None


class TacacsLogsPublic(SQLModel):
    data: list[TacacsLogPublic]
    count: int


class TacacsLogEvent(SQLModel):
    timestamp: str
    log_type: str  # "authentication" | "authorization" | "accounting"
    username: str
    nas_ip: str
    client_ip: str
    result: str  # "success" | "failed" | "permit" | "deny" | "start" | "stop"
    message: str
    command: str | None = (
        None  # extracted command/service from authorization/accounting messages
    )
    port: str | None = None  # tty/port (e.g. vty14, tty0)
    session_id: str | None = (
        None  # logical session grouping key (username+nas_ip+client_ip+port)
    )


class TacacsLogEventsPublic(SQLModel):
    data: list[TacacsLogEvent]
    count: int


class TacacsLogTypeSummary(SQLModel):
    success: int = 0
    failed: int = 0
    permit: int = 0
    deny: int = 0
    start: int = 0
    stop: int = 0
    total: int = 0


class TacacsLogDailySummary(SQLModel):
    date: str
    authentication: TacacsLogTypeSummary
    authorization: TacacsLogTypeSummary
    accounting: TacacsLogTypeSummary
    excluded_users: list[str] = []


class TacacsLogLatestDate(SQLModel):
    date: str


# -- Tacacs Custom Section Table ---
class ConfigurationOptionBase(SQLModel):
    name: str = Field(index=True, unique=True, max_length=255)
    config_option: str
    description: str | None = None


class ConfigurationOptionCreate(ConfigurationOptionBase):
    pass


class ConfigurationOptionUpdate(ConfigurationOptionBase):
    pass


# Database model, database table inferred from class name
class ConfigurationOption(ConfigurationOptionBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


# Properties to return via API, id is always required


class ConfigurationOptionPublic(ConfigurationOptionBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ConfigurationOptionsPublic(SQLModel):
    data: list[ConfigurationOptionPublic]
    count: int


# -- Authentication Statistics Table ---
class AuthenticationStatisticsBase(SQLModel):
    node_name: str = Field(default="primary", index=True, max_length=255)
    username: str = Field(index=True, max_length=255)
    nas_ip: str = Field(index=True, max_length=1024)
    user_source_ip: str = Field(index=True, max_length=1024)
    success_count: int = Field(default=0)
    fail_count: int = Field(default=0)
    # The calendar day of the log file the counts come from, in the log
    # timezone. A plain date: a timestamp here was shifted a day by the
    # PostgreSQL session timezone (#356).
    log_date: date


class AuthenticationStatisticsCreate(AuthenticationStatisticsBase):
    pass


class AuthenticationStatisticsUpdate(AuthenticationStatisticsBase):
    pass


# Database model, database table inferred from class name
class AuthenticationStatistics(
    AuthenticationStatisticsBase, TimestampModel, table=True
):
    __table_args__ = (
        UniqueConstraint(
            "username",
            "nas_ip",
            "user_source_ip",
            "log_date",
            "node_name",
            name="uq_authenticationstatistics_username_nas_ip_src_ip_log_date_nod",
        ),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


# Properties to return via API, id is always required
class AuthenticationStatisticPublic(AuthenticationStatisticsBase):
    id: uuid.UUID
    updated_at: datetime


class AuthenticationStatisticsPublic(SQLModel):
    data: list[AuthenticationStatisticPublic]
    count: int


# -- Authrorization Statistics Table ---
class AuthorizationStatisticsBase(SQLModel):
    node_name: str = Field(default="primary", index=True, max_length=255)
    username: str = Field(index=True, max_length=255)
    nas_ip: str = Field(index=True, max_length=1024)
    user_source_ip: str = Field(index=True, max_length=1024)
    permit_count: int = Field(default=0)
    deny_count: int = Field(default=0)
    # The calendar day of the log file the counts come from, in the log
    # timezone. A plain date: a timestamp here was shifted a day by the
    # PostgreSQL session timezone (#356).
    log_date: date


class AuthorizationStatisticsCreate(AuthorizationStatisticsBase):
    pass


class AuthorizationStatisticsUpdate(AuthorizationStatisticsBase):
    pass


# Database model, database table inferred from class name
class AuthorizationStatistics(AuthorizationStatisticsBase, TimestampModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "username",
            "nas_ip",
            "user_source_ip",
            "log_date",
            "node_name",
            name="uq_authorizationstatistics_username_nas_ip_src_ip_log_date_node",
        ),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


# Properties to return via API, id is always required
class AuthorizationStatisticPublic(AuthorizationStatisticsBase):
    id: uuid.UUID
    updated_at: datetime


class AuthorizationStatisticsPublic(SQLModel):
    data: list[AuthorizationStatisticPublic]
    count: int


# --- Accounting Statistics Table ---
class AccountingStatisticsBase(SQLModel):
    node_name: str = Field(default="primary", index=True, max_length=255)
    username: str = Field(index=True, max_length=255)
    nas_ip: str = Field(index=True, max_length=1024)
    user_source_ip: str = Field(index=True, max_length=1024)
    start_count: int = Field(default=0)
    stop_count: int = Field(default=0)
    # The calendar day of the log file the counts come from, in the log
    # timezone. A plain date: a timestamp here was shifted a day by the
    # PostgreSQL session timezone (#356).
    log_date: date


class AccountingStatisticsCreate(AccountingStatisticsBase):
    pass


class AccountingStatisticsUpdate(AccountingStatisticsBase):
    pass


# Database model, database table inferred from class name
class AccountingStatistics(AccountingStatisticsBase, TimestampModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "username",
            "nas_ip",
            "user_source_ip",
            "log_date",
            "node_name",
            name="uq_accountingstatistics_username_nas_ip_src_ip_log_date_node",
        ),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


# Properties to return via API, id is always required
class AccountingStatisticPublic(AccountingStatisticsBase):
    id: uuid.UUID
    updated_at: datetime


class AccountingStatisticsPublic(SQLModel):
    data: list[AccountingStatisticPublic]
    count: int


# --- End of Accounting Statistics Table ---


# --- Statistics exclusions ---
# Usernames (service / automation accounts) left out of the AAA statistics and
# dashboards. Read-side only: nothing here reaches tac_plus-ng, the raw logs,
# the log viewer, alerting, anomaly scoring or SIEM forwarding.

# The log parsers only ever capture usernames matching [\w.-]+, so a pattern is
# that charset plus `*` as a wildcard.
_STATS_EXCLUSION_PATTERN_RE = re.compile(r"^[\w.*-]+$")


def _normalize_stats_exclusion_pattern(value: str) -> str:
    pattern = (value or "").strip().lower()
    if not pattern:
        raise ValueError("Pattern is required.")
    if not _STATS_EXCLUSION_PATTERN_RE.match(pattern):
        raise ValueError(
            "Pattern may only contain letters, digits, '_', '.', '-' and '*' "
            "as a wildcard."
        )
    if not pattern.strip("*"):
        raise ValueError("A pattern made only of '*' would exclude every user.")
    return pattern


class StatsExcludedUserBase(SQLModel):
    # Lower-cased username or glob ("svc_*"); matched case-insensitively.
    pattern: str = Field(max_length=255)
    note: str | None = Field(default=None, max_length=1024)


class StatsExcludedUserCreate(StatsExcludedUserBase):
    # Validated on the create payload only, as with ApiKeyCreate: a stored row
    # that a later build would reject must stay readable and deletable.
    @field_validator("pattern")
    @classmethod
    def _validate_pattern(cls, value: str) -> str:
        return _normalize_stats_exclusion_pattern(value)


class StatsExcludedUser(StatsExcludedUserBase, TimestampModel, table=True):
    pattern: str = Field(max_length=255, unique=True, index=True)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class StatsExcludedUserPublic(StatsExcludedUserBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class StatsExcludedUsersPublic(SQLModel):
    data: list[StatsExcludedUserPublic]
    count: int


# --- End of Statistics exclusions ---


class AaaStatisticsTodayPublic(SQLModel):
    authentication_failed_count_by_user: list[dict] = []
    authentication_success_count_by_user: list[dict] = []
    authorization_deny_count_by_user: list[dict] = []
    authentication_success_count_by_user_source_ip: list[dict] = []
    last_7_days_authentication_success: list[dict] = []
    last_7_days_authentication_fail: list[dict] = []
    last_7_days_authorization_permit: list[dict] = []
    last_7_days_authorization_deny: list[dict] = []
    last_7_days_accounting_start: list[dict] = []
    last_7_days_accounting_stop: list[dict] = []
    today: str | None = None
    today_total_authentication_events: int = 0
    today_list_authentication_details: list[dict] = []
    today_unique_user_nas_client_combinations: int = 0
    today_successful_logins: int = 0
    today_failed_logins: int = 0
    today_unique_user_source_ip_count: int = 0
    today_unique_nas_ip_count: int = 0

    today_authentication_failed_count_by_user: list[dict] = []
    today_authentication_success_count_by_user: list[dict] = []
    today_authentication_success_count_by_user_source_ip: list[dict] = []
    today_authentication_success_count_by_nas_ip: list[dict] = []
    # Patterns that were applied to these numbers; empty when none are
    # configured or the caller asked for include_excluded=true.
    excluded_users: list[str] = []


class AaaStatisticsDateRangePublic(SQLModel):
    authentication_failed_count_by_user: list[dict] = []
    authentication_success_count_by_user: list[dict] = []
    authorization_deny_count_by_user: list[dict] = []
    authentication_success_count_by_user_source_ip: list[dict] = []
    authentication_success_count_by_nas_ip: list[dict] = []
    last_range_days_authentication_success: list[dict] = []
    last_range_days_authentication_fail: list[dict] = []
    last_range_days_authorization_permit: list[dict] = []
    last_range_days_authorization_deny: list[dict] = []
    last_range_days_accounting_start: list[dict] = []
    last_range_days_accounting_stop: list[dict] = []
    excluded_users: list[str] = []


# --- WebAuthn / Passkey Tables ---


class WebAuthnCredential(SQLModel, table=True):
    __tablename__ = "webauthncredential"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True
    )
    credential_id: bytes = Field(
        sa_column=Column(sa.LargeBinary, unique=True, index=True, nullable=False)
    )
    public_key: bytes = Field(sa_column=Column(sa.LargeBinary, nullable=False))
    sign_count: int = Field(default=0, nullable=False)
    name: str | None = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=_utc_now, nullable=False)
    last_used_at: datetime | None = Field(default=None)

    user: User | None = Relationship(back_populates="webauthn_credentials")


class WebAuthnChallenge(SQLModel, table=True):
    __tablename__ = "webauthchallenge"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    challenge: bytes = Field(sa_column=Column(sa.LargeBinary, nullable=False))
    user_id: uuid.UUID | None = Field(default=None, index=True)
    expires_at: datetime = Field(
        sa_column=Column(sa.DateTime(timezone=True), nullable=False)
    )
    created_at: datetime = Field(default_factory=_utc_now, nullable=False)


# WebAuthn API schemas
class WebAuthnCredentialPublic(SQLModel):
    id: uuid.UUID
    credential_id: str  # base64url-encoded
    name: str | None
    created_at: datetime
    last_used_at: datetime | None


class WebAuthnCredentialsPublic(SQLModel):
    data: list[WebAuthnCredentialPublic]
    count: int


class PasskeyRegisterCompleteRequest(SQLModel):
    credential: dict  # type: ignore[type-arg]
    name: str | None = Field(default=None, max_length=100)


class PasskeyAuthenticateCompleteRequest(SQLModel):
    credential: dict  # type: ignore[type-arg]


# --- Auth Provider Config Table ---


class AuthProviderConfig(SQLModel, table=True):
    __tablename__ = "authproviderconfig"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    provider: str = Field(unique=True, index=True, max_length=32)
    enabled: bool = Field(default=False)
    config_json: str = Field(default="{}")
    encrypted_secret: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utc_now, nullable=False)
    updated_at: datetime = Field(
        default_factory=_utc_now, sa_column_kwargs={"onupdate": _utc_now}
    )


class AuthProviderConfigPublic(SQLModel):
    provider: str
    enabled: bool
    config: dict  # type: ignore[type-arg]
    secret_is_set: bool


class AuthProviderConfigUpdate(SQLModel):
    enabled: bool | None = None
    config: dict | None = None  # type: ignore[type-arg]
    secret: str | None = None


# Audit Logging


class AuditLogBase(SQLModel):
    action: str = Field(index=True, max_length=50)
    entity_type: str = Field(index=True, max_length=100)
    entity_id: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    user_agent: str | None = Field(default=None, max_length=512)
    old_values: str | None = Field(
        default=None, sa_column=Column(sa.Text, nullable=True)
    )
    new_values: str | None = Field(
        default=None, sa_column=Column(sa.Text, nullable=True)
    )


class AuditLogCreate(AuditLogBase):
    pass


class AuditLog(AuditLogBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID | None = Field(default=None, index=True)
    user_email: str = Field(max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)


class AuditLogPublic(AuditLogBase):
    id: uuid.UUID
    user_id: uuid.UUID | None
    user_email: str
    ip_address: str | None
    created_at: datetime


class AuditLogsPublic(SQLModel):
    data: list[AuditLogPublic]
    count: int


# ---------------------------------------------------------------------------
# Alert Rules
# ---------------------------------------------------------------------------


class AlertRuleBase(SQLModel):
    name: str = Field(index=True, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    enabled: bool = Field(default=True)
    log_type: str = Field(max_length=50)  # auth/authz/accounting/all/config
    condition_field: str = Field(
        max_length=100
    )  # username/nas_ip/client_ip/result/command/config_action
    condition_operator: str = Field(
        max_length=50
    )  # gt/lt/eq/contains/new_value/any_change/created/updated/deleted/activated
    threshold: float | None = Field(default=None)
    time_window_minutes: int = Field(default=10)
    severity: str = Field(default="medium", max_length=20)  # low/medium/high/critical
    cooldown_minutes: int = Field(default=60)
    is_system: bool = Field(default=False)


class AlertRuleCreate(AlertRuleBase):
    pass


class AlertRuleUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    log_type: str | None = None
    condition_field: str | None = None
    condition_operator: str | None = None
    threshold: float | None = None
    time_window_minutes: int | None = None
    severity: str | None = None
    cooldown_minutes: int | None = None


class AlertRule(AlertRuleBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    last_fired_at: datetime | None = Field(default=None)
    alert_events: list["AlertEvent"] = Relationship(
        back_populates="alert_rule", cascade_delete=True
    )


class AlertRulePublic(AlertRuleBase):
    id: uuid.UUID
    last_fired_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AlertRulesPublic(SQLModel):
    data: list[AlertRulePublic]
    count: int


# ---------------------------------------------------------------------------
# Notification Channels
# ---------------------------------------------------------------------------


class NotificationChannelBase(SQLModel):
    name: str = Field(index=True, max_length=255)
    channel_type: str = Field(max_length=50)  # telegram/slack/discord/teams/webhook
    config_json: str = Field(default="{}")  # JSON: bot_token+chat_id or webhook_url
    enabled: bool = Field(default=True)


class NotificationChannelCreate(NotificationChannelBase):
    pass


class NotificationChannelUpdate(SQLModel):
    name: str | None = None
    channel_type: str | None = None
    config_json: str | None = None
    enabled: bool | None = None


class NotificationChannel(NotificationChannelBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # The database sets alertevent.channel_id to NULL on delete; the ORM must
    # neither delete the events nor load them to do it itself.
    alert_events: list["AlertEvent"] = Relationship(
        back_populates="notification_channel", passive_deletes=True
    )


class NotificationChannelPublic(NotificationChannelBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class NotificationChannelsPublic(SQLModel):
    data: list[NotificationChannelPublic]
    count: int


# ---------------------------------------------------------------------------
# Alert Events
# ---------------------------------------------------------------------------


class AlertEventBase(SQLModel):
    triggered_at: datetime = Field(default_factory=_utc_now)
    payload_snapshot: str | None = Field(
        default=None, sa_column=Column(sa.Text, nullable=True)
    )
    # sent / failed: one row per channel the alert was dispatched to.
    # no_channel: the rule fired while no channel was enabled; one row, no
    # channel, so the history and payload survive a rollout without channels.
    status: str = Field(default="sent", max_length=20)
    error_message: str | None = Field(default=None, max_length=1024)


class AlertEvent(AlertEventBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    rule_id: uuid.UUID = Field(
        foreign_key="alertrule.id", nullable=False, ondelete="CASCADE", index=True
    )
    # NULL for no_channel events, and for events whose channel was deleted:
    # SET NULL keeps the history when a channel is removed or replaced.
    channel_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="notificationchannel.id",
        nullable=True,
        ondelete="SET NULL",
        index=True,
    )
    alert_rule: AlertRule | None = Relationship(back_populates="alert_events")
    notification_channel: NotificationChannel | None = Relationship(
        back_populates="alert_events"
    )


class AlertEventPublic(AlertEventBase):
    id: uuid.UUID
    rule_id: uuid.UUID
    channel_id: uuid.UUID | None
    rule_name: str | None = None
    channel_name: str | None = None
    rule_severity: str | None = None
    created_at: datetime


class AlertEventsPublic(SQLModel):
    data: list[AlertEventPublic]
    count: int


class AlertStatisticsSeverityItem(SQLModel):
    severity: str
    count: int


class AlertStatisticsRuleItem(SQLModel):
    rule_name: str
    count: int


class AlertStatistics(SQLModel):
    total: int
    sent: int
    failed: int
    no_channel: int = 0
    by_severity: list[AlertStatisticsSeverityItem]
    by_rule: list[AlertStatisticsRuleItem]
    last_24h: int
    last_7d: int


# ---------------------------------------------------------------------------
# Anomaly Detection Results
# ---------------------------------------------------------------------------


class AnomalyDetectionResultBase(SQLModel):
    subject_type: str = Field(max_length=20)  # "username" | "nas_ip"
    subject_value: str = Field(max_length=255, index=True)
    scored_at: datetime = Field(default_factory=_utc_now)
    anomaly_score: float
    is_anomaly: bool = Field(default=False)
    risk_level: str = Field(
        default="normal", max_length=20
    )  # normal/low/medium/high/critical
    feature_snapshot: str | None = Field(
        default=None, sa_column=Column(sa.Text, nullable=True)
    )


class AnomalyDetectionResult(AnomalyDetectionResultBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class AnomalyDetectionResultPublic(AnomalyDetectionResultBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AnomalyDetectionResultsPublic(SQLModel):
    data: list[AnomalyDetectionResultPublic]
    count: int
    count: int


class HaState(SQLModel, table=True):
    """Singleton row (id=1) tracking confirmed HA sync timestamps."""

    id: int = Field(default=1, primary_key=True)
    last_push_at: datetime | None = Field(default=None, nullable=True)
    last_received_at: datetime | None = Field(default=None, nullable=True)


# --- Multi-Node HA Config ---


class HaConfigBase(SQLModel):
    node_name: str = Field(default="primary", max_length=100)
    sync_mode: str = Field(default="auto", max_length=10)
    scheduler_enabled: bool = Field(default=True)
    stats_interval_minutes: int = Field(default=30)


class HaConfig(HaConfigBase, TimestampModel, table=True):
    """Singleton row (id=1). Written only on primary; replicated to standbys."""

    id: int = Field(default=1, primary_key=True)


class HaConfigUpdate(SQLModel):
    node_name: str | None = None
    sync_mode: Literal["auto", "manual"] | None = None
    scheduler_enabled: bool | None = None
    stats_interval_minutes: int | None = None


class HaConfigPublic(HaConfigBase):
    id: int
    updated_at: datetime


class HaPeerNodeBase(SQLModel):
    name: str = Field(max_length=100)
    url: str = Field(max_length=500)
    enabled: bool = Field(default=True)


class HaPeerNode(HaPeerNodeBase, TimestampModel, table=True):
    """One row per standby peer. Written only on primary."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class HaPeerNodeCreate(HaPeerNodeBase):
    pass


class HaPeerNodeUpdate(SQLModel):
    name: str | None = None
    url: str | None = None
    enabled: bool | None = None


class HaPeerNodePublic(HaPeerNodeBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class HaPeerNodesPublic(SQLModel):
    data: list[HaPeerNodePublic]
    count: int


class HaNodeState(SQLModel, table=True):
    """Per-peer sync state written only by the primary after each push."""

    peer_id: uuid.UUID = Field(
        primary_key=True,
        foreign_key="hapeernode.id",
        ondelete="CASCADE",
    )
    last_push_at: datetime | None = Field(default=None, nullable=True)
    last_available: bool | None = Field(default=None, nullable=True)


# --- API Keys (machine credentials, currently used by the MCP server) ---


def _normalize_allowed_ips(value: str | None) -> str | None:
    """Validate a comma-separated IP/CIDR list, normalizing to canonical form.

    Each entry must parse as an IP address or network (IPv4 or IPv6);
    ``ip_network(..., strict=False)`` also accepts bare addresses as /32 or
    /128 networks, so a single parse call covers both forms. Empty input (or
    input that reduces to no entries) normalizes to None, meaning "no
    restriction" — matches the pre-migration behavior of every existing key.
    """
    if not value:
        return None
    entries = []
    for raw_entry in value.split(","):
        entry = raw_entry.strip()
        if not entry:
            continue
        try:
            ip_network(entry, strict=False)
        except ValueError as e:
            raise ValueError(
                f"'{entry}' is not a valid IP address or CIDR network."
            ) from e
        entries.append(entry)
    return ",".join(entries) if entries else None


# The complete set of scope strings an API key may carry. `mcp:read` and
# `mcp:write` are the two access levels (write implies read); `mcp:secrets` is an
# independent opt-in for unredacted output. Enforced below so a typo fails at key
# creation instead of silently granting nothing.
ALLOWED_API_KEY_SCOPES: frozenset[str] = frozenset(
    {"mcp:read", "mcp:write", "mcp:secrets"}
)


def _normalize_scopes(value: str) -> str:
    entries: list[str] = []
    for raw in (value or "").split(","):
        entry = raw.strip()
        if not entry:
            continue
        if entry not in ALLOWED_API_KEY_SCOPES:
            raise ValueError(
                f"'{entry}' is not a valid scope. "
                f"Valid scopes: {', '.join(sorted(ALLOWED_API_KEY_SCOPES))}."
            )
        if entry not in entries:
            entries.append(entry)
    if not entries:
        raise ValueError("At least one scope is required.")
    return ",".join(entries)


class ApiKeyBase(SQLModel):
    name: str = Field(max_length=255)
    # Comma-separated scope list, e.g. "mcp:write,mcp:secrets".
    scopes: str = Field(default="mcp:read", max_length=512)
    # Comma-separated list of IPv4/IPv6 addresses or CIDR networks this key
    # may authenticate from. None/empty means "no restriction".
    allowed_ips: str | None = Field(default=None, max_length=1024)
    description: str | None = Field(default=None, max_length=1024)
    expires_at: datetime | None = Field(default=None)

    @field_validator("allowed_ips")
    @classmethod
    def _validate_allowed_ips(cls, value: str | None) -> str | None:
        return _normalize_allowed_ips(value)


class ApiKeyCreate(ApiKeyBase):
    # Defaults to the calling superuser when omitted.
    user_id: uuid.UUID | None = Field(default=None)
    # Convenience: when expires_at is not given, it is derived from this.
    expires_in_days: int | None = Field(default=None)

    # Validated on the create payload rather than on ApiKeyBase: ApiKeyPublic
    # and the table model also inherit Base, and a stored row carrying a scope
    # string this build no longer recognises must still be readable and
    # revocable rather than blowing up response serialization.
    @field_validator("scopes")
    @classmethod
    def _validate_scopes(cls, value: str) -> str:
        return _normalize_scopes(value)


class ApiKeyAllowedIpsUpdate(SQLModel):
    """Restricted update payload: only the allowlist may be edited post-creation."""

    allowed_ips: str | None = Field(default=None, max_length=1024)

    @field_validator("allowed_ips")
    @classmethod
    def _validate_allowed_ips(cls, value: str | None) -> str | None:
        return _normalize_allowed_ips(value)


class ApiKey(ApiKeyBase, TimestampModel, table=True):
    # Table name is inferred from the class name: "apikey".
    #
    # The lifecycle timestamps below use `DateTime(timezone=True)` rather than
    # the project's usual naive columns. Writing an aware UTC value into a
    # `timestamp without time zone` column makes psycopg convert it to the
    # session's local zone and drop the offset, so an expiry read back as UTC
    # would land hours in the future — an expired key would keep authenticating.
    # Same approach as WebAuthnChallenge.expires_at.
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True
    )
    # Display-only leading fragment of the plaintext key, e.g. "tngk_a1b2c3d4".
    key_prefix: str = Field(max_length=20, index=True)
    # Hex HMAC-SHA256 of the plaintext key; the plaintext is never stored.
    key_hash: str = Field(max_length=64, unique=True, index=True)
    expires_at: datetime | None = Field(
        default=None, sa_column=Column(sa.DateTime(timezone=True), nullable=True)
    )
    last_used_at: datetime | None = Field(
        default=None, sa_column=Column(sa.DateTime(timezone=True), nullable=True)
    )
    last_used_ip: str | None = Field(default=None, max_length=45)
    revoked_at: datetime | None = Field(
        default=None, sa_column=Column(sa.DateTime(timezone=True), nullable=True)
    )
    created_by_id: uuid.UUID | None = Field(default=None, index=True)


# Deliberately omits key_hash so no route can leak it.
class ApiKeyPublic(ApiKeyBase):
    id: uuid.UUID
    user_id: uuid.UUID
    key_prefix: str
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApiKeysPublic(SQLModel):
    data: list[ApiKeyPublic]
    count: int


class ApiKeyCreated(ApiKeyPublic):
    """Returned only by the create endpoint — the one time the secret exists."""

    plaintext_key: str
