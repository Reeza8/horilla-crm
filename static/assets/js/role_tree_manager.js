(function(){
  // Keep a small shared state so handlers don't get double-bound
  window.roleTreeState = window.roleTreeState || {
    isSpace: false,
    isPanning: false,
    start: {x:0,y:0},
    base: {tx:0,ty:0},
    scale: 1,
    docHandlers: false,
    controlHandlers: false
  };

  // Initialise the tree UI (call after DOM load and after htmx swaps)
  function initRoleTree(){
    if (!document.querySelector('.genealogy-tree')) return;

    // Wait for jQuery to be ready
    if (typeof $ === 'undefined') {
      setTimeout(initRoleTree, 100);
      return;
    }

    // basic show/hide setup
    $('.genealogy-tree ul').hide();
    $('.genealogy-tree > ul').show();
    $('.genealogy-tree > ul > li > ul').show().addClass('active');

    $('.genealogy-tree li').each(function () {
      if ($(this).find('> ul').length) $(this).addClass('has-children');
    });

    // Delegated expand/collapse (namespaced so we can rebind safely)
    $(document).off('click.roleTree', '.genealogy-tree li');
    $(document).on('click.roleTree', '.genealogy-tree li', function (e) {
      // ignore clicks that originate from node buttons
      if ($(e.target).closest('.member-footer .downline button').length) return;
      e.stopPropagation();

      var $this = $(this);
      var children = $this.find('> ul');
      if (!children.length) return;

      if (children.is(':visible')) {
        children.hide('fast').removeClass('active');
        $this.removeClass('expanded');

        children.find('ul').hide('fast').removeClass('active');
        children.find('li').removeClass('expanded');
      } else {
        children.show('fast').addClass('active');
        $this.addClass('expanded');
      }
    });

    // Prevent node buttons from triggering the parent click
    $(document).off('click.roleTreeButtons', '.member-footer .downline button');
    $(document).on('click.roleTreeButtons', '.member-footer .downline button', function(e){
      e.stopPropagation();
    });

    // Mark second level expanded by default
    $('.genealogy-tree > ul > li').addClass('expanded');

    // Adjust viewport after tree is initialized
    setTimeout(adjustViewport, 100);
  }

  function setVars(){
    const plane = document.getElementById('canvas');
    if (plane) {
      plane.style.transform = `translate(${window.roleTreeState.base.tx}px, ${window.roleTreeState.base.ty}px) scale(${window.roleTreeState.scale})`;
    }
  }

  // Document-level keyboard handlers (bind once)
  function initDocumentHandlers() {
    if (window.roleTreeState.docHandlers) return;

    document.addEventListener('keydown', function(e){
      if (e.code === 'Space' && !window.roleTreeState.isSpace && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
        window.roleTreeState.isSpace = true;
        document.getElementById('viewport')?.classList.add('hand');
        e.preventDefault();
      }
    });

    document.addEventListener('keyup', function(e){
      if (e.code === 'Space') {
        window.roleTreeState.isSpace = false;
        document.getElementById('viewport')?.classList.remove('hand','dragging');
      }
    });

    window.roleTreeState.docHandlers = true;
  }

  // Attach pan/zoom handlers to the current viewport/canvas elements
  function attachViewportHandlers(){
    const wrap = document.getElementById('viewport');
    const plane = document.getElementById('canvas');
    if (!wrap || !plane) return;

    // Remove old listeners if they exist
    if (wrap._onMouseDown) wrap.removeEventListener('mousedown', wrap._onMouseDown);
    if (document._onMouseMove) document.removeEventListener('mousemove', document._onMouseMove);
    if (document._onMouseUp) document.removeEventListener('mouseup', document._onMouseUp);
    if (plane._onClick) plane.removeEventListener('click', plane._onClick, true);
    if (wrap._onWheel) wrap.removeEventListener('wheel', wrap._onWheel);

    wrap._onMouseDown = function(e){
      if (!window.roleTreeState.isSpace) return;
      window.roleTreeState.isPanning = true;
      wrap.classList.add('dragging');
      window.roleTreeState.start.x = e.clientX;
      window.roleTreeState.start.y = e.clientY;
      e.preventDefault();
    };

    document._onMouseMove = function(e){
      if (!window.roleTreeState.isPanning) return;
      window.roleTreeState.base.tx += (e.clientX - window.roleTreeState.start.x);
      window.roleTreeState.base.ty += (e.clientY - window.roleTreeState.start.y);
      window.roleTreeState.start.x = e.clientX;
      window.roleTreeState.start.y = e.clientY;
      setVars();
    };

    document._onMouseUp = function(){
      if (window.roleTreeState.isPanning) {
        window.roleTreeState.isPanning = false;
        wrap.classList.remove('dragging');
      }
    };

    plane._onClick = function(e){
      if (window.roleTreeState.isPanning || window.roleTreeState.isSpace) {
        e.stopPropagation();
        e.preventDefault();
      }
    };

    wrap._onWheel = function(e){
      if (!e.ctrlKey) return;
      e.preventDefault();
      const rect = plane.getBoundingClientRect();
      const cx = (e.clientX - rect.left) / window.roleTreeState.scale;
      const cy = (e.clientY - rect.top) / window.roleTreeState.scale;
      const old = window.roleTreeState.scale;
      const dir = Math.sign(e.deltaY);
      window.roleTreeState.scale = Math.min(2, Math.max(0.3, old * (1 - dir * 0.1)));
      window.roleTreeState.base.tx -= (cx * window.roleTreeState.scale - cx * old);
      window.roleTreeState.base.ty -= (cy * window.roleTreeState.scale - cy * old);
      setVars();
    };

    // attach
    wrap.addEventListener('mousedown', wrap._onMouseDown);
    document.addEventListener('mousemove', document._onMouseMove);
    document.addEventListener('mouseup', document._onMouseUp);
    plane.addEventListener('click', plane._onClick, true);
    wrap.addEventListener('wheel', wrap._onWheel, { passive: false });
  }

  // Canvas Control Functions
  function initCanvasControls() {
    // Prevent double binding
    if (window.roleTreeState.controlHandlers) {
      removeCanvasControls();
    }

    const panStep = 50;
    const zoomStep = 0.1;

    // Store references to handlers for cleanup
    const handlers = {};

    // Zoom controls
    const zoomInBtn = document.getElementById('zoom-in');
    const zoomOutBtn = document.getElementById('zoom-out');
    const zoomResetBtn = document.getElementById('zoom-reset');

    if (zoomInBtn) {
      handlers.zoomIn = function() {
        window.roleTreeState.scale = Math.min(2, window.roleTreeState.scale + zoomStep);
        setVars();
      };
      zoomInBtn.addEventListener('click', handlers.zoomIn);
    }

    if (zoomOutBtn) {
      handlers.zoomOut = function() {
        window.roleTreeState.scale = Math.max(0.3, window.roleTreeState.scale - zoomStep);
        setVars();
      };
      zoomOutBtn.addEventListener('click', handlers.zoomOut);
    }

    if (zoomResetBtn) {
      handlers.zoomReset = function() {
        window.roleTreeState.scale = 1;
        window.roleTreeState.base = { tx: 0, ty: 0 };
        setVars();
        setTimeout(adjustViewport, 50);
      };
      zoomResetBtn.addEventListener('click', handlers.zoomReset);
    }

    // Pan controls
    const panUpBtn = document.getElementById('pan-up');
    const panDownBtn = document.getElementById('pan-down');
    const panLeftBtn = document.getElementById('pan-left');
    const panRightBtn = document.getElementById('pan-right');

    if (panUpBtn) {
      handlers.panUp = function() {
        window.roleTreeState.base.ty -= panStep;
        setVars();
      };
      panUpBtn.addEventListener('click', handlers.panUp);
    }

    if (panDownBtn) {
      handlers.panDown = function() {
        window.roleTreeState.base.ty += panStep;
        setVars();
      };
      panDownBtn.addEventListener('click', handlers.panDown);
    }

    if (panLeftBtn) {
      handlers.panLeft = function() {
        window.roleTreeState.base.tx -= panStep;
        setVars();
      };
      panLeftBtn.addEventListener('click', handlers.panLeft);
    }

    if (panRightBtn) {
      handlers.panRight = function() {
        window.roleTreeState.base.tx += panStep;
        setVars();
      };
      panRightBtn.addEventListener('click', handlers.panRight);
    }

    // Store handlers for cleanup
    window.roleTreeState._controlHandlers = handlers;
    window.roleTreeState.controlHandlers = true;
  }

  function removeCanvasControls() {
    if (!window.roleTreeState._controlHandlers) return;

    const handlers = window.roleTreeState._controlHandlers;

    document.getElementById('zoom-in')?.removeEventListener('click', handlers.zoomIn);
    document.getElementById('zoom-out')?.removeEventListener('click', handlers.zoomOut);
    document.getElementById('zoom-reset')?.removeEventListener('click', handlers.zoomReset);
    document.getElementById('pan-up')?.removeEventListener('click', handlers.panUp);
    document.getElementById('pan-down')?.removeEventListener('click', handlers.panDown);
    document.getElementById('pan-left')?.removeEventListener('click', handlers.panLeft);
    document.getElementById('pan-right')?.removeEventListener('click', handlers.panRight);

    window.roleTreeState.controlHandlers = false;
    window.roleTreeState._controlHandlers = null;
  }

  function adjustViewport(){
    // #viewport is a flex container that already centres the canvas, so no
    // extra horizontal offset is needed (adding one double-centres the tree).
    if (document.getElementById('canvas')) {
      window.roleTreeState.base.tx = 0;
      setVars();
    }
  }

  function fullInit() {
    initDocumentHandlers();
    initRoleTree();
    attachViewportHandlers();
    initCanvasControls();
  }

  // initialise on page load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fullInit);
  } else {
    fullInit();
  }

  // re-init after HTMX swaps content into the page
  document.body.addEventListener('htmx:afterSwap', function(evt){
    const target = evt.detail?.target;
    if (!target) return;

    // Check if role-container was swapped
    if (target.id === 'role-container' || target.querySelector('#role-container') || target.closest('#role-container')) {
      // Small delay to ensure DOM is ready
      setTimeout(function() {
        initRoleTree();
        attachViewportHandlers();
        initCanvasControls();
      }, 50);
    }
  });

  // Also listen for htmx:load event which fires after content is processed
  document.body.addEventListener('htmx:load', function(evt){
    const target = evt.detail?.elt;
    if (!target) return;

    if (target.id === 'role-container' || target.querySelector('#role-container')) {
      setTimeout(function() {
        initRoleTree();
        attachViewportHandlers();
        initCanvasControls();
      }, 50);
    }
  });

  window.addEventListener('load', adjustViewport);
  window.addEventListener('resize', adjustViewport);
})();
