from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        # Remove legacy fields
        migrations.RemoveField(
            model_name="auditevent",
            name="actor_user_id",
        ),
        migrations.RemoveField(
            model_name="auditevent",
            name="event_type",
        ),
        migrations.RemoveField(
            model_name="auditevent",
            name="scope",
        ),

        # Add new fields
        migrations.AddField(
            model_name="auditevent",
            name="actor_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="event_name",
            field=models.CharField(default="__bootstrap__", max_length=128),
            preserve_default=False,
        ),

        # Ensure non-null + json defaults (NO PK CHANGES)
        migrations.AlterField(
            model_name="auditevent",
            name="company_id",
            field=models.UUIDField(),
        ),
        migrations.AlterField(
            model_name="auditevent",
            name="payload",
            field=models.JSONField(default=dict),
        ),

        # CRITICAL: No AlterField on "id"
        # CRITICAL: No RenameModel / AlterModelTable here
    ]
