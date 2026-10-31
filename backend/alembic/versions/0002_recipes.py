"""recipes, search cache and images

Revision ID: 0002_recipes
Revises: 0001_initial
Create Date: 2026-10-30

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_recipes"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recipes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("cache_key", sa.String(length=160), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=1000), nullable=False),
        sa.Column("canonical_url", sa.String(length=1200), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("image_source_url", sa.Text(), nullable=True),
        sa.Column("image_blurhash", sa.String(length=160), nullable=True),
        sa.Column("author", sa.String(length=240), nullable=False),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("rating_count", sa.Integer(), nullable=False),
        sa.Column("prep_min", sa.Integer(), nullable=True),
        sa.Column("cook_min", sa.Integer(), nullable=True),
        sa.Column("total_min", sa.Integer(), nullable=True),
        sa.Column("difficulty", sa.Integer(), nullable=True),
        sa.Column("base_servings", sa.Integer(), nullable=True),
        sa.Column("ingredients", sa.JSON(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("nutrition", sa.JSON(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("image_count", sa.Integer(), nullable=False),
        sa.Column("is_favorite", sa.Boolean(), nullable=False),
        sa.Column("is_saved", sa.Boolean(), nullable=False),
        sa.Column("has_detail", sa.Boolean(), nullable=False),
        sa.Column("access_count", sa.Integer(), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("stale_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recipes_cache_key", "recipes", ["cache_key"], unique=True)
    op.create_index("ix_recipes_source", "recipes", ["source"], unique=False)
    op.create_index("ix_recipes_canonical_url", "recipes", ["canonical_url"], unique=False)
    op.create_index("ix_recipes_is_favorite", "recipes", ["is_favorite"], unique=False)
    op.create_index("ix_recipes_is_saved", "recipes", ["is_saved"], unique=False)

    op.create_table(
        "search_cache",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index("ix_search_cache_expires_at", "search_cache", ["expires_at"], unique=False)

    op.create_table(
        "images",
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("recipe_id", sa.String(length=36), nullable=True),
        sa.Column("source_url_hash", sa.String(length=64), nullable=False),
        sa.Column("variant", sa.String(length=24), nullable=False),
        sa.Column("rel_path", sa.Text(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(length=40), nullable=False),
        sa.Column("etag", sa.String(length=80), nullable=False),
        sa.Column("blurhash", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index("ix_images_recipe_id", "images", ["recipe_id"], unique=False)
    op.create_index("ix_images_source_url_hash", "images", ["source_url_hash"], unique=False)


def downgrade() -> None:
    op.drop_table("images")
    op.drop_table("search_cache")
    op.drop_table("recipes")
