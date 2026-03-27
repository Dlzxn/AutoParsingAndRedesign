
document.addEventListener('DOMContentLoaded', () => {
    const editorForm = document.getElementById('editorForm');
    const videoUrlInput = document.getElementById('videoUrl');
    const uploadText = document.getElementById('uploadText');

    if (videoUrlInput && videoUrlInput.value.trim() !== "") {
        uploadText.innerText = "✅ Видео прикреплено";
        uploadText.style.color = "#4CAF50";
        uploadText.style.fontWeight = "bold";
    }

    editorForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const formData = new FormData(e.target);
        
        submitBtn.disabled = true;
        submitBtn.innerText = "Обработка...";
        uploadText.innerText = "⏳ Идет рендеринг видео на сервере, пожалуйста, подождите...";
        uploadText.style.color = "#ffa500";

        try {
            const response = await fetch('/process-video', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = "result_video.mp4";
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
                
                uploadText.innerText = "✅ Готово! Скачивание началось.";
                uploadText.style.color = "#4CAF50";
            } else {
                const errorData = await response.json();
                alert("Ошибка сервера: " + errorData.message);
                uploadText.innerText = "❌ Ошибка при обработке.";
                uploadText.style.color = "#f44336";
            }
        } catch (error) {
            console.error(error);
            alert("Не удалось связаться с сервером.");
            uploadText.innerText = "❌ Ошибка соединения.";
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerText = "Редактировать";
        }
    });
});