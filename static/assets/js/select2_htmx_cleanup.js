/*
 * Select2 dropdowns are appended to <body> by default, outside the DOM
 * subtree of the <select> that owns them. If an htmx swap replaces that
 * subtree (e.g. changing the filter "field" swaps out the "operator"
 * select) while the dropdown is still open -- which can happen once the
 * response for one change arrives after the user has already opened a
 * different dropdown -- the open dropdown is orphaned: its <select> is
 * gone, but the floating popup under <body> is never told to close, so
 * it stays on screen indefinitely, even after the surrounding panel/modal
 * is closed.
 *
 * This closes any open Select2 before a swap can remove its <select>,
 * and sweeps up any popup that still slipped through afterwards.
 */
(function () {
    function closeOpenSelect2Dropdowns() {
        if (window.jQuery) {
            jQuery(".select2-hidden-accessible").select2("close");
        }
    }

    function removeOrphanedSelect2Popups() {
        document.querySelectorAll("body > .select2-container").forEach(function (el) {
            el.remove();
        });
    }

    document.addEventListener("htmx:beforeSwap", closeOpenSelect2Dropdowns);
    document.addEventListener("htmx:afterSwap", removeOrphanedSelect2Popups);
})();
