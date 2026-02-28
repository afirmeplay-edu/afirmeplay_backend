"""skill_grade N:N e remoção de grade_id em skills

Revision ID: skill_grade_n_n
Revises: add_competition_templates
Create Date: 2026-02-17

- Cria tabela skill_grade (skill_id, grade_id) para múltiplas grades por skill.
- Migra dados: skills.grade_id -> skill_grade.
- Remove coluna grade_id da tabela skills.

Idempotente: se skill_grade já existir ou grade_id já foi removido, pula o passo.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "skill_grade_n_n"
down_revision = "add_competition_templates"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name):
    r = connection.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :name"
        ),
        {"name": table_name},
    )
    return r.scalar() is not None


def _column_exists(connection, table_name, column_name):
    r = connection.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :tname AND column_name = :cname"
        ),
        {"tname": table_name, "cname": column_name},
    )
    return r.scalar() is not None


def upgrade():
    conn = op.get_bind()

    # 1) Criar tabela skill_grade se não existir
    if not _table_exists(conn, "skill_grade"):
        op.create_table(
            "skill_grade",
            sa.Column("skill_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("grade_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.ForeignKeyConstraint(["grade_id"], ["grade.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("skill_id", "grade_id"),
        )

    # 2) Migrar dados só se skills ainda tem grade_id (evita duplicar em reexecução)
    if _column_exists(conn, "skills", "grade_id"):
        conn.execute(sa.text("""
            INSERT INTO skill_grade (skill_id, grade_id)
            SELECT id, grade_id FROM skills WHERE grade_id IS NOT NULL
            ON CONFLICT (skill_id, grade_id) DO NOTHING
        """))

    # 3) Remover coluna grade_id de skills se ainda existir
    if _column_exists(conn, "skills", "grade_id"):
        # Obter nome real da FK (pode variar por ambiente)
        r = conn.execute(sa.text("""
            SELECT tc.constraint_name FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_schema = 'public' AND tc.table_name = 'skills'
            AND tc.constraint_type = 'FOREIGN KEY' AND kcu.column_name = 'grade_id'
        """))
        row = r.fetchone()
        fk_name = row[0] if row else "skills_grade_id_fkey"
        with op.batch_alter_table("skills", schema=None) as batch_op:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
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
