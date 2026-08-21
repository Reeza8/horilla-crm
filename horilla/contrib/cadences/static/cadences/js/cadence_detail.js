(function () {
    var AY = 0.43;

    function isRtl() {
        return (
            document.documentElement.getAttribute("dir") === "rtl" ||
            getComputedStyle(document.documentElement).direction === "rtl"
        );
    }

    function ensureLayer(grid) {
        var layer = grid.querySelector(".cadence-flow-arrows");
        if (!layer) {
            layer = document.createElement("div");
            layer.className = "cadence-flow-arrows";
            grid.appendChild(layer);
        }
        return layer;
    }

    function clearLayer(layer) {
        while (layer.firstChild) layer.removeChild(layer.firstChild);
    }

    function placeArrow(layer, x, y, arrowSrc) {
        var img = document.createElement("img");
        img.className = "cadence-flow-arrow";
        img.src = arrowSrc;
        img.alt = "";
        img.style.left = x + "px";
        img.style.top = y + "px";
        layer.appendChild(img);
    }

    function drawFlowArrows() {
        var grid = document.getElementById("cadence-board-grid");
        if (!grid) return;

        var arrowSrc = grid.dataset.arrowSrc || "";
        if (!arrowSrc) return;

        var layer = ensureLayer(grid);
        clearLayer(layer);

        var gr = grid.getBoundingClientRect();
        var cols = grid.querySelectorAll(":scope > .kanban-block");
        if (cols.length < 2) return;

        function anchor(card, towardNextColumn) {
            var r = card.getBoundingClientRect();
            var rtl = isRtl();
            var useRight = towardNextColumn ? !rtl : rtl;
            return {
                x: (useRight ? r.right : r.left) - gr.left,
                y: (r.top - gr.top) + (r.height * AY),
            };
        }

        function placeBetween(parentCard, childCard) {
            var a = anchor(parentCard, true);
            var b = anchor(childCard, false);
            placeArrow(layer, (a.x + b.x) / 2, (a.y + b.y) / 2, arrowSrc);
        }

        function placeBetweenParentAndGroup(parentCard, childCards) {
            if (!childCards || !childCards.length) return;
            if (childCards.length === 1) {
                placeBetween(parentCard, childCards[0]);
                return;
            }
            var a = anchor(parentCard, true);
            var sumX = 0;
            var sumY = 0;
            childCards.forEach(function (ch) {
                var b = anchor(ch, false);
                sumX += b.x;
                sumY += b.y;
            });
            var n = childCards.length;
            placeArrow(layer, (a.x + sumX / n) / 2, (a.y + sumY / n) / 2, arrowSrc);
        }

        function midY(el) {
            var r = el.getBoundingClientRect();
            return r.top + r.height / 2;
        }

        for (var c = 0; c < cols.length - 1; c++) {
            var leftArr = Array.prototype.slice.call(
                cols[c].querySelectorAll(".cadence-followup-card")
            );
            var rightArr = Array.prototype.slice.call(
                cols[c + 1].querySelectorAll(".cadence-followup-card")
            );
            if (!leftArr.length || !rightArr.length) continue;

            var leftByPk = {};
            leftArr.forEach(function (el) {
                var pk = el.getAttribute("data-followup-pk");
                if (pk) leftByPk[pk] = el;
            });

            var childrenByParent = {};
            function addChild(parentPk, childEl) {
                if (!childrenByParent[parentPk]) childrenByParent[parentPk] = [];
                childrenByParent[parentPk].push(childEl);
            }

            rightArr.forEach(function (rc) {
                var bid = (rc.getAttribute("data-branch-from-id") || "").trim();
                if (bid && leftByPk[bid]) {
                    addChild(bid, rc);
                    return;
                }
                var best = leftArr[0];
                var bestD = 1e9;
                leftArr.forEach(function (lc) {
                    var d = Math.abs(midY(lc) - midY(rc));
                    if (d < bestD) {
                        bestD = d;
                        best = lc;
                    }
                });
                var bpk = best.getAttribute("data-followup-pk");
                if (bpk) addChild(bpk, rc);
            });

            Object.keys(childrenByParent).forEach(function (pk) {
                var parent = leftByPk[pk];
                if (!parent) return;
                placeBetweenParentAndGroup(parent, childrenByParent[pk]);
            });
        }
    }

    var redrawTimer = null;

    function schedule() {
        requestAnimationFrame(drawFlowArrows);
        // HTMX swaps can settle in phases (layout/scrollbars/select2). Repaint a few
        // times so arrow position stays aligned with the final card position.
        [80, 180, 320].forEach(function (ms) {
            setTimeout(function () {
                requestAnimationFrame(drawFlowArrows);
            }, ms);
        });
    }

    function scheduleDebounced() {
        if (redrawTimer) clearTimeout(redrawTimer);
        redrawTimer = setTimeout(function () {
            schedule();
        }, 40);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", schedule);
    } else {
        schedule();
    }
    window.addEventListener("resize", scheduleDebounced);
    document.addEventListener("scroll", scheduleDebounced, true);
    if (typeof htmx !== "undefined") {
        document.body.addEventListener("htmx:afterSwap", schedule);
        document.body.addEventListener("htmx:afterSettle", schedule);
    }
})();
