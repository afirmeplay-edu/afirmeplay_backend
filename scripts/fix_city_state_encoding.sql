-- Script para verificar e corrigir encoding de estados na tabela city
-- Execute primeiro a verificação, depois os updates se necessário

-- ========================================
-- 1. VERIFICAÇÃO - Ver quais estados existem
-- ========================================
SELECT DISTINCT state, COUNT(*) as total_cidades
FROM city
GROUP BY state
ORDER BY state;

-- ========================================
-- 2. VERIFICAÇÃO - Ver cidades com possíveis problemas de encoding
-- ========================================
SELECT id, name, state, slug
FROM city
WHERE state ~ '[^a-zA-Záàâãéèêíïóôõöúçñ\s-]'  -- Caracteres estranhos
ORDER BY state, name;

-- ========================================
-- 3. CORREÇÃO - Normalizar estados conhecidos
-- ========================================

-- Rondônia (caso venha errado)
UPDATE city 
SET state = 'Rondônia'
WHERE state LIKE 'Rond%'
  AND state != 'Rondônia';

-- Acre
UPDATE city 
SET state = 'Acre'
WHERE state ILIKE 'acre'
  AND state != 'Acre';

-- Amazonas
UPDATE city 
SET state = 'Amazonas'
WHERE state ILIKE 'amazonas'
  AND state != 'Amazonas';

-- Roraima
UPDATE city 
SET state = 'Roraima'
WHERE state ILIKE 'roraima'
  AND state != 'Roraima';

-- Pará
UPDATE city 
SET state = 'Pará'
WHERE state LIKE 'Par%'
  AND state != 'Pará';

-- Amapá
UPDATE city 
SET state = 'Amapá'
WHERE state LIKE 'Amap%'
  AND state != 'Amapá';

-- Tocantins
UPDATE city 
SET state = 'Tocantins'
WHERE state ILIKE 'tocantins'
  AND state != 'Tocantins';

-- Maranhão
UPDATE city 
SET state = 'Maranhão'
WHERE state LIKE 'Maranh%'
  AND state != 'Maranhão';

-- Piauí
UPDATE city 
SET state = 'Piauí'
WHERE state LIKE 'Piau%'
  AND state != 'Piauí';

-- Ceará
UPDATE city 
SET state = 'Ceará'
WHERE state LIKE 'Cear%'
  AND state != 'Ceará';

-- Rio Grande do Norte
UPDATE city 
SET state = 'Rio Grande do Norte'
WHERE state ILIKE '%rio grande%norte%'
  AND state != 'Rio Grande do Norte';

-- Paraíba
UPDATE city 
SET state = 'Paraíba'
WHERE state LIKE 'Para%ba%'
  AND state != 'Paraíba';

-- Pernambuco
UPDATE city 
SET state = 'Pernambuco'
WHERE state ILIKE 'pernambuco'
  AND state != 'Pernambuco';

-- Alagoas
UPDATE city 
SET state = 'Alagoas'
WHERE state ILIKE 'alagoas'
  AND state != 'Alagoas';

-- Sergipe
UPDATE city 
SET state = 'Sergipe'
WHERE state ILIKE 'sergipe'
  AND state != 'Sergipe';

-- Bahia
UPDATE city 
SET state = 'Bahia'
WHERE state ILIKE 'bahia'
  AND state != 'Bahia';

-- Minas Gerais
UPDATE city 
SET state = 'Minas Gerais'
WHERE state ILIKE 'minas%gerais'
  AND state != 'Minas Gerais';

-- Espírito Santo
UPDATE city 
SET state = 'Espírito Santo'
WHERE state LIKE 'Esp%Santo%'
  AND state != 'Espírito Santo';

-- Rio de Janeiro
UPDATE city 
SET state = 'Rio de Janeiro'
WHERE state ILIKE '%rio%janeiro%'
  AND state != 'Rio de Janeiro'
  AND state NOT LIKE '%norte%';

-- São Paulo
UPDATE city 
SET state = 'São Paulo'
WHERE state LIKE 'S%o Paulo'
  AND state != 'São Paulo';

-- Paraná
UPDATE city 
SET state = 'Paraná'
WHERE state LIKE 'Paran%'
  AND state != 'Paraná'
  AND state NOT LIKE '%ba%';

-- Santa Catarina
UPDATE city 
SET state = 'Santa Catarina'
WHERE state ILIKE 'santa%catarina'
  AND state != 'Santa Catarina';

-- Rio Grande do Sul
UPDATE city 
SET state = 'Rio Grande do Sul'
WHERE state ILIKE '%rio grande%sul%'
  AND state != 'Rio Grande do Sul';

-- Mato Grosso do Sul
UPDATE city 
SET state = 'Mato Grosso do Sul'
WHERE state ILIKE 'mato%grosso%sul%'
  AND state != 'Mato Grosso do Sul';

-- Mato Grosso
UPDATE city 
SET state = 'Mato Grosso'
WHERE state ILIKE 'mato%grosso'
  AND state != 'Mato Grosso'
  AND state NOT LIKE '%sul%';

-- Goiás
UPDATE city 
SET state = 'Goiás'
WHERE state LIKE 'Goi%s'
  AND state != 'Goiás';

-- Distrito Federal
UPDATE city 
SET state = 'Distrito Federal'
WHERE state ILIKE '%distrito%federal%'
  AND state != 'Distrito Federal';

-- ========================================
-- 4. VERIFICAÇÃO FINAL - Conferir resultado
-- ========================================
SELECT DISTINCT state, COUNT(*) as total_cidades
FROM city
GROUP BY state
ORDER BY state;
