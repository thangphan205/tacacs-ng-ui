"""add raw_script to profile

Revision ID: b2d7e4f9a613
Revises: f3a8c1d5e927
Create Date: 2026-11-06 00:00:00.000000

A profile can carry raw tac_plus-ng text for its `script { }` body (#359).
Nullable and additive: existing profiles read as structured.

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b2d7e4f9a613"
down_revision = "f3a8c1d5e927"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("profile", sa.Column("raw_script", sa.Text(), nullable=True))


def downgrade() -> None:
    in_use = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM profile WHERE raw_script IS NOT NULL"))
        .scalar_one()
    )
    if in_use:
        raise RuntimeError(
            f"{in_use} profile(s) use a raw script; downgrading would drop that "
            "text. Move it to the 'profile' Configuration Option first."
        )
    op.drop_column("profile", "raw_script")
