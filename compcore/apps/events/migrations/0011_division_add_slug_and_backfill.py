from django.db import migrations, models
from django.utils.text import slugify


def backfill_division_slugs(apps, schema_editor):
    Division = apps.get_model('events', 'Division')
    db = schema_editor.connection.alias

    # Rellenar slugs de forma única por evento
    for div in Division.objects.using(db).all().select_related('event'):
        # Si ya viene algo en slug (por migraciones previas en otros entornos), normalízalo
        base = slugify((div.slug or div.name) or "") or "division"
        slug = base
        i = 2
        while Division.objects.using(db).filter(event=div.event, slug=slug).exclude(pk=div.pk).exists():
            slug = f"{base}-{i}"
            i += 1

        if div.slug != slug:
            div.slug = slug
            div.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0010_event_lanes_default'),
    ]

    operations = [
        # 1) Crear el campo slug en Division
        migrations.AddField(
            model_name='division',
            name='slug',
            field=models.SlugField(
                default='',
                help_text='Slug único dentro del evento.'
            ),
        ),
        # 2) Rellenar datos de slug de forma segura
        migrations.RunPython(backfill_division_slugs, migrations.RunPython.noop),
        # 3) Asegurar unicidad por (event, slug)
        migrations.AlterUniqueTogether(
            name='division',
            unique_together={('event', 'slug')},
        ),
    ]