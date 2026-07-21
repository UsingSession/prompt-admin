function decodeSnippet(value) {
  return (value || "").replace(/\\n/g, "\n");
}

function insertAtCursor(textarea, snippet) {
  const start = textarea.selectionStart ?? 0;
  const end = textarea.selectionEnd ?? start;
  const scrollTop = textarea.scrollTop;

  if (typeof textarea.setRangeText === "function") {
    textarea.setRangeText(snippet, start, end, "end");
    textarea.focus();
  } else {
    const before = textarea.value.slice(0, start);
    const after = textarea.value.slice(end);

    textarea.value = `${before}${snippet}${after}`;
    textarea.focus();

    const cursorPosition = start + snippet.length;
    textarea.setSelectionRange(cursorPosition, cursorPosition);
  }

  textarea.scrollTop = scrollTop;
  textarea.dispatchEvent(new Event("input", { bubbles: true }));
}

document.addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) {
    return;
  }

  const button = event.target.closest("[data-insert-target][data-snippet]");
  if (!button) {
    return;
  }

  const targetId = button.dataset.insertTarget;
  const textarea = document.getElementById(targetId);
  if (!textarea) {
    return;
  }

  insertAtCursor(textarea, decodeSnippet(button.dataset.snippet));
});
