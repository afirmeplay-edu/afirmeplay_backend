"""merge_all_heads

Revision ID: b813cdb16b4d
Revises: 626d61d3c562, add_form_type_physical, e99c76543d20, fix_form_coordinates_duplicates
Create Date: 2025-09-18 17:20:04.801944

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b813cdb16b4d'
down_revision = ('626d61d3c562', 'add_form_type_physical', 'e99c76543d20', 'fix_form_coordinates_duplicates')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
