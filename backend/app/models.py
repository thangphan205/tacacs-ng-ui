import uuid
from datetime import datetime

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel
from typing import List, Optional
from app.core.config import settings


class TimestampModel(SQLModel):
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow},
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


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


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
    ipv4_address: Optional[str] = None
    ipv6_address: Optional[str] = None
    secret_key: str = Field(max_length=255)
    welcome_banner: Optional[str] = None
    reject_banner: Optional[str] = None
    motd_banner: Optional[str] = None
    failed_authentication_banner: Optional[str] = None
    parent: Optional[str] = None
    description: Optional[str] = None


class HostCreate(HostBase):
    pass


class HostUpdate(HostBase):
    pass


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
    description: Optional[str] = None


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
    description: Optional[str] = None
    password: Optional[str] = None


class TacacsUserCreate(TacacsUserBase):
    password: str | None = Field(default=None, max_length=255)


class TacacsUserUpdate(TacacsUserBase):
    password: str | None = Field(default=None, max_length=255)


# Database model, database table inferred from class name
class TacacsUser(TacacsUserBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    password: str | None = Field(default=None, max_length=255)


# Properties to return via API, id is always required
class TacacsUserPublic(TacacsUserBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TacacsUsersPublic(SQLModel):
    data: list[TacacsUserPublic]
    count: int


# -- TacacsService Table ---
class TacacsServiceBase(SQLModel):
    name: str = Field(index=True, unique=True, max_length=255)
    description: Optional[str] = None


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
    action: str = Field(index=True, max_length=255)
    description: Optional[str] = None


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(ProfileBase):
    pass


# Database model, database table inferred from class name
class Profile(ProfileBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    profile_scripts: List["ProfileScript"] = Relationship(
        back_populates="profile", cascade_delete=True
    )


# Properties to return via API, id is always required
class ProfilePreviewPublic(SQLModel):
    data: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


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
    description: Optional[str] = None
    profile_id: uuid.UUID | None = None


class ProfileScriptCreate(ProfileScriptBase):
    pass


class ProfileScriptUpdate(ProfileScriptBase):
    pass


# Database model, database table inferred from class name
class ProfileScript(ProfileScriptBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    profile_id: uuid.UUID = Field(
        foreign_key="profile.id", nullable=False, ondelete="CASCADE"
    )
    profile: Profile | None = Relationship(back_populates="profile_scripts")

    profile_script_sets: List["ProfileScriptSet"] = Relationship(
        back_populates="profile_script",
        cascade_delete=True,
    )


# Properties to return via API, id is always required
class ProfileScriptPublic(ProfileScriptBase):
    id: uuid.UUID
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
    description: Optional[str] = None
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
    description: Optional[str] = None


class RulesetCreate(RulesetBase):
    pass


class RulesetUpdate(RulesetBase):
    pass


# Database model, database table inferred from class name
class Ruleset(RulesetBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ruleset_scripts: List["RulesetScript"] = Relationship(
        back_populates="ruleset", cascade_delete=True
    )


# Properties to return via API, id is always required
class RulesetPreviewPublic(SQLModel):
    data: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RulesetPublic(RulesetBase):
    id: uuid.UUID
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
    description: Optional[str] = None
    ruleset_id: uuid.UUID = Field(nullable=False)


class RulesetScriptCreate(RulesetScriptBase):
    pass


class RulesetScriptUpdate(RulesetScriptBase):
    pass


# Database model, database table inferred from class name
class RulesetScript(RulesetScriptBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ruleset_id: uuid.UUID = Field(
        foreign_key="ruleset.id", nullable=False, ondelete="CASCADE"
    )
    ruleset: Ruleset | None = Relationship(back_populates="ruleset_scripts")

    ruleset_script_sets: List["RulesetScriptSet"] = Relationship(
        back_populates="ruleset_script", cascade_delete=True
    )


# Properties to return via API, id is always required
class RulesetScriptPublic(RulesetScriptBase):
    id: uuid.UUID
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
    description: Optional[str] = None
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


# --- End of TACACS+ Configuration Tables ---


# -- Tacacs Config File Table ---
class TacacsConfigBase(SQLModel):
    filename: str = Field(index=True, unique=True, max_length=255)
    description: Optional[str] = None


class TacacsConfigCreate(TacacsConfigBase):
    filename: str = Field(index=True, unique=True, max_length=30)


class TacacsConfigUpdate(TacacsConfigBase):
    description: str | None = Field(default=None)


# Database model, database table inferred from class name
class TacacsConfig(TacacsConfigBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    active: bool = Field(default=False)


# Properties to return via API, id is always required
class TacacsConfigPreviewPublic(SQLModel):
    created_at: datetime
    data: str | None = None
    updated_at: datetime


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
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TacacsLogCreate(TacacsLogBase):
    pass


class TacacsLogUpdate(TacacsLogBase):
    pass


# Database model, database table inferred from class name
class TacacsLog(TacacsLogBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )


# Properties to return via API, id is always required
class TacacsLogPublic(TacacsLogBase):
    id: uuid.UUID
    updated_at: datetime
    data: str | None = None


class TacacsLogsPublic(SQLModel):
    data: list[TacacsLogPublic]
    count: int


# -- Tacacs Custom Section Table ---
class ConfigurationOptionBase(SQLModel):
    name: str = Field(index=True, unique=True, max_length=255)
    config_option: str
    description: Optional[str] = None


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
    username: str = Field(index=True, max_length=255)
    nas_ip: str = Field(index=True, max_length=1024)
    user_source_ip: str = Field(index=True, max_length=1024)
    success_count: int = Field(default=0)
    fail_count: int = Field(default=0)
    log_date: datetime = Field(default_factory=datetime.utcnow)


class AuthenticationStatisticsCreate(AuthenticationStatisticsBase):
    pass


class AuthenticationStatisticsUpdate(AuthenticationStatisticsBase):
    pass


# Database model, database table inferred from class name
class AuthenticationStatistics(
    AuthenticationStatisticsBase, TimestampModel, table=True
):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


# Properties to return via API, id is always required
class AuthenticationStatisticPublic(AuthenticationStatisticsBase):
    id: uuid.UUID
    updated_at: datetime
    data: str | None = None


class AuthenticationStatisticsPublic(SQLModel):
    data: list[AuthenticationStatisticPublic]
    count: int


# -- Authrorization Statistics Table ---
class AuthorizationStatisticsBase(SQLModel):
    username: str = Field(index=True, max_length=255)
    nas_ip: str = Field(index=True, max_length=1024)
    user_source_ip: str = Field(index=True, max_length=1024)
    permit_count: int = Field(default=0)
    deny_count: int = Field(default=0)
    log_date: datetime = Field(default_factory=datetime.utcnow)


class AuthorizationStatisticsCreate(AuthorizationStatisticsBase):
    pass


class AuthorizationStatisticsUpdate(AuthorizationStatisticsBase):
    pass


# Database model, database table inferred from class name
class AuthorizationStatistics(AuthorizationStatisticsBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


# Properties to return via API, id is always required
class AuthorizationStatisticPublic(AuthorizationStatisticsBase):
    id: uuid.UUID
    updated_at: datetime
    data: str | None = None


class AuthorizationStatisticsPublic(SQLModel):
    data: list[AuthorizationStatisticPublic]
    count: int


# --- Accounting Statistics Table ---
class AccountingStatisticsBase(SQLModel):
    username: str = Field(index=True, max_length=255)
    nas_ip: str = Field(index=True, max_length=1024)
    user_source_ip: str = Field(index=True, max_length=1024)
    start_count: int = Field(default=0)
    stop_count: int = Field(default=0)
    log_date: datetime = Field(default_factory=datetime.utcnow)


class AccountingStatisticsCreate(AccountingStatisticsBase):
    pass


class AccountingStatisticsUpdate(AccountingStatisticsBase):
    pass


# Database model, database table inferred from class name
class AccountingStatistics(AccountingStatisticsBase, TimestampModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


# Properties to return via API, id is always required
class AccountingStatisticPublic(AccountingStatisticsBase):
    id: uuid.UUID
    updated_at: datetime
    data: str | None = None


class AccountingStatisticsPublic(SQLModel):
    data: list[AccountingStatisticPublic]
    count: int


# --- End of Accounting Statistics Table ---


class AaaStatisticsSummaryPublic(SQLModel):

    authentication: list[AuthenticationStatisticPublic] = []
    authorization: list[AuthorizationStatisticPublic] = []
    accounting: list[AccountingStatisticPublic] = []
    authentication_failed_count_by_user: list[dict] = []
    authentication_success_count_by_user: list[dict] = []
    authorization_deny_count_by_user: list[dict] = []
    authentication_success_count_by_user_source_ip: list[dict] = []
    last_7_days_authentication_success: list[dict] = []
    last_7_days_authentication_fail: list[dict] = []
    last_7_days_authorization_pass: list[dict] = []
    last_7_days_authorization_deny: list[dict] = []
    last_7_days_accounting: list[dict] = []
