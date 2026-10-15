/*
 * Calendar page behaviour. Everything that needs Django (URLs, CSRF token,
 * translations, icon paths) is read from CALENDAR_CONFIG, which calendar.html
 * defines before loading this file.
 */


function showCalendarMessage(level, text) {
    $('#messages-container').append(
        $('<div class="message"></div>').attr('data-level', level).attr('data-message', text)
    );
    showMessages();
}

function getCalendarUrl(baseUrl) {
    if (window.currentDisplayOnly) {
        return baseUrl + (baseUrl.includes('?') ? '&' : '?') + 'display_only=' + encodeURIComponent(window.currentDisplayOnly);
    }
    return baseUrl;
}

// Extra calendar-events params: the visible range, so only the
// activities on screen are loaded, and scope=team while the
// Mine | Team toggle is on Team.
function calendarEventsQuery(start, end) {
    let query = '&start=' + encodeURIComponent(start) + '&end=' + encodeURIComponent(end);
    if (window.calendarScope === 'team') {
        query += '&scope=team';
        // Team members picked in the filter; none picked means everyone.
        selectedTeamMembers().forEach(function (id) {
            query += '&members[]=' + encodeURIComponent(id);
        });
    }
    return query;
}

// The Mine | Team toggle is rendered only for users the Team view
// shows more to; without it the calendar always shows Mine.
function setCalendarScope(scope) {
    const $buttons = $(".calendar-scope-btn");
    window.calendarScope = $buttons.length && scope === "team" ? "team" : "mine";
    $buttons.each(function () {
        const active = this.dataset.scope === window.calendarScope;
        $(this).toggleClass("bg-primary-600 text-white", active)
            .toggleClass("bg-primary-300 text-primary-600", !active);
    });
    // The members filter only applies to the Team view.
    $("#teamMembersFilter").toggleClass("hidden", window.calendarScope !== "team");
}

// Team members filter: the field opens the user picker modal (limited to
// the members the Team view offers) and the choice is applied from it;
// nothing chosen means all members.
window.teamMembersApplied = [];        // [{id, name}]

function selectedTeamMembers() {
    return window.teamMembersApplied.map(function (m) { return m.id; });
}

// The user picker reads and fills this select, so keep it on the applied members.
function syncTeamMembersSelect() {
    const $select = $("#teamMembersSelect").empty();
    window.teamMembersApplied.forEach(function (m) {
        $select.append(new Option(m.name || m.id, m.id, true, true));
    });
}

// The field shows the applied choice: all members, one name, or an
// avatar stack with the count.
function updateTeamMembersSummary() {
    const applied = window.teamMembersApplied;
    const $label = $("#teamMembersLabel");
    const $avatars = $("#teamMembersAvatars").empty();
    let text = $label.data("all");
    if (applied.length) {
        applied.slice(0, 2).forEach(function (m) {
            $avatars.append($("<span>").text(String(m.name || "?").slice(0, 1).toUpperCase()).addClass(
                "w-6 h-6 rounded-full bg-primary-100 text-primary-600 ring-2 ring-white text-[10px] font-semibold flex items-center justify-center"));
        });
        text = applied.length === 1 && applied[0].name ? applied[0].name : applied.length + " " + $label.data("selected");
    }
    $avatars.toggleClass("hidden", !applied.length);
    $("#teamMembersIcon").toggleClass("hidden", !!applied.length);
    $label.text(text).attr("title", text);
    $("#teamMembersClearFilter").toggleClass("hidden", !applied.length);
}

function initTeamMembersFilter() {
    if (!$("#teamMembersFilter").length) {
        return;
    }
    let saved = [];
    try {
        saved = JSON.parse(localStorage.getItem("calendarMembers") || "[]");
    } catch (e) {}
    // The server ignores ids the user can no longer pick.
    window.teamMembersApplied = saved.map(function (m) {
        return (m && typeof m === "object") ? { id: String(m.id), name: m.name || "" } : { id: String(m), name: "" };
    });
    syncTeamMembersSelect();
    updateTeamMembersSummary();
}

function updateEventStatus(eventId, newStatus) {
    fetch(CALENDAR_CONFIG.urls.markCompleted, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': CALENDAR_CONFIG.csrfToken
        },
        body: JSON.stringify({
            event_id: eventId,
            status: newStatus
        })
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ ok, data }) => {
        $('#reloadMainContent').click();
        if (ok && data.status === 'success') {
            if (window.hideDetailPopup) window.hideDetailPopup(); else $("#calendarPopup").addClass("hidden");
        } else {
            showCalendarMessage('error', data.message || 'Failed to update status');
        }
    })
    .catch(error => {
        $('#reloadMainContent').click();
        showCalendarMessage('error', 'Failed to update status');
    });
}

// HTMX helper functions for calendar events
function editEvent(eventId, editUrl) {
    if (window.hideDetailPopup) window.hideDetailPopup(); else $("#calendarPopup").addClass("hidden");
    htmx.ajax('GET', editUrl, {
        target: '#modalBox',
        swap: 'innerHTML',
    }).then(function() {
        if (typeof openModal === 'function') openModal();
    }).catch(function() {
        showCalendarMessage('error', CALENDAR_CONFIG.i18n.failedLoadEditForm);
    });
}

function deleteEvent(eventId, deleteUrl) {
    if (!deleteUrl || deleteUrl === 'None' || deleteUrl === '#') {
        showCalendarMessage('warning', 'Delete action is not available for this event.');
        return;
    }

    // Use HTMX for delete operations to match the expected flow
    htmx.ajax('POST', deleteUrl, {
        headers: {
            'X-CSRFToken': CALENDAR_CONFIG.csrfToken,
        },
        values: {
            'check_dependencies': 'true'
        },
        target: '#deleteModeBox',
        swap: 'innerHTML'
    }).then(() => {
        if (typeof openDeleteModeModal === 'function') {
            openDeleteModeModal();
        }
        if (window.hideDetailPopup) window.hideDetailPopup(); else $("#calendarPopup").addClass("hidden");
    }).catch(error => {
        showCalendarMessage('error', 'Failed to delete event');
    });
}

function showEventInfo(eventId, detailUrl) {
    if (!detailUrl || detailUrl === 'None' || detailUrl === '#') {
        showCalendarMessage('warning', 'Detail view is not available for this event.');
        return;
    }

    htmx.ajax('GET', detailUrl, {
        target: '#mainContent',
        swap: 'outerHTML',
        select: '#mainContent',
        pushUrl: true,
        headers: {
            'X-CSRFToken': CALENDAR_CONFIG.csrfToken
        }
    }).then(() => {
        if (window.hideDetailPopup) window.hideDetailPopup(); else $("#calendarPopup").addClass("hidden");
    }).catch(error => {
        showCalendarMessage('error', 'Failed to load event details');
    });
}

function createNewActivity(clickedDate, isAllDay) {
    const hiddenBtn = document.getElementById('newActivityBtn');
    const data = {
        start_date_time: clickedDate,
        view: 'calendar'
    };
    // The all-day row of the day/week view: open the form with All Day on.
    if (isAllDay) {
        data.is_all_day = 'on';
    }
    hiddenBtn.setAttribute('hx-vals', JSON.stringify(data));
    hiddenBtn.click();
    if (window.hideDetailPopup) window.hideDetailPopup(); else $("#calendarPopup").addClass("hidden");
}

function markDateUnavailable(clickedDate) {
    const hiddenBtn = document.getElementById('markUnavailableBtn');
    const data = {
        start_date_time: clickedDate,
    };
    hiddenBtn.setAttribute('hx-vals', JSON.stringify(data));
    hiddenBtn.click();
    if (window.hideDetailPopup) window.hideDetailPopup(); else $("#calendarPopup").addClass("hidden");
}

document.addEventListener('htmx:afterRequest', function(event) {
    const elId = event.detail.elt.id;
    if (event.detail.xhr.status === 200 && (elId === 'markUnavailableBtn' || elId === 'newActivityBtn')) {
        if (typeof openModal === 'function') {
            openModal();
        }
    }
});



// HTML escaping function to prevent XSS attacks
function escapeHtml(text) {
    if (text == null || text === undefined) {
        return '';
    }
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, function(m) { return map[m]; });
}

// JavaScript string escaping for use in onclick handlers and similar contexts
function escapeJsString(text) {
    if (text == null || text === undefined) {
        return '';
    }
    return String(text)
        .replace(/\\/g, '\\\\')  // Escape backslashes first
        .replace(/'/g, "\\'")     // Escape single quotes
        .replace(/"/g, '\\"')     // Escape double quotes
        .replace(/\n/g, '\\n')    // Escape newlines
        .replace(/\r/g, '\\r')    // Escape carriage returns
        .replace(/\t/g, '\\t');   // Escape tabs
}

function initCalendar() {

    if (window.calendarInitialized) {
        return;
    }
    window.calendarInitialized = true;

    const calendarEl = $("#calendarGrid")[0];
    if (!calendarEl) {
        window.calendarInitialized = false;
        return;
    }
    const titleEl = document.getElementById("calendarTitle");

    // Restore saved view so initialView is always valid (undefined breaks title)
    window.currentView = window.currentView || localStorage.getItem("calendarView") || "dayGridMonth";
    const popup = $("#calendarPopup")[0];
    const popupContent = $("#popupContent")[0];

    const today = new Date();
    // Reloads (of this section or the whole page) rebuild the calendar, so reopen on the
    // date last viewed instead of jumping back to today.
    let savedDate = window.calendarViewDate;
    if (!savedDate) {
        try {
            savedDate = localStorage.getItem("calendarViewDate");
        } catch (e) {}
    }
    const currentDate = savedDate && !isNaN(new Date(savedDate)) ? savedDate : today.toISOString().split('T')[0];

    // Restore the scope first: the calendar loads its first events
    // while it is being created.
    let savedScope = null;
    try {
        savedScope = localStorage.getItem("calendarScope");
    } catch (e) {}
    initTeamMembersFilter();
    setCalendarScope(savedScope);

    const calendar = new FullCalendar.Calendar(calendarEl, {
        height: "100%",
        expandRows: true,
        slotMinTime: "00:00:00",
        slotMaxTime: "24:00:00",
        scrollTime: "08:00:00",
        slotDuration: "00:30:00",
        headerToolbar: false,
        initialView: window.currentView,
        initialDate: currentDate,
        navLinks: true,
        // Clicking a date / week number opens the same views as the Day and Week tabs.
        navLinkDayClick: "timeGridDay",
        navLinkWeekClick: "timeGridWeek",
        editable: true,
        eventDurationEditable: false,
        selectable: true,
        nowIndicator: true,
        dayMaxEvents: 2,
        /* Show only the event title in month/week cells, not "8:14am Title" */
        displayEventTime: false,
        // Stable built-in sorting (avoid custom comparator runtime issues).
        eventOrderStrict: true,
        // Prefer shorter all-day items first so single-day markers don't get buried by long spans.
        eventOrder: "start,duration,allDay,title",
        allDayText: CALENDAR_CONFIG.i18n.allDay,


        views: {
            timeGridDay: {
                dayHeaderFormat: {
                    weekday: 'long',
                    day: 'numeric'
                }
            },
            timeGridWeek: {
                dayHeaderFormat: {
                    weekday: 'short',
                    day: 'numeric'
                }
            },
            multiMonthYear: {
                type: "multiMonth",
                duration: { years: 1 },
                buttonText: "Year",
            },
        },

        slotLabelFormat: {
            hour: 'numeric',
            minute: '2-digit',
            omitZeroMinute: false,
            meridiem: 'short'
        },

        events: function(fetchInfo, successCallback, failureCallback) {
            const selectedTypes = Array.from(document.querySelectorAll('.calendar-checkbox:checked'))
                .map(checkbox => checkbox.dataset.calendarType);

            let url = CALENDAR_CONFIG.urls.getEvents + '?calendar_types[]=' + selectedTypes.join('&calendar_types[]=');
            if (window.currentDisplayOnly) {
                url += '&display_only=' + encodeURIComponent(window.currentDisplayOnly);
            }
            url += calendarEventsQuery(fetchInfo.startStr, fetchInfo.endStr);

            fetch(url, {
                headers: { 'X-CSRFToken': CALENDAR_CONFIG.csrfToken,
                        'X-Requested-With': 'XMLHttpRequest' },
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    successCallback(filterByStatus(data.events));
                } else {
                    failureCallback(new Error(data.message));
                }
            })
            .catch(error => failureCallback(error));
        },
        datesSet: function () {
            if (titleEl && calendar.view && calendar.view.title) {
                titleEl.textContent = calendar.view.title;
            }
            window.currentView = calendar.view.type;
            localStorage.setItem('calendarView', window.currentView);
            window.calendarViewDate = calendar.getDate().toISOString();
            try {
                localStorage.setItem("calendarViewDate", window.calendarViewDate);
            } catch (e) {}
            syncActiveTabToView();
        },
        eventTimeFormat: {
            hour: "numeric",
            minute: "2-digit",
            meridiem: "short",
        },
        eventClick: function (info) {
            info.jsEvent.preventDefault();
            const event = info.event;
            const rect = info.el.getBoundingClientRect();
            const containerRect = calendarEl.getBoundingClientRect();

            let content;
            let icons;

            if (event.extendedProps.calendarType === 'unavailability') {
                // Content for unavailability events
                const safeTitle = escapeHtml(event.title);
                const safeDescription = escapeHtml(event.extendedProps.description || 'No reason provided');
                const safeEventId = escapeHtml(event.id);
                const safeEventUrl = escapeHtml(event.url || '');
                const safeDeleteUrl = escapeHtml(event.extendedProps.deleteUrl || '');

                content = `
                        <div class="flex flex-col gap-2 text-sm">
                            <h5 class="font-semibold mb-1 bg-primary-300 text-primary-600">${safeTitle}</h5>
                            <div class="grid grid-cols-[90px_10px_minmax(0,1fr)] gap-y-1">
                                <div class="font-bold">${CALENDAR_CONFIG.i18n.reason}</div>
                                <div>:</div>
                                <div>${safeDescription}</div>
                                <div class="font-bold">${CALENDAR_CONFIG.i18n.startDate}</div>
                                <div>:</div>
                                <div>${event.extendedProps.start_display || event.start?.toLocaleString()}</div>
                                <div class="font-bold">${CALENDAR_CONFIG.i18n.endDate}</div>
                                <div>:</div>
                                <div>${event.extendedProps.end_display || event.end?.toLocaleString() || 'N/A'}</div>
                            </div>
                        </div>
                    `;
                // Icons for unavailability (only Edit and Delete)
                const safeEventIdJs = escapeJsString(event.id);
                const safeEventUrlJs = escapeJsString(event.url || '');
                const safeDeleteUrlJs = escapeJsString(event.extendedProps.deleteUrl || '');

                icons = `
                        <div class="flex tablebtn mt-3">
                        ${ window.hasUnavailabilityChangeOwnPerm ? `
                            <button type="button"
                                onclick="editEvent('${safeEventIdJs}', '${safeEventUrlJs}')"
                                class="w-10 h-7 bg-dark-25 flex-1 flex justify-center border-r border-r-[white] hover:bg-dark-50 transition duration-300 items-center"
                                title="${CALENDAR_CONFIG.i18n.edit}"
                                aria-label="${CALENDAR_CONFIG.i18n.edit}"
                                data-tooltip-placement="top"
                            >
                                <i class="fas fa-edit text-color-600" style="font-size:15px"></i>
                            </button>
                            ` : ''}
                            ${window.hasUnavailabilityDeletePerm ? `
                            <button type="button"
                                onclick="deleteEvent('${safeEventIdJs}', '${safeDeleteUrlJs}')"
                                class="w-10 h-7 bg-dark-25 flex-1 flex justify-center border-r border-r-[white] hover:bg-dark-50 transition duration-300 items-center"
                                title="${CALENDAR_CONFIG.i18n.delete}"
                                aria-label="${CALENDAR_CONFIG.i18n.delete}"
                                data-tooltip-placement="top"
                            >
                                <img src="${CALENDAR_CONFIG.icons.delete}" alt="" width="15" height="15" />
                            </button>
                            ` : '' }
                        </div>
                    `;
            } else {
                // Content for other activity types
                const subject = event.extendedProps.subject || "No subject";
                const status = event.extendedProps.status;
                const statusDisplay = event.extendedProps.status_display || status || "";
                const activityTypeDisplay = event.extendedProps.activity_type_display || event.extendedProps.activityType || event.extendedProps.calendarType || "";
                // Custom calendar events carry the real type in activityType.
                const activityType = event.extendedProps.activityType || event.extendedProps.calendarType || "";
                const isTask = activityType === "task";
                const dueDateDisplay = event.extendedProps.due_date_display || (event.extendedProps.dueDate ? new Date(event.extendedProps.dueDate).toLocaleString() : "—");
                const startDisplay = event.extendedProps.start_display || (event.start ? event.start.toLocaleString() : "—");
                const endDisplay = event.extendedProps.end_display || (event.end ? event.end.toLocaleString() : "—");
                const assignedToList = event.extendedProps.assignedTo || [];
                const assigneeNames = assignedToList.map(user =>
                    [user.first_name, user.last_name].filter(Boolean).join(" ") || user.email || ""
                ).filter(Boolean);
                const assigneesUrl = escapeHtml(CALENDAR_CONFIG.urls.activityAssignees.replace('/0/', `/${event.extendedProps.activityId || event.id}/`));
                const clientName = assigneeNames.length === 1 ? assigneeNames[0] : "Unassigned";

                // Escape all user inputs to prevent XSS
                const safeTitle = escapeHtml(event.title);
                const safeSubject = escapeHtml(subject);
                const safeClientName = escapeHtml(clientName);
                const safeStatus = escapeHtml(statusDisplay);
                const safeActivityType = escapeHtml(activityTypeDisplay);
                const safeEventId = escapeHtml(event.id);
                const safeEventUrl = escapeHtml(event.url || '');
                const safeDeleteUrl = escapeHtml(event.extendedProps.deleteUrl || '');
                const safeDetailUrl = escapeHtml(event.extendedProps.detailUrl || '');
                // Sent only in the Team view: what the user may do on this record
                const canChange = event.extendedProps.canChange !== false;
                const canDelete = event.extendedProps.canDelete !== false;

                const dateRows = isTask
                    ? `<div class="font-bold">${CALENDAR_CONFIG.i18n.dueDate}</div>
                                <div>:</div>
                                <div>${dueDateDisplay}</div>`
                    : `<div class="font-bold">${CALENDAR_CONFIG.i18n.startDate}</div>
                                <div>:</div>
                                <div>${startDisplay}</div>
                                <div class="font-bold">${CALENDAR_CONFIG.i18n.endDate}</div>
                                <div>:</div>
                                <div>${endDisplay}</div>`;

                content = `
                        <div class="flex flex-col gap-2 text-sm">
                            <h5 class="font-semibold mb-1 bg-primary-300 text-primary-600">${safeTitle}</h5>
                            <div class="grid grid-cols-[90px_10px_minmax(0,1fr)] gap-y-1">
                                <div class="font-bold">${CALENDAR_CONFIG.i18n.subject}</div>
                                <div>:</div>
                                <div>${safeSubject}</div>
                                ${dateRows}
                                <div class="font-bold">${CALENDAR_CONFIG.i18n.assignedTo}</div>
                                <div>:</div>
                                <div>${assigneeNames.length > 1 ? `
                                    <button type="button"
                                        hx-get="${assigneesUrl}"
                                        hx-target="#modalBox"
                                        hx-swap="innerHTML"
                                        hx-on::after-request="hideDetailPopup(); openModal()"
                                        class="inline-flex items-center text-xs font-semibold text-primary-600 bg-primary-100 hover:bg-primary-200 px-2.5 py-0.5 rounded-full transition duration-300"
                                        title="${CALENDAR_CONFIG.i18n.viewAllAssignees}"
                                    >${assigneeNames.length} ${CALENDAR_CONFIG.i18n.users}</button>` : safeClientName}</div>
                                <div class="font-bold">${CALENDAR_CONFIG.i18n.status}</div>
                                <div>:</div>
                                <div>${safeStatus}</div>
                            </div>
                            ${status != "completed" && window.statusFieldPermission === "readwrite" && canChange ? `
                            <button type="button"
                                onclick="updateEventStatus('${escapeJsString(event.extendedProps.activityId || event.id)}', 'completed')"
                                class="w-full mt-2 py-1.5 px-3 text-xs font-medium rounded-md bg-primary-100 text-primary-600 border border-primary-200 transition duration-300 flex items-center justify-center gap-1.5"
                            >
                                <i class="fas fa-check"></i>
                                <span>${CALENDAR_CONFIG.i18n.markAsComplete}</span>
                            </button>
                            ` : ""}
                        </div>
                    `;
                // Icons for other activities (Edit, Delete, Info)
                const safeEventIdJs = escapeJsString(event.id);
                const safeEventUrlJs = escapeJsString(event.url || '');
                const safeDeleteUrlJs = escapeJsString(event.extendedProps.deleteUrl || '');
                const safeDetailUrlJs = escapeJsString(event.extendedProps.detailUrl || '');
                // Set only when the user may open the related record
                const safeRelatedUrl = escapeHtml(event.extendedProps.relatedUrl || '');

                icons = `
                        <div class="flex tablebtn mt-3">
                        ${window.hasActivityChangeOwnPerm && canChange ? `
                            <button type="button"
                                onclick="editEvent('${safeEventIdJs}', '${safeEventUrlJs}')"
                                class="w-10 h-7 bg-dark-25 flex-1 flex justify-center border-r border-r-[white] hover:bg-dark-50 transition duration-300 items-center"
                                title="${CALENDAR_CONFIG.i18n.edit}"
                                aria-label="${CALENDAR_CONFIG.i18n.edit}"
                                data-tooltip-placement="top"
                            >
                                <i class="fas fa-edit text-color-600"></i>
                            </button>
                            ` : '' }
                            ${window.hasActivityDeletePerm && canDelete ? `
                            <button type="button"
                                onclick="deleteEvent('${safeEventIdJs}', '${safeDeleteUrlJs}')"
                                class="w-10 h-7 bg-dark-25 flex-1 flex justify-center border-r border-r-[white] hover:bg-dark-50 transition duration-300 items-center"
                                title="${CALENDAR_CONFIG.i18n.delete}"
                                aria-label="${CALENDAR_CONFIG.i18n.delete}"
                                data-tooltip-placement="top"
                            >
                                <i class="fas fa-trash text-color-600"></i>
                            </button>
                            ` : '' }
                            ${window.hasActivityViewOwnPerm ? `
                            <button type="button"
                                onclick="showEventInfo('${safeEventIdJs}', '${safeDetailUrlJs}')"
                                class="w-10 h-7 bg-dark-25 flex-1 flex justify-center border-r border-r-[white] hover:bg-dark-50 transition duration-300 items-center"
                                title="${CALENDAR_CONFIG.i18n.info}"
                                aria-label="${CALENDAR_CONFIG.i18n.info}"
                                data-tooltip-placement="top"
                            >
                                <i class="fas fa-info-circle text-color-600"></i>
                            </button>
                            ` :  '' }
                            ${safeRelatedUrl ? `
                            <a
                                href="${safeRelatedUrl}"
                                hx-get="${safeRelatedUrl}"
                                hx-target="#mainContent"
                                hx-select-oob="#sideMenuContainer"
                                hx-swap="outerHTML"
                                hx-push-url="true"
                                hx-select="#mainContent"
                                class="w-10 h-7 bg-dark-25 flex-1 flex justify-center border-r border-r-[white] hover:bg-dark-50 transition duration-300 items-center"
                                title="${CALENDAR_CONFIG.i18n.openRelatedRecord}"
                                aria-label="${CALENDAR_CONFIG.i18n.openRelatedRecord}"
                                data-tooltip-placement="top"
                            >
                                <i class="fas fa-external-link-alt text-color-600"></i>
                            </a>
                            ` : '' }
                        </div>
                    `;
            }

            content += icons;

            // The popup opens at the event's top-left. A tall time-grid event
            // (e.g. 00:00-23:59) can start above the visible, scrolled part of the
            // grid, so open at the click instead of off-screen.
            const scrollerEl = info.el.closest(".fc-scroller");
            const visibleTop = scrollerEl
                ? Math.max(scrollerEl.getBoundingClientRect().top, containerRect.top)
                : containerRect.top;
            const clipped = rect.top < visibleTop;
            showPopup(
                content,
                clipped ? info.jsEvent.clientX - containerRect.left : rect.left - containerRect.left,
                (clipped ? info.jsEvent.clientY : rect.top) - containerRect.top
            );
        },
        ...( (window.hasActivityCreatePerm || window.hasUnavailabilityCreatePerm) ? {
            dateClick: function (info) {

                const containerEl = document.getElementById('calendar-container') || calendarEl;
                const containerRect = containerEl.getBoundingClientRect();
                const x = info.jsEvent.clientX - containerRect.left;
                const y = info.jsEvent.clientY - containerRect.top;
                const clickedDate = info.dateStr;
                const safeClickedDate = escapeJsString(clickedDate);
                // A click on the all-day row of the day/week view (month cells are
                // date-only too, but those keep the timed default).
                const fromAllDayRow = info.allDay && info.view.type.indexOf("timeGrid") === 0;

                let content = '<div class="flex flex-col gap-2">';

                if (window.hasActivityCreatePerm) {
                    content += `
                            <button
                                onclick="createNewActivity('${safeClickedDate}', ${fromAllDayRow})"
                                class="text-blue-600 text-sm"
                            >
                                ${CALENDAR_CONFIG.i18n.newActivity}
                            </button>
                        `;
                }

                if (window.hasUnavailabilityCreatePerm) {
                    content += `
                            <button
                                onclick="markDateUnavailable('${safeClickedDate}')"
                                class="text-red-600 text-sm"
                            >
                                ${CALENDAR_CONFIG.i18n.markAsUnavailable}
                            </button>
                        `;
                }

                content += '</div>';

                showPopup(content, x, y);
            },
        } : {} ),
        eventDidMount: function (info) {
            applyEventColor(info.event, info.el);
        },
    });

    // Status checkboxes (shown in "Status" mode): the bucket an event
    // belongs to, and which buckets are switched off.
    function statusKeyOf(status) {
        return status === "completed" ? "status_completed" : "status_pending";
    }

    function hiddenStatusKeys() {
        return $(".status-checkbox").filter(function () { return !this.checked; })
            .map(function () { return this.dataset.statusColor; }).get();
    }

    // Drop the events of unchecked statuses; unavailability has no status.
    function filterByStatus(events) {
        const hidden = window.calendarColorBy === "status" ? hiddenStatusKeys() : [];
        if (!hidden.length) {
            return events;
        }
        return events.filter(function (e) {
            return !e.status || e.calendarType === "unavailability"
                || hidden.indexOf(statusKeyOf(e.status)) === -1;
        });
    }

    // The checkbox takes its status color, filled when checked (as the type ones do).
    function paintStatusCheckboxes() {
        $(".status-checkbox").each(function () {
            const picker = document.querySelector(`.status-color-picker[data-status-color="${this.dataset.statusColor}"]`);
            const color = picker ? picker.value : "";
            this.style.setProperty("border-color", color);
            this.style.setProperty("color", color);
            this.style.setProperty("accent-color", color);
            this.style.setProperty("background-color", this.checked ? color : "transparent", "important");
        });
    }

    function saveStatusFilter() {
        try {
            localStorage.setItem("calendarStatusHidden", JSON.stringify(hiddenStatusKeys()));
        } catch (e) {}
    }

    // Activities (standard types and custom calendars) carry a status, so
    // they follow the status colors; unavailability has none and always
    // keeps its calendar color.
    function statusColorFor(event) {
        const calendarType = String(event.extendedProps.calendarType || "");
        const status = event.extendedProps.status;
        if (window.calendarColorBy !== "status" || !status
            || calendarType === "unavailability") {
            return null;
        }
        const key = status === "completed" ? "status_completed" : "status_pending";
        const picker = document.querySelector(`.status-color-picker[data-status-color="${key}"]`);
        return picker ? picker.value : null;
    }

    // Text color picked for an event: per status in "Status" mode,
    // otherwise per calendar type. Falls back to the event's own
    // textColor (white) so nothing changes until a color is chosen.
    function textColorFor(event, statusColor) {
        const calendarType = event.extendedProps.calendarType;
        let picker = null;
        if (statusColor) {
            const key = event.extendedProps.status === "completed" ? "status_completed" : "status_pending";
            picker = document.querySelector(`.status-text-color-picker[data-status-color="${key}"]`);
        } else {
            picker = document.querySelector(`.calendar-text-color-picker[data-calendar-type="${calendarType}"]`);
        }
        return (picker && picker.value) || event.textColor || "#FFFFFF";
    }

    function applyEventColor(event, el) {
        const calendarType = event.extendedProps.calendarType;
        const checkbox = document.querySelector(`.calendar-checkbox[data-calendar-type="${calendarType}"]`);
        const statusColor = statusColorFor(event);
        const color = statusColor
            || (checkbox && (checkbox.style.borderColor || event.extendedProps.backgroundColor));
        if (!color) {
            return;
        }
        el.style.backgroundColor = color;
        el.style.borderColor = color;
        // Timed events in month view render as a dot, not a filled bar.
        const dot = el.querySelector(".fc-daygrid-event-dot");
        if (dot && statusColor) {
            dot.style.borderColor = statusColor;
        }
        // Text color (calendar.css sets the title white, so set it inline on the text nodes too).
        const textColor = textColorFor(event, statusColor);
        el.style.color = textColor;
        el.querySelectorAll(".fc-event-main, .fc-event-main-frame, .fc-event-time, .fc-event-title-container, .fc-event-title")
            .forEach(function (node) { node.style.color = textColor; });
    }

    function setColorBy(mode) {
        window.calendarColorBy = mode === "status" ? "status" : "type";
        $(".color-by-btn").each(function () {
            const active = this.dataset.colorBy === window.calendarColorBy;
            $(this).toggleClass("bg-primary-600 text-white", active)
                .toggleClass("bg-primary-300 text-primary-600", !active);
        });
        $("#colorByTypePanel").toggleClass("hidden", window.calendarColorBy === "status");
        $("#colorByStatusPanel").toggleClass("hidden", window.calendarColorBy !== "status");
    }

    try {
        const hidden = JSON.parse(localStorage.getItem("calendarStatusHidden") || "[]");
        $(".status-checkbox").each(function () {
            this.checked = hidden.indexOf(this.dataset.statusColor) === -1;
        });
    } catch (e) {}
    paintStatusCheckboxes();

    let savedColorBy = null;
    try {
        savedColorBy = localStorage.getItem("calendarColorBy");
    } catch (e) {}
    setColorBy(savedColorBy);

    $(".color-by-btn").on("click", function () {
        setColorBy(this.dataset.colorBy);
        try {
            localStorage.setItem("calendarColorBy", window.calendarColorBy);
        } catch (e) {}
        // Refetch so every event remounts and eventDidMount picks the new mode.
        calendar.refetchEvents();
    });

    function applyTeamMembers(members) {
        window.teamMembersApplied = members;
        try {
            localStorage.setItem("calendarMembers", JSON.stringify(window.teamMembersApplied));
        } catch (e) {}
        syncTeamMembersSelect();
        updateTeamMembersSummary();
        if (window.calendarScope === "team") {
            calendar.refetchEvents();
        }
    }
    // The user picker fills this select and fires change when Select is clicked.
    $("#teamMembersSelect").on("change", function () {
        applyTeamMembers($(this).find("option:selected").map(function () {
            return { id: String(this.value), name: $(this).text() };
        }).get());
    });
    $("#teamMembersClearFilter").on("click", function () {
        applyTeamMembers([]);
    });

    $(".calendar-scope-btn").on("click", function () {
        setCalendarScope(this.dataset.scope);
        try {
            localStorage.setItem("calendarScope", window.calendarScope);
        } catch (e) {}
        calendar.refetchEvents();
    });

    $(".status-checkbox").on("change", function () {
        paintStatusCheckboxes();
        saveStatusFilter();
        calendar.refetchEvents();
    });
    // Display This Only: just this status stays checked.
    $(".status-display-only").on("click", function () {
        const key = this.dataset.statusColor;
        $(".status-checkbox").each(function () {
            this.checked = this.dataset.statusColor === key;
        });
        paintStatusCheckboxes();
        saveStatusFilter();
        calendar.refetchEvents();
    });

    $(".status-color-picker").on("change", function () {
        paintStatusCheckboxes();
        calendar.refetchEvents();
        $.ajax({
            url: CALENDAR_CONFIG.urls.savePreferences,
            method: 'POST',
            headers: {
                'X-CSRFToken': CALENDAR_CONFIG.csrfToken,
            },
            contentType: 'application/json',
            data: JSON.stringify({
                calendar_type: this.dataset.statusColor,
                color: this.value,
            }),
            success: function (data) {
                if (data.status === 'success') {
                    $('#reloadMainContent').click();
                }
            },
            error: function (error) {
                console.error('Error saving status color:', error);
            }
        });
    });

    // Text color pickers (per calendar type, and per status in "Status" mode)
    $(".calendar-text-color-picker, .status-text-color-picker").on("change", function () {
        calendar.refetchEvents();
        $.ajax({
            url: CALENDAR_CONFIG.urls.savePreferences,
            method: 'POST',
            headers: {
                'X-CSRFToken': CALENDAR_CONFIG.csrfToken,
            },
            contentType: 'application/json',
            data: JSON.stringify({
                calendar_type: this.dataset.calendarType || this.dataset.statusColor,
                text_color: this.value,
            }),
            success: function (data) {
                if (data.status === 'success') {
                    // Same as the background color picker: reload so the "saved" message shows now.
                    $('#reloadMainContent').click();
                }
            },
            error: function (error) {
                console.error('Error saving text color:', error);
            }
        });
    });

    calendar.render();
    window.calendarInstance = calendar;
    // FullCalendar only re-measures on window resize, so collapsing or
    // expanding the side menu left the grid at its old width until a
    // reload. Re-measure whenever the calendar's own box changes size.
    if (window.calendarResizeObserver) {
        window.calendarResizeObserver.disconnect();
    }
    if (window.ResizeObserver) {
        let resizeFrame = null;
        window.calendarResizeObserver = new ResizeObserver(function () {
            cancelAnimationFrame(resizeFrame);
            resizeFrame = requestAnimationFrame(function () {
                calendar.updateSize();
            });
        });
        window.calendarResizeObserver.observe(calendarEl.parentElement);
    }
    // datesSet can run async; set title immediately so range always shows
    if (titleEl && calendar.view && calendar.view.title) {
        titleEl.textContent = calendar.view.title;
    }
    syncMasterCheckbox();

    // Toolbar buttons
    $("#prevBtn").on("click", () => calendar.prev());
    $("#nextBtn").on("click", () => calendar.next());
    $("#todayBtn").on("click", () => calendar.today());

    // Keep the Day/Week/Month/Year tabs in step with the view shown, however it was reached
    // (a tab, a date link, the saved view).
    function syncActiveTabToView() {
        const tabs = {
            timeGridDay: "dayView",
            timeGridWeek: "weekView",
            dayGridMonth: "monthView",
            multiMonthYear: "yearView",
        };
        const id = calendar.view && tabs[calendar.view.type];
        if (id) setActiveTab(id);
    }

    function setActiveTab(activeId) {
        $(".tab-btn").each(function() {
            const $btn = $(this);
            if ($btn.attr("id") === activeId) {
                $btn.addClass("bg-primary-600 text-white")
                    .removeClass("bg-primary-300 text-primary-600");
            } else {
                $btn.addClass("bg-primary-300 text-primary-600")
                    .removeClass("bg-primary-600 text-white");
            }
        });
    }

    $("#dayView").on("click", () => {
        calendar.changeView("timeGridDay");
        window.currentView = "timeGridDay";
        localStorage.setItem('calendarView', window.currentView);
        setActiveTab("dayView");
    });

    $("#weekView").on("click", () => {
        calendar.changeView("timeGridWeek");
        window.currentView = "timeGridWeek";
        localStorage.setItem('calendarView', window.currentView);
        setActiveTab("weekView");
    });

    $("#monthView").on("click", () => {
        calendar.changeView("dayGridMonth");
        window.currentView = "dayGridMonth";
        localStorage.setItem('calendarView', window.currentView);
        setActiveTab("monthView");
    });

    $("#yearView").on("click", () => {
        calendar.changeView("multiMonthYear");
        window.currentView = "multiMonthYear";
        localStorage.setItem('calendarView', window.currentView);
        setActiveTab("yearView");
    });

    setActiveTab(
        window.currentView === "timeGridDay" ? "dayView" :
        window.currentView === "timeGridWeek" ? "weekView" :
        window.currentView === "multiMonthYear" ? "yearView" : "monthView"
    );


    // Color picker functionality
    $('.calendar-color-picker').on('change', function () {
        const calendarType = $(this).data('calendar-type');
        const color = this.value;
        const checkbox = $(`.calendar-checkbox[data-calendar-type="${calendarType}"]`)[0];

        // Update checkbox styles
        checkbox.style.borderColor = color;
        checkbox.style.accentColor = color;
        checkbox.style.color = color;
        if (checkbox.checked) {
            checkbox.style.setProperty('background-color', color, 'important');
        }

        // Get currently selected calendar types
        const selectedTypes = Array.from(document.querySelectorAll('.calendar-checkbox:checked'))
            .map(checkbox => checkbox.dataset.calendarType);

        // Save color preference to backend
        $.ajax({
            url: CALENDAR_CONFIG.urls.savePreferences,
            method: 'POST',
            headers: {
                'X-CSRFToken': CALENDAR_CONFIG.csrfToken,
            },
            contentType: 'application/json',
            data: JSON.stringify({
                calendar_type: calendarType,
                color: color,
                calendar_types: selectedTypes
            }),
            success: function (data) {
                if (data.status === 'success') {
                    $('#reloadMainContent').click();
                    calendar.refetchEvents();
                    calendar.render();
                } else {
                    console.error('Error saving color:', data.message);
                }
            },
            error: function (error) {
                console.error('Error:', error);
            }
        });
    });

    // Update checkbox background and refresh events when checked/unchecked
    $('.calendar-checkbox').on('change', function () {
        this.style.accentColor = this.style.borderColor;
        this.style.color = this.style.borderColor;
        if (this.checked) {
            this.style.setProperty('background-color', this.style.borderColor, 'important');
        } else {
            this.style.setProperty('background-color', 'transparent', 'important');
        }
        syncMasterCheckbox();

        const selectedTypes = Array.from(document.querySelectorAll('.calendar-checkbox:checked'))
            .map(checkbox => checkbox.dataset.calendarType);

        fetch(CALENDAR_CONFIG.urls.savePreferences, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CALENDAR_CONFIG.csrfToken,
            },
            body: JSON.stringify({ calendar_types: selectedTypes }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const url = CALENDAR_CONFIG.urls.getEvents + '?' + selectedTypes.map(type => `calendar_types[]=${encodeURIComponent(type)}`).join('&') +
                    calendarEventsQuery(calendar.view.activeStart.toISOString(), calendar.view.activeEnd.toISOString());
                fetch(url, {
                    headers: { 'X-CSRFToken': CALENDAR_CONFIG.csrfToken,
                                'X-Requested-With': 'XMLHttpRequest' },
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        calendar.getEventSources().forEach(source => source.remove());
                        calendar.addEventSource(data.events);

                        const calendarUrl = CALENDAR_CONFIG.urls.calendarView;
                        const url = new URL(window.location.href);
                        url.searchParams.delete('display_only');
                        if (window.history.replaceState) {
                            window.history.replaceState(null, '', url.toString());
                        }
                        window.currentDisplayOnly = '';
                        htmx.ajax('GET', calendarUrl, { target: '#mainContent', swap: 'outerHTML', select: '#mainContent' });
                    } else {
                        console.error('Error fetching events:', data.message);
                    }
                })
                .catch(error => console.error('Fetch error:', error));
            } else {
                console.error('Error saving preferences:', data.message);
            }
        })
        .catch(error => console.error('Fetch error:', error));
    });

    // Master checkbox logic for "My Calendars"
    $('#masterCheckbox').on('change', function() {
        const isChecked = this.checked;
        const allCheckboxes = $('.calendar-checkbox');

        allCheckboxes.each(function() {
            this.checked = isChecked;
            this.style.accentColor = this.style.borderColor;
            this.style.color = this.style.borderColor;
            if (isChecked) {
                this.style.setProperty('background-color', this.style.borderColor, 'important');
            } else {
                this.style.setProperty('background-color', 'transparent', 'important');
            }
        });

        const selectedTypes = isChecked ?
            allCheckboxes.map(function() { return this.dataset.calendarType; }).get() :
            [];

        // Always send the request, even with empty array
        $.ajax({
            url: CALENDAR_CONFIG.urls.savePreferences,
            method: 'POST',
            headers: {
                'X-CSRFToken': CALENDAR_CONFIG.csrfToken,
            },
            contentType: 'application/json',
            data: JSON.stringify({
                calendar_types: selectedTypes
            }),
            success: function(data) {
                if (data.status === 'success') {
                    calendar.getEventSources().forEach(source => source.remove());

                    if (selectedTypes.length > 0) {
                        const url = CALENDAR_CONFIG.urls.getEvents + '?' +
                            selectedTypes.map(type => `calendar_types[]=${encodeURIComponent(type)}`).join('&') +
                            calendarEventsQuery(calendar.view.activeStart.toISOString(), calendar.view.activeEnd.toISOString());

                        $.ajax({
                            url: url,
                            headers: { 'X-CSRFToken': CALENDAR_CONFIG.csrfToken,
                                        'X-Requested-With': 'XMLHttpRequest' },

                            success: function(data) {
                                if (data.status === 'success') {
                                    calendar.addEventSource(data.events);
                                    // Reload without display_only; clear URL so checkboxes stay in sync
                                    const calendarUrl = CALENDAR_CONFIG.urls.calendarView;
                                    const url = new URL(window.location.href);
                                    url.searchParams.delete('display_only');
                                    if (window.history.replaceState) {
                                        window.history.replaceState(null, '', url.toString());
                                    }
                                    window.currentDisplayOnly = '';
                                    htmx.ajax('GET', calendarUrl, { target: '#mainContent', swap: 'outerHTML', select: '#mainContent' });
                                } else {
                                    console.error('Error fetching events:', data.message);
                                }
                            },
                            error: function(error) {
                                console.error('Fetch error:', error);
                            }
                        });
                    }
                } else {
                    console.error('Error saving preferences:', data.message);
                }
            },
            error: function(error) {
                console.error('Error:', error);
            }
        });
    });

    function syncMasterCheckbox() {
        const masterCheckbox = $('#masterCheckbox')[0];
        if (!masterCheckbox) {
            return;
            }
        const calendarCheckboxes = $('.calendar-checkbox');
        const checkedCount = calendarCheckboxes.filter(':checked').length;
        const totalCount = calendarCheckboxes.length;

        if (checkedCount === 0) {
            masterCheckbox.checked = false;
            masterCheckbox.indeterminate = false;
        } else if (checkedCount === totalCount) {
            masterCheckbox.checked = true;
            masterCheckbox.indeterminate = false;
        } else {
            masterCheckbox.checked = false;
            masterCheckbox.indeterminate = true;
        }
    }

    // Sync checkbox state with "Display This Only" after HTMX settle.
    $(document).on('htmx:afterSettle', function() {
        const displayOnly = new URLSearchParams(window.location.search).get('display_only') || '';
        if (displayOnly) {
            $('.calendar-checkbox').each(function() {
                const type = this.dataset.calendarType;
                this.checked = (type === displayOnly);
                this.style.accentColor = this.style.borderColor;
                this.style.color = this.style.borderColor;
                if (this.checked) {
                    this.style.setProperty('background-color', this.style.borderColor, 'important');
                } else {
                    this.style.setProperty('background-color', 'transparent', 'important');
                }
            });
            calendar.refetchEvents();
        }
        syncMasterCheckbox();
    });

    // Popup functions
    function showPopup(content, x, y) {
        popupContent.innerHTML = content;
        // Activate hx-* links in the popup (e.g. Open Related Record)
        htmx.process(popupContent);
        popup.style.left = `${x}px`;
        popup.style.top = `${y}px`;
        $(popup).removeClass("hidden").addClass("fc-popover");
        // Keep the whole popup (down to its action buttons) inside the
        // visible window: an event near the bottom or right edge opens
        // it higher or further left instead of needing a scroll.
        const margin = 16;
        const rect = popup.getBoundingClientRect();
        const overflowBottom = rect.bottom - (window.innerHeight - margin);
        const overflowRight = rect.right - (document.documentElement.clientWidth - margin);
        if (overflowBottom > 0) {
            // Never push the popup's top above the visible area.
            const shiftUp = Math.min(overflowBottom, Math.max(rect.top - margin, 0));
            popup.style.top = `${y - shiftUp}px`;
        }
        if (overflowRight > 0) {
            const shiftLeft = Math.min(overflowRight, Math.max(rect.left - margin, 0));
            popup.style.left = `${x - shiftLeft}px`;
        }
    }
    function hideDetailPopup() {
        $(popup).addClass("hidden").removeClass("fc-popover");
    }

    $("#closePopupBtn").on("click", function (e) {
        e.stopPropagation();
        hideDetailPopup();
    });

    // Use capture phase so we run before FullCalendar removes the list popover from DOM
    document.addEventListener("click", function (e) {
        if ($(popup).hasClass("hidden")) return;
        if ($(popup).has(e.target).length) return;
        if ($(e.target).closest(".fc-event").length) return;
        if ($(e.target).closest(".fc-popover").length) return;
        hideDetailPopup();
    }, true);

    window.showPopup = showPopup;
    window.hideDetailPopup = hideDetailPopup;
}


$(document).on("htmx:beforeRequest", function(event) {
    if (event.detail.target.id === "mainContent") {
        window.calendarInitialized = false;
    }
});

$(document).on("htmx:afterSettle", function(event) {
    const urlParams = new URLSearchParams(window.location.search);
    window.currentDisplayOnly = urlParams.get('display_only') || '';

    if (!window.calendarInitialized) {
        initCalendar();
    }
    let activeLinkId = "#" + localStorage.getItem("activeSidebarLinkId");
    if (activeLinkId) {
        $(activeLinkId).addClass("bg-primary-600 text-white").find("img").css("filter", "brightness(0) invert(1)");
    }
});

// Build the calendar once the markup is in the page: right away after an HTMX
// swap, or on DOM ready after a full load.
$(function () {
    if (!window.calendarInitialized) {
initCalendar();
    }
});
