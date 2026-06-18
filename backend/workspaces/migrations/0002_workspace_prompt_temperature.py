import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='workspace',
            name='system_prompt',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='workspace',
            name='temperature',
            field=models.FloatField(
                default=0.7,
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(2.0),
                ],
            ),
        ),
    ]
