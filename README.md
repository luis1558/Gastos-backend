# Backend

Backend para la app de gastos construido con FastAPI, SQLAlchemy y PostgreSQL
en Supabase.

## Estructura

La aplicacion sigue una organizacion modular por dominio:

- `app/api`: routers HTTP y versionado de endpoints.
- `app/core`: configuracion, seguridad y componentes transversales.
- `app/db`: base declarativa, sesion y utilidades de persistencia.
- `app/modules`: dominios del negocio separados por contexto.
- `app/shared`: piezas reutilizables entre modulos.
- `app/tests`: pruebas.

## Dominios iniciales

- `auth`: login, refresh tokens y JWT.
- `users`: usuarios y perfil.
- `income`: configuracion mensual de ingresos.
- `expenses`: categorias y gastos.
- `debts`: deudas y abonos.
- `reports`: agregados y resumentes para dashboard.

## Seeds utiles

Para cargar categorias base a un usuario existente:

```bash
venv/bin/python scripts/seed_expense_categories.py --email usuario@correo.com
```
# Gastos-backend
