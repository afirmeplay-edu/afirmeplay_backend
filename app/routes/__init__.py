from flask import Flask

def register_routes(app: Flask):
    # Imports
    from . import (
        admin_route,
        city_routes,
        class_routes,
        educationStage_routes,
        grades_routes,
        login,
        logout,
        persistUser_routes,
        professor_route,
        question_routes,
        school_routes,
        schoolTeacher,
        skill_routes,
        student_answer_routes,
        student_routes,
        subject_routes,
        teacherClass,
        test_routes,
        user_routes,
        userQuickLinks_routes,
        evaluation_results_routes
    )
    
    # Register blueprints
    app.register_blueprint(admin_route.bp)
    app.register_blueprint(city_routes.bp)
    app.register_blueprint(class_routes.bp)
    app.register_blueprint(educationStage_routes.bp)
    app.register_blueprint(grades_routes.bp)
    app.register_blueprint(login.bp)
    app.register_blueprint(logout.bp)
    app.register_blueprint(persistUser_routes.bp)
    app.register_blueprint(professor_route.bp)
    app.register_blueprint(question_routes.bp)
    app.register_blueprint(school_routes.bp)
    app.register_blueprint(schoolTeacher.bp)
    app.register_blueprint(skill_routes.bp)
    app.register_blueprint(student_answer_routes.bp)
    app.register_blueprint(student_routes.bp)
    app.register_blueprint(subject_routes.bp)
    app.register_blueprint(teacherClass.bp)
    app.register_blueprint(test_routes.bp)
    app.register_blueprint(user_routes.bp)
    app.register_blueprint(userQuickLinks_routes.bp)
    app.register_blueprint(evaluation_results_routes.bp)
