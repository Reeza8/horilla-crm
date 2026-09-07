"""
Tests for Horilla _inherit_tab tab view extensions.
"""

from django.test import RequestFactory, SimpleTestCase
from django.views.generic import TemplateView

from horilla.extension.tab import clear_tab_extension_cache, resolve_tab_view_class
from horilla.extension.tab.compose import compose_tab_view_class
from horilla.extension.tab.metaclass import TabExtension
from horilla.extension.tab.registry import (
    TAB_COMPOSED_MAP,
    TAB_EXTENSION_REGISTRY,
    TabExtensionSpec,
    register_tab_extension,
)


class _TargetTabView(TemplateView):
    """Minimal tab-like target for compose tests."""

    template_name = "tab_view.html"

    def get_tabs(self):
        return [
            {
                "title": "Core",
                "url": "/core/",
                "target": "core-content",
                "id": "core-tab",
            }
        ]


class _ExtTab(TabExtension):
    """Sample tab extension registered against _TargetTabView."""

    _inherit_tab = "horilla.extension.tab.tests._TargetTabView"

    def get_tabs(self):
        tabs = list(_TargetTabView.get_tabs(self))
        tabs.append(
            {
                "title": "Extra",
                "url": "/extra/",
                "target": "extra-content",
                "id": "extra-tab",
            }
        )
        return tabs


class TabExtensionMetaclassTests(SimpleTestCase):
    """Tests for TabExtension registration and validation."""

    def test_invalid_inherit_tab_raises(self):
        """Reject _inherit_tab paths without module.Class form."""
        with self.assertRaises(ValueError):

            class _BadTabExt(TabExtension):
                """Extension with invalid _inherit_tab path."""

                _inherit_tab = "invalid-no-dot"

    def test_extension_class_is_registered(self):
        """Registered extensions are flagged and cannot be instantiated."""
        self.assertTrue(getattr(_ExtTab, "_is_tab_extension", False))
        with self.assertRaises(TypeError):
            _ExtTab()


class TabExtensionComposeTests(SimpleTestCase):
    """Tests for compose_tab_view_class and composed get_tabs."""

    def setUp(self):
        """Isolate registry and register a single test extension spec."""
        self._saved_registry = {k: list(v) for k, v in TAB_EXTENSION_REGISTRY.items()}
        clear_tab_extension_cache()
        TAB_EXTENSION_REGISTRY.clear()
        TAB_COMPOSED_MAP.clear()
        register_tab_extension(
            TabExtensionSpec(
                inherit_tab="horilla.extension.tab.tests._TargetTabView",
                class_name="_ExtTab",
                module="horilla.extension.tab.tests",
                extension_app_label="tests",
                methods={
                    "get_tabs": _ExtTab.__dict__["get_tabs"],
                },
            )
        )

    def tearDown(self):
        """Restore registry and clear composed view cache."""
        clear_tab_extension_cache()
        TAB_EXTENSION_REGISTRY.clear()
        TAB_EXTENSION_REGISTRY.update(self._saved_registry)
        TAB_COMPOSED_MAP.clear()

    def test_compose_marks_extended_class(self):
        """Composed class carries markers and wraps the target."""
        path = "horilla.extension.tab.tests._TargetTabView"
        composed = compose_tab_view_class(path, target=_TargetTabView)
        self.assertTrue(getattr(composed, "__horilla_tab_composed__", False))
        self.assertIs(composed.__wrapped_tab_view__, _TargetTabView)
        self.assertEqual(composed.__horilla_tab_path__, path)

    def test_composed_get_tabs_appends_extension_tab(self):
        """Extension get_tabs appends onto the target tab list."""
        path = "horilla.extension.tab.tests._TargetTabView"
        composed = compose_tab_view_class(path, target=_TargetTabView)
        request = RequestFactory().get("/")
        view = composed()
        view.request = request
        tabs = view.get_tabs()
        self.assertEqual([t["id"] for t in tabs], ["core-tab", "extra-tab"])

    def test_resolve_returns_composed(self):
        """resolve_tab_view_class returns the composed class when registered."""
        path = "horilla.extension.tab.tests._TargetTabView"
        TAB_COMPOSED_MAP[path] = compose_tab_view_class(path, target=_TargetTabView)
        resolved = resolve_tab_view_class(_TargetTabView)
        self.assertTrue(getattr(resolved, "__horilla_tab_composed__", False))
