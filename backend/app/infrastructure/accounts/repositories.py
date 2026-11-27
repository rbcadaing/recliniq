"""SQLAlchemy implementations of the account repository ports."""

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import exists, select, update
from sqlalchemy.exc import IntegrityError

from app.domain.accounts.entities import (
    AccountProfile,
    DoctorProfile,
    DoctorSummary,
    RefreshToken,
    Specialization,
    User,
    VerificationToken,
)
from app.domain.accounts.values import LicenseStatus, Role
from app.domain.errors import FieldConflictError
from app.infrastructure.accounts.models import (
    DoctorProfileModel,
    EmailVerificationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
    SpecializationModel,
    UserModel,
)
from app.infrastructure.db.repository import SoftDeleteRepository

# Partial unique index name -> request field it protects.
_FIELD_BY_CONSTRAINT = {
    "uq_users_email_active": "email",
    "uq_users_mobile_active": "mobile",
    "uq_doctor_profiles_prc_license_no_active": "prc_license_no",
}


def _to_user(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        mobile=model.mobile,
        password_hash=model.password_hash,
        first_name=model.first_name,
        middle_name=model.middle_name,
        last_name=model.last_name,
        role=Role(model.role),
        email_verified_at=model.email_verified_at,
        privacy_consent_at=model.privacy_consent_at,
        privacy_notice_version=model.privacy_notice_version,
    )


def _conflicting_field(exc: IntegrityError) -> str | None:
    message = str(exc.orig)
    return next((f for c, f in _FIELD_BY_CONSTRAINT.items() if c in message), None)


class SqlUserRepository(SoftDeleteRepository[UserModel]):
    model = UserModel

    async def find(self, user_id: uuid.UUID) -> User | None:
        found = await self.get(user_id)
        return _to_user(found) if found else None

    async def find_by_email(self, email: str) -> User | None:
        found = await self.session.scalar(select(UserModel).where(UserModel.email == email))
        return _to_user(found) if found else None

    async def mobile_exists(self, mobile: str) -> bool:
        return bool(await self.session.scalar(select(exists().where(UserModel.mobile == mobile))))

    async def prc_license_exists(self, prc_license_no: str) -> bool:
        statement = select(exists().where(DoctorProfileModel.prc_license_no == prc_license_no))
        return bool(await self.session.scalar(statement))

    async def add_doctor(self, user: User, profile: DoctorProfile) -> None:
        try:
            # A savepoint keeps the session usable if a concurrent sign-up won the race.
            async with self.session.begin_nested():
                self.session.add(
                    UserModel(
                        id=user.id,
                        email=user.email,
                        mobile=user.mobile,
                        password_hash=user.password_hash,
                        first_name=user.first_name,
                        middle_name=user.middle_name,
                        last_name=user.last_name,
                        role=user.role.value,
                        email_verified_at=user.email_verified_at,
                        privacy_consent_at=user.privacy_consent_at,
                        privacy_notice_version=user.privacy_notice_version,
                    )
                )
                await self.session.flush()
                self.session.add(
                    DoctorProfileModel(
                        user_id=profile.user_id,
                        specialization_id=profile.specialization_id,
                        prc_license_no=profile.prc_license_no,
                        license_status=profile.license_status.value,
                    )
                )
                await self.session.flush()
        except IntegrityError as exc:
            field = _conflicting_field(exc)
            if field is None:
                raise
            raise FieldConflictError(field) from None

    async def mark_email_verified(self, user_id: uuid.UUID, at: datetime) -> None:
        await self.session.execute(
            update(UserModel).where(UserModel.id == user_id).values(email_verified_at=at)
        )

    async def update_password(self, user_id: uuid.UUID, password_hash: str) -> None:
        await self.session.execute(
            update(UserModel).where(UserModel.id == user_id).values(password_hash=password_hash)
        )

    async def find_profile(self, user_id: uuid.UUID) -> AccountProfile | None:
        statement = (
            select(UserModel, DoctorProfileModel, SpecializationModel)
            .outerjoin(DoctorProfileModel, DoctorProfileModel.user_id == UserModel.id)
            .outerjoin(
                SpecializationModel, SpecializationModel.id == DoctorProfileModel.specialization_id
            )
            .where(UserModel.id == user_id)
        )
        row = (await self.session.execute(statement)).first()
        if row is None:
            return None
        user, profile, specialization = row
        doctor = None
        if profile is not None and specialization is not None:
            doctor = DoctorSummary(
                specialization=Specialization(
                    id=specialization.id, code=specialization.code, name=specialization.name
                ),
                license_status=LicenseStatus(profile.license_status),
            )
        return AccountProfile(
            id=user.id,
            first_name=user.first_name,
            middle_name=user.middle_name,
            last_name=user.last_name,
            email=user.email,
            role=Role(user.role),
            email_verified=user.email_verified_at is not None,
            doctor=doctor,
        )


class SqlSpecializationRepository(SoftDeleteRepository[SpecializationModel]):
    model = SpecializationModel

    async def list_all(self) -> list[Specialization]:
        rows = await self.session.scalars(
            select(SpecializationModel).order_by(SpecializationModel.name)
        )
        return [Specialization(id=row.id, code=row.code, name=row.name) for row in rows]

    async def exists(self, specialization_id: uuid.UUID) -> bool:
        return await self.get(specialization_id) is not None


class _SingleUseTokenRepository(SoftDeleteRepository[Any]):
    """Shared by email verification and password reset tokens (same table shape)."""

    model: ClassVar[type[EmailVerificationTokenModel] | type[PasswordResetTokenModel]]

    async def add(self, token: VerificationToken) -> None:
        self.session.add(
            self.model(
                id=token.id,
                user_id=token.user_id,
                token_hash=token.token_hash,
                expires_at=token.expires_at,
                used_at=token.used_at,
            )
        )
        await self.session.flush()

    async def find_by_hash(self, token_hash: str) -> VerificationToken | None:
        found: (
            EmailVerificationTokenModel | PasswordResetTokenModel | None
        ) = await self.session.scalar(select(self.model).where(self.model.token_hash == token_hash))
        if found is None:
            return None
        return VerificationToken(
            id=found.id,
            user_id=found.user_id,
            token_hash=found.token_hash,
            expires_at=found.expires_at,
            used_at=found.used_at,
        )

    async def mark_used(self, token_id: uuid.UUID, at: datetime) -> None:
        await self.session.execute(
            update(self.model).where(self.model.id == token_id).values(used_at=at)
        )

    async def invalidate_unused(self, user_id: uuid.UUID) -> None:
        # Superseded tokens are soft-deleted (system actor), so lookups no longer see them.
        unused = await self.session.scalars(
            select(self.model).where(self.model.user_id == user_id, self.model.used_at.is_(None))
        )
        for token in unused.all():
            await self.soft_delete(token, actor_id=None)


class SqlVerificationTokenRepository(_SingleUseTokenRepository):
    model = EmailVerificationTokenModel


class SqlPasswordResetTokenRepository(_SingleUseTokenRepository):
    model = PasswordResetTokenModel


def _to_refresh(model: RefreshTokenModel) -> RefreshToken:
    return RefreshToken(
        id=model.id,
        user_id=model.user_id,
        family_id=model.family_id,
        token_hash=model.token_hash,
        expires_at=model.expires_at,
        used_at=model.used_at,
        revoked_at=model.revoked_at,
    )


class SqlRefreshTokenRepository(SoftDeleteRepository[RefreshTokenModel]):
    model = RefreshTokenModel

    async def add(self, token: RefreshToken) -> None:
        self.session.add(
            RefreshTokenModel(
                id=token.id,
                user_id=token.user_id,
                family_id=token.family_id,
                token_hash=token.token_hash,
                expires_at=token.expires_at,
            )
        )
        await self.session.flush()

    async def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        found = await self.session.scalar(
            select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        )
        return _to_refresh(found) if found else None

    async def mark_used(self, token_id: uuid.UUID, at: datetime) -> None:
        await self.session.execute(
            update(RefreshTokenModel).where(RefreshTokenModel.id == token_id).values(used_at=at)
        )

    async def revoke_family(self, family_id: uuid.UUID, at: datetime) -> None:
        await self.session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.family_id == family_id, RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=at)
        )

    async def revoke_all_for_user(self, user_id: uuid.UUID, at: datetime) -> None:
        await self.session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.user_id == user_id, RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=at)
        )
