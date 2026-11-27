"""SQLAlchemy implementations of the account repository ports."""

import uuid
from datetime import datetime

from sqlalchemy import exists, select, update
from sqlalchemy.exc import IntegrityError

from app.domain.accounts.entities import DoctorProfile, Specialization, User, VerificationToken
from app.domain.accounts.values import Role
from app.domain.errors import FieldConflictError
from app.infrastructure.accounts.models import (
    DoctorProfileModel,
    EmailVerificationTokenModel,
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


class SqlSpecializationRepository(SoftDeleteRepository[SpecializationModel]):
    model = SpecializationModel

    async def list_all(self) -> list[Specialization]:
        rows = await self.session.scalars(
            select(SpecializationModel).order_by(SpecializationModel.name)
        )
        return [Specialization(id=row.id, code=row.code, name=row.name) for row in rows]

    async def exists(self, specialization_id: uuid.UUID) -> bool:
        return await self.get(specialization_id) is not None


class SqlTokenRepository(SoftDeleteRepository[EmailVerificationTokenModel]):
    model = EmailVerificationTokenModel

    async def add(self, token: VerificationToken) -> None:
        self.session.add(
            EmailVerificationTokenModel(
                id=token.id,
                user_id=token.user_id,
                token_hash=token.token_hash,
                expires_at=token.expires_at,
                used_at=token.used_at,
            )
        )
        await self.session.flush()

    async def find_by_hash(self, token_hash: str) -> VerificationToken | None:
        found = await self.session.scalar(
            select(EmailVerificationTokenModel).where(
                EmailVerificationTokenModel.token_hash == token_hash
            )
        )
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
            update(EmailVerificationTokenModel)
            .where(EmailVerificationTokenModel.id == token_id)
            .values(used_at=at)
        )

    async def invalidate_unused(self, user_id: uuid.UUID) -> None:
        # Superseded tokens are soft-deleted (system actor), so lookups no longer see them.
        unused = await self.session.scalars(
            select(EmailVerificationTokenModel).where(
                EmailVerificationTokenModel.user_id == user_id,
                EmailVerificationTokenModel.used_at.is_(None),
            )
        )
        for token in unused.all():
            await self.soft_delete(token, actor_id=None)
