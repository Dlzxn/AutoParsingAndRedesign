/* Простой текстовый редактор для постов (Tumblr). Текст передаётся со страницы поиска через sessionStorage. */
document.addEventListener('DOMContentLoaded', () => {
  const editor = document.getElementById('editor');
  const sourceLink = document.querySelector('[data-source-link]');

  try {
    const text = sessionStorage.getItem('textEditorContent');
    const source = sessionStorage.getItem('textEditorSource');
    if (text) editor.innerText = text;
    if (source && /^https?:\/\//.test(source)) {
      sourceLink.href = source;
      sourceLink.hidden = false;
    }
  } catch (_) { /* sessionStorage недоступен */ }

  editor.addEventListener('input', () => {
    try { sessionStorage.setItem('textEditorContent', editor.innerText); } catch (_) { /* ignore */ }
  });

  document.querySelectorAll('.text-toolbar button').forEach((button) => {
    button.addEventListener('click', async () => {
      const command = button.dataset.command;
      if (command === 'copy') {
        try {
          await navigator.clipboard.writeText(editor.innerText);
          App.toast('Текст скопирован', 'success', 2000);
        } catch (_) {
          App.toast('Не удалось скопировать текст');
        }
      } else if (command === 'selectAll') {
        const range = document.createRange();
        range.selectNodeContents(editor);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
      } else {
        document.execCommand(command, false, null);
      }
      editor.focus();
    });
  });

  editor.focus();
});
