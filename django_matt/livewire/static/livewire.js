/**
 * Django Matt Livewire - Client-side JavaScript
 *
 * Handles:
 * - wire:click, wire:submit, wire:model bindings
 * - WebSocket connection for real-time updates
 * - State synchronization
 * - Optimistic UI updates
 */

(function () {
  "use strict";

  // ==========================================================================
  // Configuration
  // ==========================================================================

  const config = {
    messageEndpoint: "/livewire/message",
    uploadEndpoint: "/livewire/upload",
    websocketUrl: null, // Set to enable WebSocket mode
    debounceMs: 150,
    csrfToken: null,
  };

  // ==========================================================================
  // Utilities
  // ==========================================================================

  function debounce(func, wait) {
    let timeout;
    return function (...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  }

  function getCsrfToken() {
    if (config.csrfToken) return config.csrfToken;

    // Try cookie
    const cookies = document.cookie.split(";");
    for (const cookie of cookies) {
      const [name, value] = cookie.trim().split("=");
      if (name === "csrftoken") return value;
    }

    // Try meta tag
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute("content");

    // Try hidden input
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input) return input.value;

    return null;
  }

  function getComponentElement(el) {
    return el.closest("[wire\\:id]");
  }

  function getComponentData(el) {
    const componentEl = getComponentElement(el);
    if (!componentEl) return null;

    return {
      id: componentEl.getAttribute("wire:id"),
      snapshot: componentEl.getAttribute("wire:snapshot"),
      element: componentEl,
    };
  }

  // ==========================================================================
  // HTTP Transport
  // ==========================================================================

  async function sendMessage(componentData, payload) {
    const response = await fetch(config.messageEndpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
        "X-Livewire": "true",
      },
      body: JSON.stringify({
        _snapshot: componentData.snapshot,
        ...payload,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  // ==========================================================================
  // WebSocket Transport
  // ==========================================================================

  class WebSocketConnection {
    constructor(url) {
      this.url = url;
      this.ws = null;
      this.connected = false;
      this.queue = [];
      this.callbacks = new Map();
      this.reconnectAttempts = 0;
      this.maxReconnectAttempts = 5;
      this.reconnectDelay = 1000;
    }

    connect() {
      return new Promise((resolve, reject) => {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          this.connected = true;
          this.reconnectAttempts = 0;
          console.log("[Livewire] WebSocket connected");

          // Process queued messages
          while (this.queue.length > 0) {
            const msg = this.queue.shift();
            this.ws.send(JSON.stringify(msg));
          }

          resolve();
        };

        this.ws.onclose = () => {
          this.connected = false;
          console.log("[Livewire] WebSocket disconnected");
          this.attemptReconnect();
        };

        this.ws.onerror = (error) => {
          console.error("[Livewire] WebSocket error:", error);
          reject(error);
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(JSON.parse(event.data));
        };
      });
    }

    attemptReconnect() {
      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        console.error("[Livewire] Max reconnection attempts reached");
        return;
      }

      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

      console.log(`[Livewire] Reconnecting in ${delay}ms...`);
      setTimeout(() => this.connect(), delay);
    }

    send(message) {
      if (this.connected) {
        this.ws.send(JSON.stringify(message));
      } else {
        this.queue.push(message);
      }
    }

    handleMessage(data) {
      switch (data.type) {
        case "update":
          this.handleUpdate(data);
          break;
        case "event":
          this.handleEvent(data);
          break;
        case "error":
          console.error("[Livewire] Server error:", data.message);
          break;
      }
    }

    handleUpdate(data) {
      const componentEl = document.querySelector(`[wire\\:id="${data.component_id}"]`);
      if (componentEl) {
        morphdom(componentEl, data.html, {
          onBeforeElUpdated: (fromEl, toEl) => {
            // Preserve focus
            if (fromEl === document.activeElement) {
              toEl.focus();
            }
            return true;
          },
        });
        componentEl.setAttribute("wire:snapshot", data.snapshot);
      }
    }

    handleEvent(data) {
      const event = new CustomEvent(`livewire:${data.event}`, {
        detail: data.data,
        bubbles: true,
      });
      document.dispatchEvent(event);
    }

    subscribe(componentId, componentName) {
      this.send({
        type: "subscribe",
        component_id: componentId,
        component_name: componentName,
      });
    }

    unsubscribe(componentId) {
      this.send({
        type: "unsubscribe",
        component_id: componentId,
      });
    }

    callAction(snapshot, action, params = []) {
      this.send({
        type: "action",
        snapshot: snapshot,
        action: action,
        params: params,
      });
    }
  }

  let wsConnection = null;

  // ==========================================================================
  // DOM Morphing (Simple Implementation)
  // ==========================================================================

  function morphdom(fromEl, toHtml, options = {}) {
    // Simple implementation - replace innerHTML
    // In production, use a proper morphdom library
    const temp = document.createElement("div");
    temp.innerHTML = toHtml;
    const toEl = temp.firstElementChild;

    if (toEl) {
      // Copy wire attributes
      const wireId = fromEl.getAttribute("wire:id");
      const wireSnapshot = fromEl.getAttribute("wire:snapshot");

      fromEl.innerHTML = toEl.innerHTML;

      // Restore wire attributes
      if (wireId) fromEl.setAttribute("wire:id", wireId);
      if (wireSnapshot) fromEl.setAttribute("wire:snapshot", wireSnapshot);

      // Re-bind events
      initComponent(fromEl);
    }
  }

  // ==========================================================================
  // Event Handlers
  // ==========================================================================

  async function handleAction(el, action, params = []) {
    const componentData = getComponentData(el);
    if (!componentData) return;

    // Show loading state
    el.setAttribute("wire:loading", "true");

    try {
      if (wsConnection && wsConnection.connected) {
        wsConnection.callAction(componentData.snapshot, action, params);
      } else {
        const result = await sendMessage(componentData, {
          _action: action,
          _params: params,
        });

        // Update DOM
        morphdom(componentData.element, result.html);
        componentData.element.setAttribute("wire:snapshot", result.snapshot);

        // Handle effects
        if (result.effects) {
          handleEffects(result.effects);
        }
      }
    } catch (error) {
      console.error("[Livewire] Action error:", error);
    } finally {
      el.removeAttribute("wire:loading");
    }
  }

  async function handleModelUpdate(el, property, value) {
    const componentData = getComponentData(el);
    if (!componentData) return;

    try {
      if (wsConnection && wsConnection.connected) {
        wsConnection.send({
          type: "update",
          snapshot: componentData.snapshot,
          updates: { [property]: value },
        });
      } else {
        const result = await sendMessage(componentData, {
          _updates: { [property]: value },
        });

        morphdom(componentData.element, result.html);
        componentData.element.setAttribute("wire:snapshot", result.snapshot);
      }
    } catch (error) {
      console.error("[Livewire] Model update error:", error);
    }
  }

  function handleEffects(effects) {
    if (effects.redirect) {
      window.location.href = effects.redirect;
    }

    if (effects.refresh) {
      window.location.reload();
    }

    if (effects.emit) {
      const event = new CustomEvent(`livewire:${effects.emit.event}`, {
        detail: effects.emit.data,
        bubbles: true,
      });
      document.dispatchEvent(event);
    }
  }

  // ==========================================================================
  // Parse Action
  // ==========================================================================

  function parseAction(actionStr) {
    // Parse: "methodName" or "methodName(arg1, arg2)"
    const match = actionStr.match(/^(\w+)(?:\((.*)\))?$/);
    if (!match) return { method: actionStr, params: [] };

    const method = match[1];
    const paramsStr = match[2] || "";

    let params = [];
    if (paramsStr) {
      // Simple parameter parsing
      try {
        params = JSON.parse(`[${paramsStr}]`);
      } catch {
        // If JSON parse fails, split by comma
        params = paramsStr.split(",").map((p) => {
          p = p.trim();
          // Try to parse as number
          if (!isNaN(p)) return Number(p);
          // Remove quotes
          if ((p.startsWith('"') && p.endsWith('"')) || (p.startsWith("'") && p.endsWith("'"))) {
            return p.slice(1, -1);
          }
          return p;
        });
      }
    }

    return { method, params };
  }

  // ==========================================================================
  // Initialize Component
  // ==========================================================================

  function initComponent(componentEl) {
    // wire:click
    componentEl.querySelectorAll("[wire\\:click]").forEach((el) => {
      if (el._livewireClickBound) return;
      el._livewireClickBound = true;

      el.addEventListener("click", (e) => {
        e.preventDefault();
        const actionStr = el.getAttribute("wire:click");
        const { method, params } = parseAction(actionStr);
        handleAction(el, method, params);
      });
    });

    // wire:submit
    componentEl.querySelectorAll("form[wire\\:submit]").forEach((form) => {
      if (form._livewireSubmitBound) return;
      form._livewireSubmitBound = true;

      form.addEventListener("submit", (e) => {
        e.preventDefault();
        const actionStr = form.getAttribute("wire:submit");
        const { method, params } = parseAction(actionStr);
        handleAction(form, method, params);
      });
    });

    // wire:model
    componentEl.querySelectorAll("[wire\\:model]").forEach((el) => {
      if (el._livewireModelBound) return;
      el._livewireModelBound = true;

      const property = el.getAttribute("wire:model");
      const isLazy = el.hasAttribute("wire:model.lazy");
      const isDebounce = el.hasAttribute("wire:model.debounce");

      let handler;
      if (el.type === "checkbox") {
        handler = () => handleModelUpdate(el, property, el.checked);
      } else if (el.type === "radio") {
        handler = () => {
          if (el.checked) handleModelUpdate(el, property, el.value);
        };
      } else {
        handler = () => handleModelUpdate(el, property, el.value);
      }

      if (isDebounce) {
        handler = debounce(handler, config.debounceMs);
      }

      const event = isLazy ? "change" : "input";
      el.addEventListener(event, handler);
    });

    // wire:keydown, wire:keyup
    ["keydown", "keyup"].forEach((eventType) => {
      componentEl.querySelectorAll(`[wire\\:${eventType}]`).forEach((el) => {
        const attr = `_livewire${eventType}Bound`;
        if (el[attr]) return;
        el[attr] = true;

        const actionStr = el.getAttribute(`wire:${eventType}`);
        const modifiers = actionStr.split(".");
        const actionPart = modifiers[0];
        const keys = modifiers.slice(1);

        el.addEventListener(eventType, (e) => {
          // Check key modifiers
          if (keys.length > 0) {
            const keyMatch = keys.some((key) => {
              if (key === "enter") return e.key === "Enter";
              if (key === "escape") return e.key === "Escape";
              if (key === "tab") return e.key === "Tab";
              if (key === "space") return e.key === " ";
              return e.key.toLowerCase() === key.toLowerCase();
            });
            if (!keyMatch) return;
          }

          const { method, params } = parseAction(actionPart);
          handleAction(el, method, params);
        });
      });
    });
  }

  // ==========================================================================
  // Initialize All Components
  // ==========================================================================

  function initAllComponents() {
    document.querySelectorAll("[wire\\:id]").forEach(initComponent);
  }

  // ==========================================================================
  // Public API
  // ==========================================================================

  window.Livewire = {
    // Configuration
    config(options) {
      Object.assign(config, options);
    },

    // Initialize
    init() {
      initAllComponents();

      // Observe for new components
      const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          mutation.addedNodes.forEach((node) => {
            if (node.nodeType === 1 && node.hasAttribute("wire:id")) {
              initComponent(node);
            } else if (node.nodeType === 1) {
              node.querySelectorAll("[wire\\:id]").forEach(initComponent);
            }
          });
        });
      });

      observer.observe(document.body, { childList: true, subtree: true });
    },

    // Connect WebSocket
    async connectWebSocket(url) {
      config.websocketUrl = url;
      wsConnection = new WebSocketConnection(url);
      await wsConnection.connect();

      // Subscribe all existing components
      document.querySelectorAll("[wire\\:id]").forEach((el) => {
        const id = el.getAttribute("wire:id");
        const name = el.getAttribute("wire:name") || "unknown";
        wsConnection.subscribe(id, name);
      });
    },

    // Manual refresh
    refresh(componentId) {
      const el = document.querySelector(`[wire\\:id="${componentId}"]`);
      if (el) {
        const snapshot = el.getAttribute("wire:snapshot");
        sendMessage({ id: componentId, snapshot }, {}).then((result) => {
          morphdom(el, result.html);
          el.setAttribute("wire:snapshot", result.snapshot);
        });
      }
    },

    // Emit event
    emit(event, data) {
      const customEvent = new CustomEvent(`livewire:${event}`, {
        detail: data,
        bubbles: true,
      });
      document.dispatchEvent(customEvent);
    },

    // Listen to events
    on(event, callback) {
      document.addEventListener(`livewire:${event}`, (e) => callback(e.detail));
    },
  };

  // Auto-init on DOMContentLoaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => Livewire.init());
  } else {
    Livewire.init();
  }
})();
