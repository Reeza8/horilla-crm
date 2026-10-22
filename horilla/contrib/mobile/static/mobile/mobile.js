/*
 * Behaviour shared by mobile pages.
 *
 * - [data-open-dialog="id"] opens <dialog id>; [data-close-dialog] closes the
 *   dialog it sits in; tapping a dialog's backdrop closes it.
 * - [data-toggle-target="id"] shows or hides that element and swaps its own
 *   label between data-label-closed and data-label-open.
 * - An HTMX swap into #detail-sheet-body opens the record page's details
 *   sheet.
 * - [data-status-choice] buttons (record page) ask for confirmation, then post
 *   the change through the desktop stage update and reload the page.
 */
(function () {
    "use strict";

    function closest(el, selector) {
        return el && el.closest ? el.closest(selector) : null;
    }

    function showToast(text) {
        const box = document.getElementById("mobile-toast");
        if (!box || !text) {
            return;
        }
        box.textContent = text;
        box.hidden = false;
        window.setTimeout(function () {
            box.hidden = true;
        }, 3500);
    }

    document.addEventListener("click", function (event) {
        const opener = closest(event.target, "[data-open-dialog]");
        if (opener) {
            const dialog = document.getElementById(opener.dataset.openDialog);
            if (dialog && !dialog.open) {
                dialog.showModal();
            }
            return;
        }
        const closer = closest(event.target, "[data-close-dialog]");
        if (closer) {
            const dialog = closest(closer, "dialog");
            if (dialog) {
                dialog.close();
            }
            return;
        }
        if (event.target.tagName === "DIALOG" && event.target.open) {
            // A click on the dialog element itself is a click on its backdrop.
            event.target.close();
        }
    });

    document.addEventListener("click", function (event) {
        const toggle = closest(event.target, "[data-toggle-target]");
        if (!toggle) {
            return;
        }
        const target = document.getElementById(toggle.dataset.toggleTarget);
        if (!target) {
            return;
        }
        const open = target.hidden;
        target.hidden = !open;
        toggle.setAttribute("aria-expanded", String(open));
        const label = toggle.querySelector("[data-toggle-label]");
        if (label) {
            label.textContent = open ? toggle.dataset.labelOpen : toggle.dataset.labelClosed;
        }
        const icon = toggle.querySelector("i");
        if (icon) {
            icon.classList.toggle("rotate-180", open);
        }
        if (!open) {
            // Closing a long list: keep the button in view.
            toggle.scrollIntoView({block: "nearest"});
        }
    });

    // Record page: a tapped activity or note loads into the details sheet.
    document.addEventListener("htmx:afterSwap", function (event) {
        if (event.detail.target.id !== "detail-sheet-body") {
            return;
        }
        const sheet = document.getElementById("detail-sheet");
        if (sheet && !sheet.open) {
            sheet.showModal();
        }
    });

    // Record page: status change.
    let pendingChoice = null;

    document.addEventListener("click", function (event) {
        const choice = closest(event.target, "[data-status-choice]");
        if (!choice) {
            return;
        }
        const confirmDialog = document.getElementById("status-confirm");
        if (!confirmDialog) {
            return;
        }
        pendingChoice = choice;
        confirmDialog.querySelector("[data-confirm-text]").textContent =
            choice.dataset.confirm;
        const sheet = closest(choice, "dialog");
        if (sheet) {
            sheet.close();
        }
        confirmDialog.showModal();
    });

    document.addEventListener("click", function (event) {
        const accept = closest(event.target, "[data-status-accept]");
        if (!accept || !pendingChoice) {
            return;
        }
        const form = document.getElementById("status-form");
        const choice = pendingChoice;
        pendingChoice = null;
        accept.disabled = true;
        form.querySelector("[name=pipeline_value]").value = choice.dataset.value;
        fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            credentials: "same-origin",
            headers: {"HX-Request": "true"},
        })
            .then(function () {
                try {
                    sessionStorage.setItem(
                        "mobileStatusChange",
                        JSON.stringify({
                            path: location.pathname,
                            value: choice.dataset.value,
                            message: choice.dataset.success,
                        })
                    );
                } catch (error) {
                    // Private mode: the page still reloads, just without the toast.
                }
            })
            .finally(function () {
                location.reload();
            });
    });

    // After the reload, confirm a change that actually went through. An
    // error comes back as a regular message from the server instead.
    document.addEventListener("DOMContentLoaded", function () {
        let saved = null;
        try {
            saved = JSON.parse(sessionStorage.getItem("mobileStatusChange") || "null");
            sessionStorage.removeItem("mobileStatusChange");
        } catch (error) {
            saved = null;
        }
        if (!saved || saved.path !== location.pathname) {
            return;
        }
        const current = document.querySelector("[data-status-current]");
        if (current && current.dataset.statusCurrent === String(saved.value)) {
            showToast(saved.message);
        }
    });
})();
