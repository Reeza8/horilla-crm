"""
Initial schema for the Field Settings app.

The app merges the former ``custom_fields``, ``field_requirements`` and
``form_layouts`` apps. A plain ``migrate`` handles both cases:

* Fresh install: the four tables are created.
* Existing install: the old apps' tables are renamed in place (rows, ids and
  foreign keys are kept), and the references the old app labels left behind
  are remapped to ``field_management`` -- ContentType rows (and with them
  permissions and audit entries), stored ``app_label`` fields, recycle bin
  entries, audit log text and the old apps' migration records.
"""

import json

import django.db.models.deletion
import horilla.contrib.field_management.registry.field_requirements
import horilla.contrib.field_management.registry.form_layouts
from django.apps import apps as global_apps
from django.conf import settings
from django.db import migrations, models
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import F, Value
from django.db.models.functions import Concat, Replace, Substr

NEW_LABEL = "field_management"

# Model name -> table used by the app that owned it before the merge.
LEGACY_TABLES = {
    "CustomFieldDefinition": "custom_fields_customfielddefinition",
    "CustomFieldValue": "custom_fields_customfieldvalue",
    "FieldRequirement": "field_requirements_fieldrequirement",
    "FormLayoutField": "form_layouts_formlayoutfield",
}

# Old app label -> lower-case model names (as stored in ContentType.model).
LEGACY_MODELS = {
    "custom_fields": ["customfielddefinition", "customfieldvalue"],
    "field_requirements": ["fieldrequirement"],
    "form_layouts": ["formlayoutfield"],
}

CAMEL_NAMES = {
    "customfielddefinition": "CustomFieldDefinition",
    "customfieldvalue": "CustomFieldValue",
    "fieldrequirement": "FieldRequirement",
    "formlayoutfield": "FormLayoutField",
}

# Columns the merged models have that some legacy tables do not:
# model name -> field names to add after the table is renamed. Each is added
# only when the renamed table lacks it, because installs older than 1.15.2
# have no value_date/value_datetime (custom_fields 0004) while 1.15.2 and
# later already do.
NEW_COLUMNS = {
    "CustomFieldDefinition": ["is_full_width"],
    "CustomFieldValue": ["value_date", "value_datetime"],
    "FormLayoutField": ["is_full_width"],
}


def create_or_rename_tables(apps, schema_editor):
    """Rename each legacy table to its new name, or create the table if absent."""
    existing = set(schema_editor.connection.introspection.table_names())
    for model_name, legacy_table in LEGACY_TABLES.items():
        model = apps.get_model(NEW_LABEL, model_name)
        new_table = model._meta.db_table
        if new_table in existing:
            continue
        if legacy_table in existing:
            schema_editor.alter_db_table(model, legacy_table, new_table)
            # A renamed legacy table may lack columns the merged model has.
            with schema_editor.connection.cursor() as cursor:
                present = {
                    column.name
                    for column in schema_editor.connection.introspection.get_table_description(
                        cursor, new_table
                    )
                }
            for field_name in NEW_COLUMNS.get(model_name, []):
                field = model._meta.get_field(field_name)
                if field.column not in present:
                    schema_editor.add_field(model, field)
        else:
            schema_editor.create_model(model)
        existing.add(new_table)


def remap_legacy_references(apps, schema_editor):
    """Point everything that referenced the old app labels at field_management."""
    db = schema_editor.connection.alias

    # Content types: keep the original rows so permissions and audit entries
    # follow; any fresh field_management rows for the same models are replaced.
    ContentType = apps.get_model("contenttypes", "ContentType")
    for old_label, model_names in LEGACY_MODELS.items():
        for model_name in model_names:
            legacy = ContentType.objects.using(db).filter(
                app_label=old_label, model=model_name
            )
            if legacy.exists():
                ContentType.objects.using(db).filter(
                    app_label=NEW_LABEL, model=model_name
                ).delete()
                legacy.update(app_label=NEW_LABEL)

    # Stored app_label fields.
    for model_name in (
        "KanbanGroupBy",
        "TimelineSpanBy",
        "QuickFilter",
        "ImportHistory",
        "ListColumnVisibility",
        "DetailFieldVisibility",
    ):
        try:
            Model = apps.get_model("core", model_name)
        except LookupError:
            continue
        if not any(f.name == "app_label" for f in Model._meta.get_fields()):
            continue
        for old_label in LEGACY_MODELS:
            Model._base_manager.using(db).filter(app_label=old_label).update(
                app_label=NEW_LABEL
            )

    # Recycle bin: "<app>.<model>" prefixes.
    try:
        RecycleBin = apps.get_model("core", "RecycleBin")
    except LookupError:
        RecycleBin = None
    if RecycleBin is not None:
        for old_label in LEGACY_MODELS:
            prefix = f"{old_label}."
            RecycleBin._base_manager.using(db).filter(
                model_name__startswith=prefix
            ).update(
                model_name=Concat(
                    Value(f"{NEW_LABEL}."), Substr(F("model_name"), len(prefix) + 1)
                )
            )

    _patch_audit_log(db)

    # The old apps' migration history no longer applies.
    MigrationRecorder(schema_editor.connection).migration_qs.filter(
        app__in=list(LEGACY_MODELS)
    ).delete()


def _patch_audit_log(db):
    """Rewrite ``<old_label>.<model>`` text in audit entries of these models.

    Only fully qualified references are replaced: a bare ``custom_fields``
    also occurs in unrelated names such as ``removed_custom_fields``.
    """
    try:
        LogEntry = global_apps.get_model("auditlog", "LogEntry")
    except LookupError:
        return
    replacements = []
    for old_label, model_names in LEGACY_MODELS.items():
        for model_name in model_names:
            camel = CAMEL_NAMES[model_name]
            replacements.append((f"{old_label}.{model_name}", f"{NEW_LABEL}.{model_name}"))
            replacements.append((f"{old_label}.{camel}", f"{NEW_LABEL}.{camel}"))

    entries = LogEntry.objects.using(db).filter(
        content_type__app_label=NEW_LABEL,
        content_type__model__in=[m for ms in LEGACY_MODELS.values() for m in ms],
    )
    for old, new in replacements:
        entries.filter(object_repr__contains=old).update(
            object_repr=Replace(F("object_repr"), Value(old), Value(new))
        )
    for entry in entries.only("id", "changes").iterator(chunk_size=500):
        if not entry.changes:
            continue
        data = entry.changes
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError:
                continue
        original = json.dumps(data)
        patched = original
        for old, new in replacements:
            patched = patched.replace(old, new)
        if patched != original:
            entry.changes = json.loads(patched)
            entry.save(update_fields=["changes"])


def forwards(apps, schema_editor):
    """Create or rename the tables, then remap legacy references."""
    create_or_rename_tables(apps, schema_editor)
    remap_legacy_references(apps, schema_editor)


def drop_tables(apps, schema_editor):
    """Drop the tables created by this migration (reverse of a fresh install)."""
    # Values reference definitions, so drop in reverse dependency order.
    for model_name in (
        "FormLayoutField",
        "FieldRequirement",
        "CustomFieldValue",
        "CustomFieldDefinition",
    ):
        schema_editor.delete_model(apps.get_model(NEW_LABEL, model_name))


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("core", "0010_alter_recyclebin_deleted_by_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # State first, so the RunPython below can resolve the models.
        migrations.SeparateDatabaseAndState(
            state_operations=[
            migrations.CreateModel(
                name='CustomFieldDefinition',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Is Active')),
                    ('additional_info', models.JSONField(blank=True, null=True, verbose_name='Additional Info')),
                    ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                    ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                    ('name', models.CharField(max_length=255, verbose_name='Field Name')),
                    ('field_type', models.CharField(choices=[('small_text', 'Small Text'), ('large_text', 'Large Text'), ('number', 'Number'), ('choice', 'Multiple Choice'), ('single_choice', 'Single Choice'), ('date', 'Date'), ('datetime', 'Date and Time')], max_length=20, verbose_name='Field Type')),
                    ('is_required', models.BooleanField(default=False, verbose_name='Required')),
                    ('choices', models.TextField(blank=True, help_text='Comma-separated list of choices (only for Multiple Choice type)', verbose_name='Choices')),
                    ('order', models.PositiveIntegerField(default=0, verbose_name='Display Order')),
                    ('is_full_width', models.BooleanField(default=False, help_text='Span both columns of the form.', verbose_name='Full Width')),
                    ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.company', verbose_name='Company')),
                    ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.horillacontenttype', verbose_name='Model')),
                    ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                    ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='Updated By')),
                ],
                options={
                    'verbose_name': 'Custom Field',
                    'verbose_name_plural': 'Custom Fields',
                    'ordering': ['order', 'pk'],
                    'unique_together': {('content_type', 'name', 'company')},
                },
            ),
            migrations.CreateModel(
                name='CustomFieldValue',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Is Active')),
                    ('additional_info', models.JSONField(blank=True, null=True, verbose_name='Additional Info')),
                    ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                    ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                    ('object_id', models.PositiveIntegerField(verbose_name='Object ID')),
                    ('value_text', models.TextField(blank=True, default='', verbose_name='Value')),
                    ('value_number', models.DecimalField(blank=True, decimal_places=4, max_digits=20, null=True, verbose_name='Numeric Value')),
                    ('value_date', models.DateField(blank=True, null=True, verbose_name='Date Value')),
                    ('value_datetime', models.DateTimeField(blank=True, null=True, verbose_name='Date and Time Value')),
                    ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.company', verbose_name='Company')),
                    ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.horillacontenttype', verbose_name='Model')),
                    ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                    ('field_definition', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='values', to='field_management.customfielddefinition', verbose_name='Field Definition')),
                    ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='Updated By')),
                ],
                options={
                    'verbose_name': 'Custom Field Value',
                    'verbose_name_plural': 'Custom Field Values',
                    'unique_together': {('field_definition', 'content_type', 'object_id')},
                },
            ),
            migrations.CreateModel(
                name='FieldRequirement',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Is Active')),
                    ('additional_info', models.JSONField(blank=True, null=True, verbose_name='Additional Info')),
                    ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                    ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                    ('field_name', models.CharField(max_length=255, verbose_name='Field')),
                    ('is_required', models.BooleanField(default=True, help_text='When enabled the field must be filled in. When disabled the field becomes optional on create and edit forms.', verbose_name='Required')),
                    ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.company', verbose_name='Company')),
                    ('content_type', models.ForeignKey(limit_choices_to=horilla.contrib.field_management.registry.field_requirements.limit_content_types, on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='core.horillacontenttype', verbose_name='Model')),
                    ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                    ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='Updated By')),
                ],
                options={
                    'verbose_name': 'Field Requirement',
                    'verbose_name_plural': 'Field Requirements',
                    'ordering': ['content_type__model', 'field_name'],
                    'unique_together': {('content_type', 'field_name', 'company')},
                },
            ),
            migrations.CreateModel(
                name='FormLayoutField',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Is Active')),
                    ('additional_info', models.JSONField(blank=True, null=True, verbose_name='Additional Info')),
                    ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                    ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                    ('field_name', models.CharField(max_length=255, verbose_name='Field')),
                    ('is_visible', models.BooleanField(default=True, verbose_name='Show on Form')),
                    ('sequence', models.PositiveIntegerField(default=0, verbose_name='Sequence')),
                    ('is_full_width', models.BooleanField(default=False, verbose_name='Full Width')),
                    ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.company', verbose_name='Company')),
                    ('content_type', models.ForeignKey(limit_choices_to=horilla.contrib.field_management.registry.form_layouts.limit_content_types, on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='core.horillacontenttype', verbose_name='Model')),
                    ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                    ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='Updated By')),
                ],
                options={
                    'verbose_name': 'Form Layout Field',
                    'verbose_name_plural': 'Form Layout Fields',
                    'ordering': ['content_type__model', 'sequence', 'pk'],
                    'unique_together': {('content_type', 'field_name', 'company')},
                },
            ),
            ],
        ),
        migrations.RunPython(forwards, drop_tables),
    ]
