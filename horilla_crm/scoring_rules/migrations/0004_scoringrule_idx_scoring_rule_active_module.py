from django.conf import settings
from django.db import migrations, models

INDEX_NAME = "idx_scoring_rule_active_module"

INDEX = models.Index(
    fields=["module"],
    condition=models.Q(("is_active", True)),
    name=INDEX_NAME,
)


def add_index_if_missing(apps, schema_editor):
    """
    Create the partial index only where it is not already present.

    0001_initial builds the tables for a fresh install with
    ``live_apps.get_model(...)`` + ``schema_editor.create_model(model)`` -- the
    *live* model, not the historical one. The live ScoringRule.Meta already
    declares this index, so a fresh database gets it during 0001 and a plain
    AddIndex here fails with "index idx_scoring_rule_active_module already
    exists". Databases migrated before the index was added to Meta do not have
    it, so the operation cannot simply be dropped either.

    This is not a SQLite quirk -- 0001 uses the live model on every backend.
    """
    model = apps.get_model("scoring_rules", "ScoringRule")
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        existing = connection.introspection.get_constraints(
            cursor, model._meta.db_table
        )
    if INDEX_NAME in existing:
        return
    schema_editor.add_index(model, INDEX)


def drop_index_if_present(apps, schema_editor):
    """Reverse: remove the index only if it is actually there."""
    model = apps.get_model("scoring_rules", "ScoringRule")
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        existing = connection.introspection.get_constraints(
            cursor, model._meta.db_table
        )
    if INDEX_NAME not in existing:
        return
    schema_editor.remove_index(model, INDEX)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_alter_recyclebin_deleted_by_and_more"),
        ("scoring_rules", "0003_alter_emailactivityscoring_created_at_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name="scoringrule",
                    index=INDEX,
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    add_index_if_missing,
                    drop_index_if_present,
                ),
            ],
        ),
    ]
