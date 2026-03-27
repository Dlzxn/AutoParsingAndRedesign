document.addEventListener('DOMContentLoaded', () => {
    const editor = document.getElementById('editor');

    // Обработчики для кнопок
    document.querySelectorAll('.toolbar button').forEach(button => {
        button.addEventListener('click', () => {
            const command = button.dataset.command;
            handleCommand(command);
        });
    });

    // Автофокус при загрузке
    editor.focus();
});

function handleCommand(command) {
    switch(command) {
        case 'copy':
            copyToClipboard();
            break;
        case 'selectAll':
            selectAll();
            break;
        default:
            execCommand(command);
    }
}

function execCommand(command, value = null) {
    document.execCommand(command, false, value);
    focusEditor();
}

function copyToClipboard() {
    const text = document.getElementById('editor').innerText;
    navigator.clipboard.writeText(text)
        .then(() => alert('Текст скопирован!'))
        .catch(err => console.error('Ошибка копирования:', err));
}

function selectAll() {
    const range = document.createRange();
    range.selectNodeContents(document.getElementById('editor'));
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
}

function focusEditor() {
    document.getElementById('editor').focus();
}