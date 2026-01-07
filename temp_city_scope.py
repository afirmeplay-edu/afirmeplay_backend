from app import create_app
from app.models.classTest import ClassTest
from app.models.student import Student
from app.models.studentClass import Class
from app.models.school import School
from app.models.evaluationResult import EvaluationResult

TEST_ID = '9d5ea14f-be9f-4b2d-abee-c38ae564addf'
CITY_ID = 'f252f786-cac5-439f-b0b1-8e3e558f2636'

app = create_app()
with app.app_context():
    class_tests = ClassTest.query.filter_by(test_id=TEST_ID).all()
    class_ids = [ct.class_id for ct in class_tests if ct.class_id]
    print('class_ids:', class_ids)

    classes = Class.query.filter(Class.id.in_(class_ids)).all() if class_ids else []
    class_map = {cls.id: cls for cls in classes}

    schools = {}
    for cls in classes:
        if cls.school_id:
            school = School.query.get(cls.school_id)
            schools[cls.school_id] = school
    print('schools involved:', [(sid, sch.name if sch else None) for sid, sch in schools.items()])

    results = EvaluationResult.query.filter_by(test_id=TEST_ID).all()
    city_results = []
    for res in results:
        student = res.student
        if not student:
            continue
        cls = class_map.get(student.class_id)
        if not cls or not cls.school_id:
            continue
        school = schools.get(cls.school_id)
        if school and str(school.city_id) == CITY_ID:
            city_results.append((res, school))

    print('Total city results:', len(city_results))
    for res, school in city_results:
        student = res.student
        print(f"student {student.id} name={student.name} school={school.name} classification={res.classification}")

    students = Student.query.filter(Student.class_id.in_(class_ids)).all() if class_ids else []
    city_students = []
    for stu in students:
        cls = class_map.get(stu.class_id)
        if not cls or not cls.school_id:
            continue
        school = schools.get(cls.school_id)
        if school and str(school.city_id) == CITY_ID:
            city_students.append(stu)
    print('Total students in city scope:', len(city_students))
