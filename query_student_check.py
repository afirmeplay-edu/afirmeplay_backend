"""Script temporário: consulta student no schema da cidade e users em public (matrículas 2024001, 2024002)."""
from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    schema = "city_4f5078e3_58a5_48e6_bca9_e3f85d35f87e"
    # 1) student no schema da cidade
    db.session.execute(text(f'SET search_path TO "{schema}", public'))
    r = db.session.execute(text("SELECT id, name, registration, user_id FROM student WHERE registration IN ('2024001', '2024002')"))
    rows = r.fetchall()
    print("=== student no schema", schema, "===")
    print("Registros com matrícula 2024001 ou 2024002:", len(rows))
    for row in rows:
        print(dict(row._mapping))
    # 2) public.users
    db.session.execute(text("SET search_path TO public"))
    r2 = db.session.execute(text("SELECT id, name, email, registration, role FROM users WHERE registration IN ('2024001', '2024002')"))
    rows2 = r2.fetchall()
    print()
    print("=== public.users com matrícula 2024001 ou 2024002 ===")
    print("Registros:", len(rows2))
    for row in rows2:
        print(dict(row._mapping))
