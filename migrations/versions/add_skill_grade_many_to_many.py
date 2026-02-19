"""skill_grade N:N e remoção de grade_id em skills

Revision ID: skill_grade_n_n
Revises: add_competition_templates
Create Date: 2026-02-17

- Cria tabela skill_grade (skill_id, grade_id) para múltiplas grades por skill.
- Migra dados: skills.grade_id -> skill_grade.
- Remove coluna grade_id da tabela skills.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "skill_grade_n_n"
down_revision = "add_competition_templates"
branch_labels = None
depends_on = None


def upgrade():
    # 1) Criar tabela skill_grade
    op.create_table(
        "skill_grade",
        sa.Column("skill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("grade_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["grade_id"], ["grade.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("skill_id", "grade_id"),
    )

    # 2) Migrar: copiar (id, grade_id) de skills para skill_grade onde grade_id não é nulo
    conn = op.get_bind()
    conn.execute(sa.text("""
        INSERT INTO skill_grade (skill_id, grade_id)
        SELECT id, grade_id FROM skills WHERE grade_id IS NOT NULL
    """))

    # 3) Remover coluna grade_id de skills (a FK é removida junto no PostgreSQL)
    with op.batch_alter_table("skills", schema=None) as batch_op:
        batch_op.drop_constraint("skills_grade_id_fkey", type_="foreignkey")
        batch_op.drop_column("grade_id")


def downgrade():
    # 1) Recolocar coluna grade_id em skills
    with op.batch_alter_table("skills", schema=None) as batch_op:
        batch_op.add_column(sa.Column("grade_id", postgresql.UUID(as_uuid=True), nullable=True))

    # 2) Restaurar um grade_id por skill (o primeiro de skill_grade, se houver)
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE skills s
        SET grade_id = (
            SELECT sg.grade_id FROM skill_grade sg WHERE sg.skill_id = s.id LIMIT 1
        )
    """))

    # 3) Recriar FK
    with op.batch_alter_table("skills", schema=None) as batch_op:
        batch_op.create_foreign_key("skills_grade_id_fkey", "grade", ["grade_id"], ["id"])

    # 4) Dropar tabela skill_grade
    op.drop_table("skill_grade")
