// Make these variables accessible to closeShortcutModal
window.shortcutKeysState = {
    modalShown: false,
    activeModifier: null,
    modifierHoldTimer: null
};

function closeShortcutModal() {
    const modal = $('#shortcutKeysModal');
    const modalBox = modal.find('.bg-white.w-full.max-w-md');

    // Add closing animation
    modalBox.removeClass('opacity-100 scale-100').addClass('opacity-0 scale-95');

    // Hide modal after animation completes
    setTimeout(function() {
        modal.addClass('hidden');
    }, 200);

    // Reset all state variables
    window.shortcutKeysState.modalShown = false;
    window.shortcutKeysState.activeModifier = null;

    if (window.shortcutKeysState.modifierHoldTimer) {
        clearTimeout(window.shortcutKeysState.modifierHoldTimer);
        window.shortcutKeysState.modifierHoldTimer = null;
    }
}

function setupModalObserver() {
    const modalElement = document.getElementById('shortcutKeysModal');
    if (modalElement && !modalElement.hasAttribute('data-observer-attached')) {
        modalElement.setAttribute('data-observer-attached', 'true');

        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    const isHidden = modalElement.classList.contains('hidden');

                    // If modal is hidden, always reset state
                    if (isHidden) {
                        window.shortcutKeysState.modalShown = false;
                        window.shortcutKeysState.activeModifier = null;

                        if (window.shortcutKeysState.modifierHoldTimer) {
                            clearTimeout(window.shortcutKeysState.modifierHoldTimer);
                            window.shortcutKeysState.modifierHoldTimer = null;
                        }
                    }
                }
            });
        });

        observer.observe(modalElement, {
            attributes: true,
            attributeFilter: ['class']
        });
    }
}

function initShortcutKeys() {
    if (window.shortcutKeysInitialized) {
        return;
    }
    window.shortcutKeysInitialized = true;

    const MODIFIER_HOLD_DURATION = 200;
    const shortKeyDataUrl = "/shortkeys/short-key-data/";
    window.shortcutKeysCache = [];

    function createShortcutModal() {
        if ($('#shortcutKeysModal').length) {
            setupModalObserver();
            return;
        }

        const modalHTML = `
        <div id="shortcutKeysModal" class="fixed inset-0 bg-black bg-opacity-50 hidden items-center justify-center z-50 bg-[#00000030] flex">
            <div class="bg-white w-full max-w-md rounded-lg shadow-lg p-0 transition-all duration-300 md:min-w-[650px] opacity-100 scale-100">
                <div class="relative p-4 w-full max-w-2xl max-h-full">
                    <div class="relative bg-white rounded-lg shadow-sm">
                        <div class="p-5 pt-3 flex justify-between items-center">
                            <h2 class="text-md font-semibold">Available Shortcut Keys</h2>
                            <button type="button" class="text-gray-500 hover:text-red-500 text-xl" onclick="closeShortcutModal()">
                            <img src="/static/assets/icons/close.svg" alt="icon">
                            </button>
                        </div>
                        <div id="shortcut-content" class="overflow-hidden p-4 grid gap-2" style="max-height: 400px; overflow-y: auto;"></div>
                    </div>
                </div>
            </div>
        </div>
        `;
        $('body').append(modalHTML);

        // Setup observer after modal is created
        setTimeout(setupModalObserver, 0);
    }

    function fetchShortcutKeys(callback) {
        $.ajax({
            url: shortKeyDataUrl,
            method: 'GET',
            success: function(data) {
                const isMac = /mac|darwin/i.test(navigator.userAgent);
                window.shortcutKeysCache = data.shortcuts.map(sk => ({
                    key: sk.key.toUpperCase(),
                    command: sk.command.toLowerCase(),
                    displayCommand: (sk.command.toLowerCase() === 'alt' && isMac) ? 'OPTION' : sk.command.toUpperCase(),
                    displaySymbol: (sk.command.toLowerCase() === 'alt' && isMac) ? '⌥' : sk.command.toUpperCase(),
                    title: sk.title,
                    section: sk.section,
                    description: sk.description || '',
                    page: sk.page
                }));
                callback(window.shortcutKeysCache);
            },
            error: function(error) {
                console.error('Failed to fetch shortcut keys:', error);
                callback([]);
            }
        });
    }

    function showShortcutModal(keys) {
        createShortcutModal();
        const modal = $('#shortcutKeysModal');
        const modalBox = modal.find('.bg-white.w-full.max-w-md');

        // Remove hidden class
        modal.removeClass('hidden');

        // Remove the hidden animation classes and add visible ones
        modalBox.removeClass('opacity-0 scale-95').addClass('opacity-100 scale-100');

        window.shortcutKeysState.modalShown = true;

        let contentHTML = keys.map(sk => `
            <div class="flex items-center p-2 mb-1 border-[2px] border-primary-300 rounded-[5px] shadow-sm">
                <div class="min-w-[80px] flex gap-1">
                    <span class="outline outline-1 outline-offset-[-1px] outline-primary-600 hover:bg-primary-300 transition duration-300 text-primary-600 bg-primary-300 rounded font-semibold text-xs px-2 py-1">${sk.displayCommand}</span>
                    <span>+</span>
                    <span class="bg-[#e1850d23] text-[#e1850d] border border-[#e1850d] px-2 py-1 rounded text-xs font-semibold">${sk.key}</span>
                </div>
                <div class="ms-4 flex-1">
                    <div class="font-medium">${sk.title}</div>
                    ${sk.description ? `<div class="text-xs text-gray-600">${sk.description}</div>` : ''}
                </div>
            </div>
        `).join('');

        $('#shortcut-content').html(contentHTML);
    }

    $(document).off("keydown.shortcutKeys keyup.shortcutKeys");

    fetchShortcutKeys(function(keys) {
        window.shortcutKeysCache = keys;

        $(document).on("keydown.shortcutKeys", function(e) {
            if (e.altKey && !window.shortcutKeysState.activeModifier) {
                window.shortcutKeysState.activeModifier = 'alt';

                if ($("input:focus, textarea:focus, select:focus").length) {
                    return;
                }

                if (!window.shortcutKeysState.modalShown && !window.shortcutKeysState.modifierHoldTimer) {
                    window.shortcutKeysState.modifierHoldTimer = setTimeout(function() {
                        showShortcutModal(window.shortcutKeysCache);
                    }, MODIFIER_HOLD_DURATION);
                }
                return;
            }

            if (window.shortcutKeysState.activeModifier && e.altKey) {
                const pressedKey = e.key.toUpperCase();

                if (window.shortcutKeysState.modifierHoldTimer) {
                    clearTimeout(window.shortcutKeysState.modifierHoldTimer);
                    window.shortcutKeysState.modifierHoldTimer = null;
                }

                const match = window.shortcutKeysCache.find(
                    sk => sk.key === pressedKey && sk.command.toLowerCase() === 'alt'
                );

                if (match) {
                    e.preventDefault();

                    if ($("input:focus, textarea:focus, select:focus").length) {
                        return;
                    }

                    closeShortcutModal();

                    const url = new URL(match.page, window.location.origin);
                    if (match.section) {
                        url.searchParams.set("section", match.section);
                    }
                    window.location.href = url.toString();
                }
            }
        });

        $(document).on("keyup.shortcutKeys", function(e) {
            if (!e.altKey && window.shortcutKeysState.activeModifier === 'alt') {
                window.shortcutKeysState.activeModifier = null;

                if (window.shortcutKeysState.modifierHoldTimer) {
                    clearTimeout(window.shortcutKeysState.modifierHoldTimer);
                    window.shortcutKeysState.modifierHoldTimer = null;
                }
            }
        });
    });
}

function refreshShortcutKeys() {
    const shortKeyDataUrl = "/shortkeys/short-key-data/";
    $.ajax({
        url: shortKeyDataUrl,
        method: 'GET',
        success: function(data) {
            const isMac = /mac|darwin/i.test(navigator.userAgent);
            window.shortcutKeysCache = data.shortcuts.map(sk => ({
                key: sk.key.toUpperCase(),
                command: sk.command.toLowerCase(),
                displayCommand: (sk.command.toLowerCase() === 'alt' && isMac) ? 'OPTION' : sk.command.toUpperCase(),
                displaySymbol: (sk.command.toLowerCase() === 'alt' && isMac) ? '⌥' : sk.command.toUpperCase(),
                title: sk.title,
                section: sk.section,
                description: sk.description || '',
                page: sk.page
            }));
        },
        error: function(error) {
            console.error('Failed to refresh shortcut keys:', error);
        }
    });
}

$(document).ready(initShortcutKeys);

$(document).on("htmx:afterSwap htmx:afterSettle", function(event) {
    const target = event.target;
    const triggeringElement = event.detail?.elt;

    if (
        (triggeringElement && (
            triggeringElement.id === 'short-key-create' ||
            triggeringElement.closest('[hx-get*="short_key"]') ||
            triggeringElement.closest('[hx-post*="short_key"]')
        )) ||
        (target && (
            target.id === 'short_key_list' ||
            target.closest('#short_key_list')
        ))
    ) {
        refreshShortcutKeys();
    }
});
