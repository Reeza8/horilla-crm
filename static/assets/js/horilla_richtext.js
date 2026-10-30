/**
 * Helpers for editors rendered by HorillaSummernoteWidget (textarea[data-richtext]):
 * copy the content back to the textarea, replace it, remember the cursor, insert text.
 * Requires jQuery and summernote-lite.
 */
window.HorillaRichText = (function () {
    var savedRange = null;

    /** The .note-editor of a textarea (the django-summernote widget wraps it in .summernote-div). */
    function editorOf($ta) {
        var $editor = $ta.next('.note-editor');
        return $editor.length ? $editor : $ta.next('.summernote-div').find('.note-editor');
    }

    function hasEditor($ta) {
        return $ta.length && editorOf($ta).length > 0;
    }

    /** Copy the editor content back into the textarea so it is submitted. */
    function sync($scope) {
        $scope.find('textarea[data-richtext]').each(function () {
            if (hasEditor($(this))) $(this).val($(this).summernote('code'));
        });
    }

    /** Replace the whole content of an editor (e.g. when a saved template is chosen). */
    function setContent($ta, html) {
        if (hasEditor($ta)) $ta.summernote('code', html);
        $ta.val(html);
    }

    /** Destroy the editors inside a container (frees the dialogs Summernote adds to <body>). */
    function destroy($scope) {
        $scope.find('textarea[data-richtext]').each(function () {
            if (hasEditor($(this))) {
                try { $(this).summernote('destroy'); } catch (e) { /* already gone */ }
            }
        });
    }

    function saveCursor() {
        var sel = window.getSelection();
        savedRange = sel.rangeCount > 0 ? sel.getRangeAt(0).cloneRange() : null;
    }

    /** Insert text at the saved cursor (or code-view caret) of the given editor. */
    function insertText($ta, text) {
        if (!hasEditor($ta)) return;
        var $editor = editorOf($ta);
        if ($editor.hasClass('codeview')) {
            var codable = $editor.find('.note-codable')[0];
            var start = codable.selectionStart, end = codable.selectionEnd;
            codable.value = codable.value.substring(0, start) + text + codable.value.substring(end);
            $ta.summernote('code', codable.value);
        } else {
            if (savedRange && savedRange.startContainer) {
                try {
                    var sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(savedRange);
                } catch (e) { /* range no longer valid: insert at current caret */ }
            }
            $ta.summernote('focus');
            $ta.summernote('insertText', text);
        }
        $ta.val($ta.summernote('code'));
        savedRange = null;
    }

    // Copy editor content into its textarea before any button/submit handler runs
    // (capture phase), so Preview, Save and Send always see what was typed.
    document.addEventListener('click', function (e) {
        if (e.target.closest && e.target.closest('button, [type=submit], [hx-post]')) {
            sync($(document));
        }
    }, true);

    // Clean up editors when HTMX is about to replace the container they live in
    $(document).on('htmx:beforeSwap', function (evt) {
        destroy($(evt.target));
    });

    return { hasEditor: hasEditor, sync: sync, destroy: destroy, setContent: setContent, saveCursor: saveCursor, insertText: insertText };
})();
