from django.db import migrations, models, connection


def ensure_created_at_column(apps, schema_editor):
    """
    Asegura que la columna 'created_at' exista en la tabla física.
    - Si ya existe: no hace nada.
    - Si no existe: la crea con NOT NULL y DEFAULT CURRENT_TIMESTAMP.
    Esto es robusto para SQLite y evita fallos por duplicar columnas.
    """
    table_name = "events_heatassignment"
    col_name = "created_at"

    with connection.cursor() as cursor:
        # Listado de columnas actuales
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        cols = [row[1] for row in cursor.fetchall()]  # row[1] = name
        if col_name not in cols:
            # Creamos columna (NOT NULL con default de timestamp actual)
            cursor.execute(
                f"ALTER TABLE {table_name} "
                f"ADD COLUMN {col_name} datetime NOT NULL DEFAULT CURRENT_TIMESTAMP"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0011_division_add_slug_and_backfill"),
    ]

    operations = [
        # 1) Asegura la columna en la BD física (idempotente)
        migrations.RunPython(ensure_created_at_column, migrations.RunPython.noop),

        # 2) Actualiza el "estado" de Django para incluir el campo en el modelo,
        #    SIN tocar la BD (ya la tocamos arriba en RunPython o ya existía).
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="heatassignment",
                    name="created_at",
                    field=models.DateTimeField(auto_now_add=True),
                ),
            ],
        ),
    ]