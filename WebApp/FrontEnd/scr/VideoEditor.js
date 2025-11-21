document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("editorForm");
    const videoInput = document.getElementById("videoFile");

    // Создаём оверлей
    const overlay = document.createElement("div");
    overlay.style.position = "fixed";
    overlay.style.top = 0;
    overlay.style.left = 0;
    overlay.style.width = "100%";
    overlay.style.height = "100%";
    overlay.style.backgroundColor = "rgba(0,0,0,0.5)";
    overlay.style.color = "white";
    overlay.style.display = "flex";
    overlay.style.alignItems = "center";
    overlay.style.justifyContent = "center";
    overlay.style.fontSize = "24px";
    overlay.style.zIndex = 9999;
    overlay.style.display = "none"; // по умолчанию скрыт
    overlay.innerText = "Видео обрабатывается, подождите...";
    document.body.appendChild(overlay);

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        // Показываем оверлей
        overlay.style.display = "flex";

        const fd = new FormData();

        // Добавляем видео
        if (videoInput.files.length > 0) {
            fd.append("videoFile", videoInput.files[0]);
        }

        // Добавляем остальные поля формы
        const formData = new FormData(form);
        for (const [key, value] of formData.entries()) {
            if (key !== "videoFile" && value) {
                fd.append(key, value);
            }
        }

        try {
            const res = await fetch("/VideoEditor/editor/getpar", {
                method: "POST",
                body: fd
            });

            // Скрываем оверлей после ответа
            overlay.style.display = "none";

            if (!res.ok) {
                alert("Ошибка при обработке видео!");
                return;
            }

            const data = await res.json();

            if (data.link) {
                window.location.href = data.link;
            } else {
                alert("Ссылка не получена!");
            }
        } catch (err) {
            overlay.style.display = "none";
            console.error(err);
            alert("Ошибка соединения с сервером!");
        }
    });
});
