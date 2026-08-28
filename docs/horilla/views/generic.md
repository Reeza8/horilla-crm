# Horilla generic views (`horilla.views.generic`)

Thin Django CBV wrappers that apply Horilla extension composition. Import from this package when you need platform hooks without the full generics list/detail stack.

```python
from horilla.views.generic import View, FormView, ListView
```

Supported re-exports in this package:

- `FormView`
- `View`
- `TemplateView`
- `ListView`
- `DetailView`

In `horilla.contrib` modules, place `from horilla.views.generic import ...` under `# First party imports (Horilla)` (not under Django imports).

If you need a CBV that is not exported here (for example `DeleteView`), import it directly from Django.

---

## `View`

```python
from horilla.views.generic import View
```

Subclass of Django’s `View`. `as_view()` resolves [`_inherit_view`](../extension/view/inherit.md) extensions for the **concrete** subclass on each request (same late-binding idea as list/card/kanban).

```python
from horilla.extension.view import ViewExtension

class JalaliEditFieldViewExtension(ViewExtension):
    _inherit_view = (
        "horilla.contrib.generics.views.helpers.edit_field.EditFieldView"
    )

    def get_field_info(self, field, obj, user=None):
        ...
```

Examples that inherit this base: `EditFieldView`, `UpdateFieldView`, `CancelEditView`.

Direct instantiation must go through `resolve_view_class` (or helpers such as `get_edit_field_view()`) so extensions apply.

---

## `FormView`

```python
from horilla.views.generic import FormView
```

Subclass of Django’s `FormView`. `get_form_class()` returns `resolve_form_class(base)` so registered `FormExtension` classes apply.

```python
class ReginalFormatingView(LoginRequiredMixin, FormView):
    form_class = RegionalFormattingForm

    def get(self, request, *args, **kwargs):
        form = self.get_form_class()(instance=request.user)
        ...
```

Do **not** instantiate `RegionalFormattingForm(...)` directly in the view if extensions should run — always go through `get_form_class()`.

`HorillaSingleFormView` / `HorillaMultiStepFormView` already call `resolve_form_class()`; they do not need this wrapper.

Lazy import of `resolve_form_class` avoids a cycle: `horilla.extension.forms.compose` imports `HorillaModelForm` from generics.

---

## `ListView`

```python
from horilla.views.generic import ListView
```

Thin wrapper around Django’s `ListView` (no extension resolve of its own). Prefer `HorillaListView` when you need `_inherit_list`, filters, bulk actions, etc.

---

## Related

- [View `_inherit_view`](../extension/view/inherit.md)
- [Form `_inherit_form`](../extension/forms/inherit.md)
- [Regional formatting](../contrib/core/core_app.md#regional-formatting)
- [Edit field helpers](../contrib/generics/views/helpers/edit_field.md)
- [Coding rules — import `horilla.views.generic`](../coding_rule.md#avoid-direct-django-usage)
