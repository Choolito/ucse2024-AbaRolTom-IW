# Generated by Django 5.1 on 2024-08-25 20:01

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prode', '0002_prediccion'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='prediccion',
            name='partido',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='predicciones', to='prode.partido'),
        ),
        migrations.AlterUniqueTogether(
            name='prediccion',
            unique_together={('partido', 'usuario')},
        ),
    ]
