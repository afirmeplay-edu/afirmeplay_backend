-- Execute no pgAdmin/DBeaver (conectado ao mesmo banco do .env)
-- 1) Limpar referências nas questões
UPDATE question SET skill = NULL WHERE skill IS NOT NULL;

-- 2) Apagar todas as skills (rode depois do UPDATE)
DELETE FROM skills;

-- 3) Conferir
SELECT COUNT(*) AS total_skills FROM skills;
