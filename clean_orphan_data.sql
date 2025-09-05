-- =====================================================
-- SCRIPT PARA LIMPAR DADOS ÓRFÃOS NO BANCO
-- =====================================================

-- IMPORTANTE: Execute este script com cuidado!
-- Faça backup do banco antes de executar!

BEGIN;

-- 1. Limpar test_questions com question_id inexistente
DELETE FROM test_questions 
WHERE question_id NOT IN (SELECT id FROM question);

-- 2. Limpar test_questions com test_id inexistente
DELETE FROM test_questions 
WHERE test_id NOT IN (SELECT id FROM test);

-- 3. Limpar test_sessions com test_id inexistente
DELETE FROM test_sessions 
WHERE test_id NOT IN (SELECT id FROM test);

-- 4. Limpar test_sessions com student_id inexistente
DELETE FROM test_sessions 
WHERE student_id NOT IN (SELECT id FROM student);

-- 5. Limpar student_answers com question_id inexistente
DELETE FROM student_answers 
WHERE question_id NOT IN (SELECT id FROM question);

-- 6. Limpar student_answers com test_id inexistente
DELETE FROM student_answers 
WHERE test_id NOT IN (SELECT id FROM test);

-- 7. Limpar student_answers com student_id inexistente
DELETE FROM student_answers 
WHERE student_id NOT IN (SELECT id FROM student);

-- 8. Limpar class_test com test_id inexistente
DELETE FROM class_test 
WHERE test_id NOT IN (SELECT id FROM test);

-- 9. Limpar class_test com class_id inexistente
DELETE FROM class_test 
WHERE class_id NOT IN (SELECT id FROM class);

-- 10. Limpar class_subject com class_id inexistente
DELETE FROM class_subject 
WHERE class_id NOT IN (SELECT id FROM class);

-- 11. Limpar class_subject com subject_id inexistente
DELETE FROM class_subject 
WHERE subject_id NOT IN (SELECT id FROM subject);

-- 12. Limpar class_subject com teacher_id inexistente
DELETE FROM class_subject 
WHERE teacher_id NOT IN (SELECT id FROM teacher);

-- 13. Limpar student com user_id inexistente
DELETE FROM student 
WHERE user_id NOT IN (SELECT id FROM users);

-- 14. Limpar student com grade_id inexistente
DELETE FROM student 
WHERE grade_id NOT IN (SELECT id FROM grade);

-- 15. Limpar student com class_id inexistente
DELETE FROM student 
WHERE class_id NOT IN (SELECT id FROM class);

-- 16. Limpar student com school_id inexistente
DELETE FROM student 
WHERE school_id NOT IN (SELECT id FROM school);

-- 17. Limpar teacher com user_id inexistente
DELETE FROM teacher 
WHERE user_id NOT IN (SELECT id FROM users);

-- 18. Limpar school_teacher com school_id inexistente
DELETE FROM school_teacher 
WHERE school_id NOT IN (SELECT id FROM school);

-- 19. Limpar school_teacher com teacher_id inexistente
DELETE FROM school_teacher 
WHERE teacher_id NOT IN (SELECT id FROM teacher);

-- 20. Limpar teacher_class com teacher_id inexistente
DELETE FROM teacher_class 
WHERE teacher_id NOT IN (SELECT id FROM teacher);

-- 21. Limpar teacher_class com class_id inexistente
DELETE FROM teacher_class 
WHERE class_id NOT IN (SELECT id FROM class);

-- 22. Limpar evaluation_results com test_id inexistente
DELETE FROM evaluation_results 
WHERE test_id NOT IN (SELECT id FROM test);

-- 23. Limpar evaluation_results com student_id inexistente
DELETE FROM evaluation_results 
WHERE student_id NOT IN (SELECT id FROM student);

-- 24. Limpar evaluation_results com session_id inexistente
DELETE FROM evaluation_results 
WHERE session_id NOT IN (SELECT id FROM test_sessions);

-- 25. Limpar user_quick_links com user_id inexistente
DELETE FROM user_quick_links 
WHERE user_id NOT IN (SELECT id FROM users);

-- 26. Limpar games com userId inexistente (corrigindo nome da coluna)
DELETE FROM games 
WHERE "userId" NOT IN (SELECT id FROM users);

-- 27. Limpar manager com user_id inexistente
DELETE FROM manager 
WHERE user_id NOT IN (SELECT id FROM users);

-- 28. Limpar manager com school_id inexistente
DELETE FROM manager 
WHERE school_id IS NOT NULL AND school_id NOT IN (SELECT id FROM school);

-- 29. Limpar manager com city_id inexistente
DELETE FROM manager 
WHERE city_id IS NOT NULL AND city_id NOT IN (SELECT id FROM city);

-- 30. Limpar question com created_by inexistente
UPDATE question 
SET created_by = NULL 
WHERE created_by IS NOT NULL AND created_by NOT IN (SELECT id FROM users);

-- 31. Limpar question com last_modified_by inexistente
UPDATE question 
SET last_modified_by = NULL 
WHERE last_modified_by IS NOT NULL AND last_modified_by NOT IN (SELECT id FROM users);

-- 32. Limpar question com subject_id inexistente
UPDATE question 
SET subject_id = NULL 
WHERE subject_id IS NOT NULL AND subject_id NOT IN (SELECT id FROM subject);

-- 33. Limpar question com grade_level inexistente
UPDATE question 
SET grade_level = NULL 
WHERE grade_level IS NOT NULL AND grade_level NOT IN (SELECT id FROM grade);

-- 34. Limpar question com education_stage_id inexistente
UPDATE question 
SET education_stage_id = NULL 
WHERE education_stage_id IS NOT NULL AND education_stage_id NOT IN (SELECT id FROM education_stage);

-- 35. Limpar test com created_by inexistente
UPDATE test 
SET created_by = NULL 
WHERE created_by IS NOT NULL AND created_by NOT IN (SELECT id FROM users);

-- 36. Limpar test com subject inexistente
UPDATE test 
SET subject = NULL 
WHERE subject IS NOT NULL AND subject NOT IN (SELECT id FROM subject);

-- 37. Limpar test com grade_id inexistente
UPDATE test 
SET grade_id = NULL 
WHERE grade_id IS NOT NULL AND grade_id NOT IN (SELECT id FROM grade);

-- 38. Limpar grade com education_stage_id inexistente
UPDATE grade 
SET education_stage_id = NULL 
WHERE education_stage_id IS NOT NULL AND education_stage_id NOT IN (SELECT id FROM education_stage);

-- 39. Limpar skill com subject_id inexistente
UPDATE skills 
SET subject_id = NULL 
WHERE subject_id IS NOT NULL AND subject_id NOT IN (SELECT id FROM subject);

-- 40. Limpar skill com grade_id inexistente
UPDATE skills 
SET grade_id = NULL 
WHERE grade_id IS NOT NULL AND grade_id NOT IN (SELECT id FROM grade);

-- 41. Limpar class com school_id inexistente
UPDATE class 
SET school_id = NULL 
WHERE school_id IS NOT NULL AND school_id NOT IN (SELECT id FROM school);

-- 42. Limpar class com grade_id inexistente
UPDATE class 
SET grade_id = NULL 
WHERE grade_id IS NOT NULL AND grade_id NOT IN (SELECT id FROM grade);

-- 43. Limpar school com city_id inexistente
UPDATE school 
SET city_id = NULL 
WHERE city_id IS NOT NULL AND city_id NOT IN (SELECT id FROM city);

-- 44. Limpar users com city_id inexistente
UPDATE users 
SET city_id = NULL 
WHERE city_id IS NOT NULL AND city_id NOT IN (SELECT id FROM city);

-- 45. Limpar student_answers com corrected_by inexistente
UPDATE student_answers 
SET corrected_by = NULL 
WHERE corrected_by IS NOT NULL AND corrected_by NOT IN (SELECT id FROM users);

-- 46. Limpar test_sessions com corrected_by inexistente
UPDATE test_sessions 
SET corrected_by = NULL 
WHERE corrected_by IS NOT NULL AND corrected_by NOT IN (SELECT id FROM users);

COMMIT;

-- Verificar se ainda há dados órfãos
SELECT 'Verificação pós-limpeza' as status;
