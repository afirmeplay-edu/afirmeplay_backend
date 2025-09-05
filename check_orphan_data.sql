-- =====================================================
-- SCRIPT PARA IDENTIFICAR DADOS ÓRFÃOS NO BANCO
-- =====================================================

-- 1. Verificar test_questions com question_id inexistente
SELECT 'test_questions com question_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM test_questions tq 
LEFT JOIN question q ON tq.question_id = q.id 
WHERE q.id IS NULL;

-- 2. Verificar test_questions com test_id inexistente
SELECT 'test_questions com test_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM test_questions tq 
LEFT JOIN test t ON tq.test_id = t.id 
WHERE t.id IS NULL;

-- 3. Verificar test_sessions com test_id inexistente
SELECT 'test_sessions com test_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM test_sessions ts 
LEFT JOIN test t ON ts.test_id = t.id 
WHERE t.id IS NULL;

-- 4. Verificar test_sessions com student_id inexistente
SELECT 'test_sessions com student_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM test_sessions ts 
LEFT JOIN student s ON ts.student_id = s.id 
WHERE s.id IS NULL;

-- 5. Verificar student_answers com question_id inexistente
SELECT 'student_answers com question_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM student_answers sa 
LEFT JOIN question q ON sa.question_id = q.id 
WHERE q.id IS NULL;

-- 6. Verificar student_answers com test_id inexistente
SELECT 'student_answers com test_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM student_answers sa 
LEFT JOIN test t ON sa.test_id = t.id 
WHERE t.id IS NULL;

-- 7. Verificar student_answers com student_id inexistente
SELECT 'student_answers com student_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM student_answers sa 
LEFT JOIN student s ON sa.student_id = s.id 
WHERE s.id IS NULL;

-- 8. Verificar class_test com test_id inexistente
SELECT 'class_test com test_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM class_test ct 
LEFT JOIN test t ON ct.test_id = t.id 
WHERE t.id IS NULL;

-- 9. Verificar class_test com class_id inexistente
SELECT 'class_test com class_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM class_test ct 
LEFT JOIN class c ON ct.class_id = c.id 
WHERE c.id IS NULL;

-- 10. Verificar class_subject com class_id inexistente
SELECT 'class_subject com class_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM class_subject cs 
LEFT JOIN class c ON cs.class_id = c.id 
WHERE c.id IS NULL;

-- 11. Verificar class_subject com subject_id inexistente
SELECT 'class_subject com subject_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM class_subject cs 
LEFT JOIN subject s ON cs.subject_id = s.id 
WHERE s.id IS NULL;

-- 12. Verificar class_subject com teacher_id inexistente
SELECT 'class_subject com teacher_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM class_subject cs 
LEFT JOIN teacher t ON cs.teacher_id = t.id 
WHERE t.id IS NULL;

-- 13. Verificar student com user_id inexistente
SELECT 'student com user_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM student s 
LEFT JOIN users u ON s.user_id = u.id 
WHERE u.id IS NULL;

-- 14. Verificar student com grade_id inexistente
SELECT 'student com grade_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM student s 
LEFT JOIN grade g ON s.grade_id = g.id 
WHERE g.id IS NULL;

-- 15. Verificar student com class_id inexistente
SELECT 'student com class_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM student s 
LEFT JOIN class c ON s.class_id = c.id 
WHERE c.id IS NULL;

-- 16. Verificar student com school_id inexistente
SELECT 'student com school_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM student s 
LEFT JOIN school sc ON s.school_id = sc.id 
WHERE sc.id IS NULL;

-- 17. Verificar teacher com user_id inexistente
SELECT 'teacher com user_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM teacher t 
LEFT JOIN users u ON t.user_id = u.id 
WHERE u.id IS NULL;

-- 18. Verificar school_teacher com school_id inexistente
SELECT 'school_teacher com school_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM school_teacher st 
LEFT JOIN school s ON st.school_id = s.id 
WHERE s.id IS NULL;

-- 19. Verificar school_teacher com teacher_id inexistente
SELECT 'school_teacher com teacher_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM school_teacher st 
LEFT JOIN teacher t ON st.teacher_id = t.id 
WHERE t.id IS NULL;

-- 20. Verificar teacher_class com teacher_id inexistente
SELECT 'teacher_class com teacher_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM teacher_class tc 
LEFT JOIN teacher t ON tc.teacher_id = t.id 
WHERE t.id IS NULL;

-- 21. Verificar teacher_class com class_id inexistente
SELECT 'teacher_class com class_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM teacher_class tc 
LEFT JOIN class c ON tc.class_id = c.id 
WHERE c.id IS NULL;

-- 22. Verificar evaluation_results com test_id inexistente
SELECT 'evaluation_results com test_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM evaluation_results er 
LEFT JOIN test t ON er.test_id = t.id 
WHERE t.id IS NULL;

-- 23. Verificar evaluation_results com student_id inexistente
SELECT 'evaluation_results com student_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM evaluation_results er 
LEFT JOIN student s ON er.student_id = s.id 
WHERE s.id IS NULL;

-- 24. Verificar evaluation_results com session_id inexistente
SELECT 'evaluation_results com session_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM evaluation_results er 
LEFT JOIN test_sessions ts ON er.session_id = ts.id 
WHERE ts.id IS NULL;

-- 25. Verificar user_quick_links com user_id inexistente
SELECT 'user_quick_links com user_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM user_quick_links uql 
LEFT JOIN users u ON uql.user_id = u.id 
WHERE u.id IS NULL;

-- 26. Verificar games com userId inexistente
SELECT 'games com userId inexistente' as problema, 
       COUNT(*) as quantidade
FROM games g 
LEFT JOIN users u ON g.userId = u.id 
WHERE u.id IS NULL;

-- 27. Verificar manager com user_id inexistente
SELECT 'manager com user_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM manager m 
LEFT JOIN users u ON m.user_id = u.id 
WHERE u.id IS NULL;

-- 28. Verificar manager com school_id inexistente
SELECT 'manager com school_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM manager m 
LEFT JOIN school s ON m.school_id = s.id 
WHERE s.id IS NULL AND m.school_id IS NOT NULL;

-- 29. Verificar manager com city_id inexistente
SELECT 'manager com city_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM manager m 
LEFT JOIN city c ON m.city_id = c.id 
WHERE c.id IS NULL AND m.city_id IS NOT NULL;

-- 30. Verificar question com created_by inexistente
SELECT 'question com created_by inexistente' as problema, 
       COUNT(*) as quantidade
FROM question q 
LEFT JOIN users u ON q.created_by = u.id 
WHERE u.id IS NULL AND q.created_by IS NOT NULL;

-- 31. Verificar question com last_modified_by inexistente
SELECT 'question com last_modified_by inexistente' as problema, 
       COUNT(*) as quantidade
FROM question q 
LEFT JOIN users u ON q.last_modified_by = u.id 
WHERE u.id IS NULL AND q.last_modified_by IS NOT NULL;

-- 32. Verificar question com subject_id inexistente
SELECT 'question com subject_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM question q 
LEFT JOIN subject s ON q.subject_id = s.id 
WHERE s.id IS NULL AND q.subject_id IS NOT NULL;

-- 33. Verificar question com grade_level inexistente
SELECT 'question com grade_level inexistente' as problema, 
       COUNT(*) as quantidade
FROM question q 
LEFT JOIN grade g ON q.grade_level = g.id 
WHERE g.id IS NULL AND q.grade_level IS NOT NULL;

-- 34. Verificar question com education_stage_id inexistente
SELECT 'question com education_stage_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM question q 
LEFT JOIN education_stage es ON q.education_stage_id = es.id 
WHERE es.id IS NULL AND q.education_stage_id IS NOT NULL;

-- 35. Verificar test com created_by inexistente
SELECT 'test com created_by inexistente' as problema, 
       COUNT(*) as quantidade
FROM test t 
LEFT JOIN users u ON t.created_by = u.id 
WHERE u.id IS NULL AND t.created_by IS NOT NULL;

-- 36. Verificar test com subject inexistente
SELECT 'test com subject inexistente' as problema, 
       COUNT(*) as quantidade
FROM test t 
LEFT JOIN subject s ON t.subject = s.id 
WHERE s.id IS NULL AND t.subject IS NOT NULL;

-- 37. Verificar test com grade_id inexistente
SELECT 'test com grade_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM test t 
LEFT JOIN grade g ON t.grade_id = g.id 
WHERE g.id IS NULL AND t.grade_id IS NOT NULL;

-- 38. Verificar grade com education_stage_id inexistente
SELECT 'grade com education_stage_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM grade g 
LEFT JOIN education_stage es ON g.education_stage_id = es.id 
WHERE es.id IS NULL AND g.education_stage_id IS NOT NULL;

-- 39. Verificar skill com subject_id inexistente
SELECT 'skill com subject_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM skills sk 
LEFT JOIN subject s ON sk.subject_id = s.id 
WHERE s.id IS NULL AND sk.subject_id IS NOT NULL;

-- 40. Verificar skill com grade_id inexistente
SELECT 'skill com grade_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM skills sk 
LEFT JOIN grade g ON sk.grade_id = g.id 
WHERE g.id IS NULL AND sk.grade_id IS NOT NULL;

-- 41. Verificar class com school_id inexistente
SELECT 'class com school_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM class c 
LEFT JOIN school s ON c.school_id = s.id 
WHERE s.id IS NULL AND c.school_id IS NOT NULL;

-- 42. Verificar class com grade_id inexistente
SELECT 'class com grade_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM class c 
LEFT JOIN grade g ON c.grade_id = g.id 
WHERE g.id IS NULL AND c.grade_id IS NOT NULL;

-- 43. Verificar school com city_id inexistente
SELECT 'school com city_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM school s 
LEFT JOIN city c ON s.city_id = c.id 
WHERE c.id IS NULL AND s.city_id IS NOT NULL;

-- 44. Verificar users com city_id inexistente
SELECT 'users com city_id inexistente' as problema, 
       COUNT(*) as quantidade
FROM users u 
LEFT JOIN city c ON u.city_id = c.id 
WHERE c.id IS NULL AND u.city_id IS NOT NULL;

-- 45. Verificar student_answers com corrected_by inexistente
SELECT 'student_answers com corrected_by inexistente' as problema, 
       COUNT(*) as quantidade
FROM student_answers sa 
LEFT JOIN users u ON sa.corrected_by = u.id 
WHERE u.id IS NULL AND sa.corrected_by IS NOT NULL;

-- 46. Verificar test_sessions com corrected_by inexistente
SELECT 'test_sessions com corrected_by inexistente' as problema, 
       COUNT(*) as quantidade
FROM test_sessions ts 
LEFT JOIN users u ON ts.corrected_by = u.id 
WHERE u.id IS NULL AND ts.corrected_by IS NOT NULL;
