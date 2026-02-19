-- Cria a tabela skill_grade (N:N entre skills e grade) quando não existir.
-- Execute no pgAdmin/DBeaver conectado ao banco do projeto.
-- Depois rode: python scripts/upload_educacao_infantil_skills.py

-- 1) Criar tabela skill_grade
CREATE TABLE IF NOT EXISTS skill_grade (
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    grade_id UUID NOT NULL REFERENCES grade(id) ON DELETE CASCADE,
    PRIMARY KEY (skill_id, grade_id)
);

-- 2) Migrar dados antigos: se a coluna grade_id ainda existir em skills, copiar para skill_grade
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'skills' AND column_name = 'grade_id'
    ) THEN
        INSERT INTO skill_grade (skill_id, grade_id)
        SELECT id, grade_id FROM skills WHERE grade_id IS NOT NULL
        ON CONFLICT (skill_id, grade_id) DO NOTHING;
    END IF;
END $$;
