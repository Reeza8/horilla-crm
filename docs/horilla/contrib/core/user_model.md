````markdown
# Custom User Model Handling in Horilla

## 🎯 Purpose

Horilla is designed to fully support Django’s `AUTH_USER_MODEL` mechanism without requiring changes across the codebase.

This is achieved by:
- Centralizing User model access
- Using a custom extensible User model (`HorillaUser`)
- Avoiding direct imports from Django’s default `User`

---

## 🧠 Core Concept

Instead of importing Django’s default User model:

```python
from django.contrib.auth.models import User  ❌
````

Horilla uses a centralized approach:

```python
from horilla.auth.models import User  ✅
```

Which internally resolves to:

```python
from django.contrib.auth import get_user_model

User = get_user_model()
```

📍 Location:

```
horilla/auth/models.py
```

---

## ⚙️ Active User Model Configuration

The active user model is defined in:

📍 `horilla/settings/base.py`

```python
AUTH_USER_MODEL = "horilla_core.HorillaUser"
```

This tells Django to use:

```
horilla_core.HorillaUser
```

as the main User model across the project.

---

## 🔁 How It Works

1. Django reads `AUTH_USER_MODEL`
2. `get_user_model()` returns `HorillaUser`
3. All imports from `horilla.auth.models` automatically use it

---

## 🔄 Changing the User Model

To switch to a different user model:

### ✅ Only update this:

```python
AUTH_USER_MODEL = "yourapp.YourCustomUserModel"
```

---

### 🚀 Result

* No need to change views, forms, or queries
* Entire project adapts automatically

---

## 👤 Default User Model: `HorillaUser`

Horilla provides a powerful custom user model:

```python
class HorillaUser(AbstractUser):
```

---

## 🧩 Key Features

### 📌 1. Extended Profile

* Profile image
* Contact number
* Country, state, city, zip code

---

### 🏢 2. Organization Mapping

* `company` → Company association
* `department` → Department mapping
* `role` → Role-based access

---

### 🌍 3. User Preferences

* Language
* Time zone
* Currency
* Time format
* Date format
* DateTime format
* Number grouping

---

### 🧾 4. Audit Fields

* `created_at`, `updated_at`
* `created_by`, `updated_by`

---

### 🔐 5. Permission Helper

```python
def has_any_perms(self, perm_list, obj=None):
```

* Checks multiple permissions
* Supports superuser override

---

### 🧠 6. Smart Defaults

```python
def save(self, *args, **kwargs):
    if not self.username and self.email:
        self.username = self.email

    if not self.password and self.contact_number:
        self.set_password(self.contact_number)

    super().save(*args, **kwargs)
```

---

### 🖼️ 7. Avatar Handling

* `get_avatar()` returns the uploaded **profile** image URL when present; otherwise a ui-avatars.com URL based on `first_name`
* `get_avatar_with_name()` reuses `get_avatar()` and returns ready-to-render HTML (avatar + full name) via `horilla.utils.html.format_html`

```python
def get_avatar()
def get_avatar_with_name()
```

---

### 🔗 8. URL Helpers

* Edit user
* Detail view
* Change company
* Delete user

---

### 🎨 9. UI Helper

```python
def get_avatar_with_name()
```

Returns ready-to-render HTML for UI components (list columns, etc.). Avatar source is always `get_avatar()`.

---

### 🧱 10. Constraints

```python
unique_together = ["company", "username", "role"]
```

---

### ⚙️ 11. Swappable Support

```python
class Meta:
    swappable = "AUTH_USER_MODEL"
```

---

## ⚠️ Important Guidelines

### ❌ Never do this:

```python
from django.contrib.auth.models import User
```

---

### ✅ Always do this:

```python
from horilla.auth.models import User
```

---

## 🧩 Benefits

* 🔄 Plug-and-play user model replacement
* 🧼 Clean architecture
* 🧠 AI-friendly structure
* 🛡️ Future-proof
* ⚡ No refactoring needed

---

## 📌 Summary

| Action            | Required                 |
| ----------------- | ------------------------ |
| Change User Model | Update `AUTH_USER_MODEL` |
| Refactor Code     | ❌ Not required           |
| Imports           | Already centralized      |

---

## 💡 Developer Recommendation

Always import User like this:

```python
from horilla.auth.models import User
```

---

## 🏁 Conclusion

Horilla’s user system is:

* Flexible
* Scalable
* Easy to customize

By combining:

* `get_user_model()`
* Centralized imports
* `HorillaUser`

You can safely extend or replace the user system with minimal effort.

---
