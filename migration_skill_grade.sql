-- Remover campo grade_id da tabela skills
ALTER TABLE public.skills DROP COLUMN IF EXISTS grade_id;

-- Criar tabela de associação skill_grade
CREATE TABLE public.skill_grade (
    skill_id UUID NOT NULL,
    grade_id UUID NOT NULL,
    PRIMARY KEY (skill_id, grade_id),
    FOREIGN KEY (skill_id) REFERENCES public.skills(id) ON DELETE CASCADE,
    FOREIGN KEY (grade_id) REFERENCES public.grade(id) ON DELETE CASCADE
);