## 📄 `exceptions.md`

````markdown id="k2n8x1"
# Centralized Exception Handling in Horilla

## 🎯 Purpose

Horilla centralizes all exception imports through a single module:

``` id="x1m4ps"
horilla/core/exceptions.py
````

This avoids directly importing from Django across the project.

---

## 🧠 Core Concept

Instead of using:

```python
from django.core.exceptions import ValidationError  ❌
```

Always use:

```python id="y7c2qa"
from horilla.core.exceptions import ValidationError  ✅
```

---

## 📦 What This File Does

The file re-exports Django exceptions:

```python id="h9p3vd"
from django.core.exceptions import ...
```

And exposes them via:

```python id="q4mz7n"
__all__ = [ ... ]
```

---

## 🔁 Why This Approach?

* 🔄 Centralized import management
* 🧼 Cleaner and consistent codebase
* 🔧 Easy to extend in future
* 🤖 AI-friendly structure

---

## 🚀 Future Extensibility

You can add custom exceptions here:

```python id="c8w2la"
class CustomHorillaException(Exception):
    pass
```

Then use it anywhere:

```python id="p1z8rt"
from horilla.core.exceptions import CustomHorillaException
```

---

## ⚠️ Important Rule

### ❌ Do NOT import directly:

```python id="z9k3lm"
from django.core.exceptions import *
```

---

### ✅ ALWAYS use:

```python id="m5t7xs"
from horilla.core.exceptions import *
```

---

## 📌 Summary

| Action             | Approach                  |
| ------------------ | ------------------------- |
| Import exceptions  | `horilla.core.exceptions` |
| Add new exceptions | Add in centralized file   |
| Modify behavior    | Do it in one place        |

---

## 🏁 Conclusion

This pattern ensures:

* Consistency across Horilla and all apps
* Easy maintainability
* Future-proof exception handling

---

## Exception chaining (`raise ... from`)

When catching an exception and re-raising a **different** type (or a clearer message), chain the original cause so tracebacks stay debuggable:

```python
# ✅ Preferred — preserves root cause in traceback
try:
    followup_number = int(followup_number)
except (ValueError, TypeError) as exc:
    raise ValueError(f"Invalid follow-up number: {followup_number}") from exc

try:
    obj = super().get_object(queryset)
except Http404 as exc:
    raise Http404(f"{self.model._meta.object_name} matching query does not exist.") from exc
```

```python
# ❌ Avoid — loses the original exception context
except ValueError:
    raise ValueError("Invalid value")
```

Apply this in forms (`ValidationError`), views (`HttpNotFound`, `Http404`), serializers, mail backends, and delete/reassign mixins. User-facing messages stay the same; server logs and Sentry-style tools show the full chain.

---
