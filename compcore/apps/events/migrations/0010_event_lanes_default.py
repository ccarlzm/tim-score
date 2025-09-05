# Generated manually to add lanes_default to Event
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0009_alter_workoutheat_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='lanes_default',
            field=models.PositiveIntegerField(
                default=8,
                help_text="Carriles por defecto si la división no define capacidad."
            ),
        ),
    ]