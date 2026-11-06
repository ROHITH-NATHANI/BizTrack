// BizTrack Interactive Kanban Board Logic
document.addEventListener("DOMContentLoaded", () => {
  const board = document.getElementById("kanbanBoard");
  const toast = document.getElementById("toast");
  const transitions = window.BIZTRACK_TRANSITIONS || {};

  let draggedCard = null;
  let originCol = null;
  let originStatus = null;
  let originNextSibling = null;

  function showToast(message, type = "info") {
    if (!toast) return;
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(() => {
      toast.className = "toast";
    }, 3500);
  }

  function updateColumnCounts() {
    document.querySelectorAll(".kanban-col").forEach(col => {
      const status = col.dataset.status;
      const cards = col.querySelectorAll(".kanban-card");
      const countEl = col.querySelector(".kanban-count");
      const emptyHint = col.querySelector(".kanban-empty-hint");

      if (countEl) countEl.textContent = cards.length;
      if (emptyHint) {
        if (cards.length === 0) {
          emptyHint.classList.remove("hidden");
        } else {
          emptyHint.classList.add("hidden");
        }
      }
    });
  }

  // Set up cards
  function attachCardListeners(card) {
    card.addEventListener("dragstart", (e) => {
      draggedCard = card;
      originCol = card.closest(".kanban-cards");
      originStatus = card.dataset.status;
      originNextSibling = card.nextElementSibling;

      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", card.dataset.id);

      // Delay adding class slightly so ghost image isn't transparent
      setTimeout(() => card.classList.add("dragging"), 0);

      // Highlight allowed and disallowed drop columns
      const allowed = transitions[originStatus] || [];
      document.querySelectorAll(".kanban-col").forEach(col => {
        const colStatus = col.dataset.status;
        if (colStatus === originStatus) {
          // Current column
          col.classList.add("current-column");
        } else if (allowed.includes(colStatus)) {
          col.classList.add("valid-drop");
        } else {
          col.classList.add("invalid-drop");
        }
      });
    });

    card.addEventListener("dragend", () => {
      card.classList.remove("dragging");
      document.querySelectorAll(".kanban-col").forEach(col => {
        col.classList.remove("valid-drop", "invalid-drop", "current-column", "drag-over");
      });
      draggedCard = null;
      originCol = null;
      originStatus = null;
      originNextSibling = null;
    });
  }

  document.querySelectorAll(".kanban-card").forEach(attachCardListeners);

  // Set up drop zones
  document.querySelectorAll(".kanban-cards").forEach(dropZone => {
    dropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      if (!draggedCard) return;

      const targetCol = dropZone.closest(".kanban-col");
      const targetStatus = dropZone.dataset.status;
      const allowed = transitions[originStatus] || [];

      if (targetStatus === originStatus || allowed.includes(targetStatus)) {
        e.dataTransfer.dropEffect = "move";
        targetCol.classList.add("drag-over");
      } else {
        e.dataTransfer.dropEffect = "none";
        targetCol.classList.remove("drag-over");
      }
    });

    dropZone.addEventListener("dragleave", (e) => {
      const targetCol = dropZone.closest(".kanban-col");
      // Only remove if actually leaving the column element
      if (!targetCol.contains(e.relatedTarget)) {
        targetCol.classList.remove("drag-over");
      }
    });

    dropZone.addEventListener("drop", async (e) => {
      e.preventDefault();
      const targetCol = dropZone.closest(".kanban-col");
      targetCol.classList.remove("drag-over");

      if (!draggedCard) return;

      const targetStatus = dropZone.dataset.status;
      const cardId = draggedCard.dataset.id;
      const currentStatus = originStatus;

      // Dropped into same column
      if (targetStatus === currentStatus) return;

      const allowed = transitions[currentStatus] || [];
      if (!allowed.includes(targetStatus)) {
        const allowedMsg = allowed.length ? allowed.join(", ") : "None";
        showToast(`Cannot move request from "${currentStatus}" to "${targetStatus}". Allowed: ${allowedMsg}`, "error");
        return;
      }

      // Optimistic UI move
      dropZone.appendChild(draggedCard);
      draggedCard.dataset.status = targetStatus;
      updateColumnCounts();

      try {
        const response = await fetch(`/api/requests/${cardId}/status`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ status: targetStatus })
        });

        const data = await response.json();

        if (response.ok && data.ok) {
          showToast(`Request #${cardId} updated to ${targetStatus}`, "ok");
        } else {
          throw new Error(data.error || "Failed to update status");
        }
      } catch (err) {
        // Revert UI move on failure
        if (originNextSibling && originNextSibling.parentNode === originCol) {
          originCol.insertBefore(draggedCard, originNextSibling);
        } else {
          originCol.appendChild(draggedCard);
        }
        draggedCard.dataset.status = currentStatus;
        updateColumnCounts();
        showToast(`Workflow error: ${err.message}`, "error");
      }
    });
  });

  updateColumnCounts();
});

