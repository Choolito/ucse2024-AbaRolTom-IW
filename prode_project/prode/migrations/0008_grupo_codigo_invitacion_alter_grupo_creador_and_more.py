# Generated by Django 5.1 on 2024-09-13 01:20

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prode', '0007_alter_partido_status_alter_prediccion_usuario_grupo'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='grupo',
            name='codigo_invitacion',
            field=models.CharField(blank=True, max_length=10, unique=True),
        ),
        migrations.AlterField(
            model_name='grupo',
            name='creador',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='grupo',
            name='descripcion',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='grupo',
            name='privacidad',
            field=models.CharField(choices=[('publico', 'Público'), ('privado', 'Privado')], max_length=10),
        ),
    ]
