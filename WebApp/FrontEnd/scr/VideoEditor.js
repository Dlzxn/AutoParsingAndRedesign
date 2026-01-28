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

        const formData = new FormData(form);
        const errors = [];

        // Валидация видео
        if (videoInput.files.length === 0) {
            errors.push("Пожалуйста, выберите видеофайл.");
        }

        // Валидация полей
        const trimVal = formData.get("trim");
        if (trimVal && !/^\d+(\.\d+)?\s*-\s*\d+(\.\d+)?$/.test(trimVal.trim())) {
            errors.push("Обрезка: формат должен быть 'начало-конец' (например, 10-60).");
        }

        const resizeVal = formData.get("resize");
        if (resizeVal) {
             const val = resizeVal.trim().toLowerCase();
             if (!/^\d+x\d+$/.test(val) && !/^\d+p$/.test(val)) {
                 errors.push("Размер: формат должен быть '1280x720' или '720p'.");
             }
        }

        const speedVal = formData.get("speed");
        if (speedVal && (isNaN(speedVal) || parseFloat(speedVal) <= 0)) {
            errors.push("Скорость: должно быть положительное число.");
        }

        const rotateVal = formData.get("rotate");
        if (rotateVal && isNaN(rotateVal)) {
            errors.push("Поворот: должно быть число.");
        }

        const scaleVal = formData.get("scale");
        if (scaleVal && (isNaN(scaleVal) || parseFloat(scaleVal) <= 0)) {
            errors.push("Масштаб: должно быть положительное число.");
        }

        const volumeVal = formData.get("volume");
        if (volumeVal && (isNaN(volumeVal) || parseFloat(volumeVal) < 0)) {
            errors.push("Громкость: должно быть неотрицательное число.");
        }

        if (errors.length > 0) {
            alert("Пожалуйста, исправьте ошибки:\n" + errors.join("\n"));
            return;
        }

        // Показываем оверлей
        overlay.style.display = "flex";

        const fd = new FormData();

        // Добавляем видео
        if (videoInput.files.length > 0) {
            fd.append("videoFile", videoInput.files[0]);
        }

        // Добавляем остальные поля формы
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
