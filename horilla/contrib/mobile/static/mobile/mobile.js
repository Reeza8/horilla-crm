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
 * - A "mobileToast" event from the server (HX-Trigger) shows a toast, with an
 *   Undo button when it carries one (mark as done on My work and the Agenda).
 * - People pickers in forms ([data-picker]): the summary follows the ticked
 *   boxes, and the search box filters the list.
 * - The Agenda's type filter ([data-calendar-filter]) saves through the desktop
 *   calendar's preference endpoint, then reloads the page.
 * - Edit details ([data-edit-form]): a related record ([data-choice]) is
 *   picked in the choice sheet, which pages through the desktop's select2
 *   search; on submit, the fields the user didn't change are left out.
 */
(function () {
    "use strict";

    function closest(el, selector) {
        return el && el.closest ? el.closest(selector) : null;
    }

    let toastTimer = null;

    function showToast(text, undo) {
        const box = document.getElementById("mobile-toast");
        if (!box || !text) {
            return;
        }
        box.textContent = "";
        const message = document.createElement("span");
        // The sentence reads in the page direction, whatever the title starts with.
        message.dir = document.documentElement.dir || "auto";
        message.textContent = text;
        box.appendChild(message);
        if (undo && window.htmx) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "ms-4 font-semibold text-primary-300";
            button.textContent = undo.label;
            button.addEventListener("click", function () {
                box.hidden = true;
                window.htmx.ajax("POST", undo.url, {
                    target: undo.target,
                    swap: "outerHTML",
                    values: undo.values,
                });
            });
            box.appendChild(button);
        }
        box.hidden = false;
        window.clearTimeout(toastTimer);
        toastTimer = window.setTimeout(function () {
            box.hidden = true;
        }, undo ? 6000 : 3500);
    }

    document.addEventListener("mobileToast", function (event) {
        const detail = event.detail || {};
        showToast(detail.message, detail.undo);
    });

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
        const chevron = toggle.querySelector(".fa-chevron-down");
        if (chevron) {
            chevron.classList.toggle("rotate-180", open);
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

    // People pickers: keep the summary in step with the ticked boxes.
    function pickerSummary(picker) {
        const summary = picker.querySelector("[data-picker-summary]");
        if (!summary) {
            return;
        }
        const names = Array.from(picker.querySelectorAll("input[type=checkbox]:checked")).map(
            function (box) {
                const label = closest(box, "label");
                return label ? label.textContent.trim() : "";
            }
        );
        summary.textContent = names.length
            ? names.join(picker.dataset.separator || ", ")
            : summary.dataset.empty;
    }

    document.addEventListener("change", function (event) {
        const picker = closest(event.target, "[data-picker]");
        if (picker && event.target.type === "checkbox") {
            pickerSummary(picker);
        }
    });

    document.addEventListener("input", function (event) {
        const search = event.target;
        if (!search.matches || !search.matches("[data-picker-search]")) {
            return;
        }
        const query = search.value.trim().toLowerCase();
        const picker = closest(search, "[data-picker]");
        picker.querySelectorAll("[data-picker-option]").forEach(function (option) {
            option.hidden = query !== "" && !option.textContent.toLowerCase().includes(query);
        });
    });

    // Agenda: save the type filter where the desktop calendar keeps it.
    function csrfToken() {
        try {
            return JSON.parse(document.body.getAttribute("hx-headers") || "{}")["X-CSRFToken"];
        } catch (error) {
            return "";
        }
    }

    document.addEventListener("submit", function (event) {
        const form = event.target;
        if (!form.matches("[data-calendar-filter]")) {
            return;
        }
        event.preventDefault();
        const types = Array.from(form.querySelectorAll("input[name=calendar_types]:checked")).map(
            function (box) {
                return box.value;
            }
        );
        const keep = JSON.parse(form.dataset.keep || "[]");
        const submit = form.querySelector("[type=submit]");
        if (submit) {
            submit.disabled = true;
        }
        fetch(form.dataset.url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken(),
                "X-Requested-With": "XMLHttpRequest",
            },
            body: JSON.stringify({calendar_types: types.concat(keep)}),
        }).finally(function () {
            location.reload();
        });
    });

    // Edit details: related records. The picked values live in hidden inputs
    // inside the field ([data-choice-values]), named as the desktop posts them.
    let choiceField = null;
    let choicePage = 1;
    let choiceRequest = 0;
    let choiceTimer = null;

    function choiceText(item) {
        // A record whose name is blank (e.g. a user without one) still shows.
        return String(item.text || "").trim() || "#" + item.id;
    }

    function choiceItems(field) {
        return Array.from(field.querySelectorAll("[data-choice-values] input"))
            .filter(function (input) {
                return input.value !== "";
            })
            .map(function (input) {
                return {id: input.value, text: input.dataset.label || ""};
            });
    }

    function setChoiceItems(field, items) {
        const values = field.querySelector("[data-choice-values]");
        values.textContent = "";
        // An empty value is posted when nothing is picked, to clear the field.
        (items.length ? items : [{id: "", text: ""}]).forEach(function (item) {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = field.dataset.postName;
            input.value = item.id;
            input.dataset.label = item.text;
            values.appendChild(input);
        });
        const summary = field.querySelector("[data-choice-summary]");
        summary.textContent = items.length
            ? items.map(choiceText).join(field.dataset.separator || ", ")
            : summary.dataset.empty;
        summary.classList.toggle("text-dark-400", !items.length);
    }

    function choiceRow(field, item, picked) {
        const row = document.createElement("li");
        const text = document.createElement("bdi");
        text.textContent = item.id === "" ? item.text : choiceText(item);
        if (field.hasAttribute("data-multiple")) {
            const label = document.createElement("label");
            label.className = "flex items-center gap-3 px-5 py-3";
            const box = document.createElement("input");
            box.type = "checkbox";
            box.checked = picked.has(String(item.id));
            box.dataset.choiceId = item.id;
            box.dataset.choiceText = item.text;
            label.append(box, text);
            row.appendChild(label);
        } else {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "flex w-full items-center justify-between gap-3 px-5 py-3";
            button.style.textAlign = "start";
            button.dataset.choiceId = item.id;
            button.dataset.choiceText = item.text;
            button.appendChild(text);
            if (picked.has(String(item.id))) {
                const check = document.createElement("i");
                check.className = "fa-solid fa-check text-primary-600";
                check.setAttribute("aria-hidden", "true");
                button.appendChild(check);
                button.setAttribute("aria-current", "true");
            }
            row.appendChild(button);
        }
        return row;
    }

    function loadChoices(append) {
        const sheet = document.getElementById("choice-sheet");
        const field = choiceField;
        const list = sheet.querySelector("[data-choice-results]");
        const query = sheet.querySelector("[data-choice-search]").value.trim();
        const url = new URL(field.dataset.url, location.href);
        url.searchParams.set("q", query);
        url.searchParams.set("page", String(choicePage));
        url.searchParams.set("field_name", field.dataset.field);
        const request = ++choiceRequest;
        fetch(url, {credentials: "same-origin", headers: {"X-Requested-With": "XMLHttpRequest"}})
            .then(function (response) {
                if (!response.ok) {
                    throw new Error(response.status);
                }
                return response.json();
            })
            .then(function (data) {
                if (request !== choiceRequest) {
                    return;
                }
                const picked = new Set(
                    choiceItems(field).map(function (item) {
                        return String(item.id);
                    })
                );
                if (!picked.size) {
                    picked.add(""); // "None" is the current choice
                }
                if (!append) {
                    list.textContent = "";
                    if (!query && field.hasAttribute("data-optional") && !field.hasAttribute("data-multiple")) {
                        list.appendChild(choiceRow(field, {id: "", text: sheet.dataset.noneLabel}, picked));
                    }
                }
                (data.results || []).forEach(function (item) {
                    list.appendChild(choiceRow(field, item, picked));
                });
                sheet.querySelector("[data-choice-more]").hidden = !(data.pagination && data.pagination.more);
                sheet.querySelector("[data-choice-error]").hidden = true;
                sheet.querySelector("[data-choice-empty]").hidden =
                    list.querySelector("[data-choice-id]:not([data-choice-id=''])") !== null;
            })
            .catch(function () {
                if (request === choiceRequest) {
                    sheet.querySelector("[data-choice-error]").hidden = false;
                }
            });
    }

    document.addEventListener("click", function (event) {
        const opener = closest(event.target, "[data-choice-open]");
        if (!opener) {
            return;
        }
        const sheet = document.getElementById("choice-sheet");
        choiceField = closest(opener, "[data-choice]");
        choicePage = 1;
        sheet.querySelector("[data-choice-title]").textContent =
            choiceField.querySelector("[data-choice-label]").textContent;
        sheet.querySelector("[data-choice-search]").value = "";
        sheet.querySelector("[data-choice-results]").textContent = "";
        sheet.querySelector("[data-choice-empty]").hidden = true;
        sheet.querySelector("[data-choice-error]").hidden = true;
        sheet.querySelector("[data-choice-more]").hidden = true;
        loadChoices(false);
        sheet.showModal();
        sheet.querySelector("[data-choice-title]").focus();
    });

    document.addEventListener("input", function (event) {
        if (!event.target.matches || !event.target.matches("[data-choice-search]")) {
            return;
        }
        window.clearTimeout(choiceTimer);
        choiceTimer = window.setTimeout(function () {
            choicePage = 1;
            loadChoices(false);
        }, 250);
    });

    // The keyboard's Search key searches; it must not submit the form around it.
    document.addEventListener("keydown", function (event) {
        if (event.key !== "Enter" || !event.target.matches || !event.target.matches("[data-choice-search]")) {
            return;
        }
        event.preventDefault();
        window.clearTimeout(choiceTimer);
        choicePage = 1;
        loadChoices(false);
    });

    document.addEventListener("click", function (event) {
        const sheet = closest(event.target, "#choice-sheet");
        if (!sheet || !choiceField) {
            return;
        }
        if (closest(event.target, "[data-choice-more]")) {
            choicePage += 1;
            loadChoices(true);
            return;
        }
        const pick = closest(event.target, "button[data-choice-id]");
        if (pick) {
            setChoiceItems(choiceField, pick.dataset.choiceId ? [{id: pick.dataset.choiceId, text: pick.dataset.choiceText}] : []);
            sheet.close();
        }
    });

    document.addEventListener("change", function (event) {
        const box = event.target;
        if (!choiceField || !box.matches || !box.matches("#choice-sheet input[data-choice-id]")) {
            return;
        }
        const items = choiceItems(choiceField).filter(function (item) {
            return String(item.id) !== box.dataset.choiceId;
        });
        if (box.checked) {
            items.push({id: box.dataset.choiceId, text: box.dataset.choiceText});
        }
        setChoiceItems(choiceField, items);
    });

    // Edit details: post only the fields the user changed.
    function fieldState(field) {
        return Array.from(field.querySelectorAll("[name]"))
            .filter(function (input) {
                return !((input.type === "checkbox" || input.type === "radio") && !input.checked);
            })
            .map(function (input) {
                return input.name + "=" + input.value;
            })
            .join("&");
    }

    const initialStates = new WeakMap();
    document.querySelectorAll("[data-edit-form] [data-edit-field]").forEach(function (field) {
        initialStates.set(field, fieldState(field));
    });

    document.addEventListener("submit", function (event) {
        if (!event.target.matches("[data-edit-form]")) {
            return;
        }
        event.target.querySelectorAll("[data-edit-field]").forEach(function (field) {
            if (fieldState(field) === initialStates.get(field)) {
                field.querySelectorAll("[name]").forEach(function (input) {
                    input.disabled = true;
                    input.dataset.editSkipped = "true";
                });
            }
        });
    });

    // Back to a form after saving (page cache): its fields post again.
    window.addEventListener("pageshow", function () {
        document.querySelectorAll("[data-edit-skipped]").forEach(function (input) {
            input.disabled = false;
            delete input.dataset.editSkipped;
        });
    });
})();
