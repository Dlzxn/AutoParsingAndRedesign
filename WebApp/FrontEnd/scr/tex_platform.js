document.addEventListener('DOMContentLoaded', () => {
    createParticles();
    animateAstronautTools();
});

function createParticles() {
    const particlesContainer = document.querySelector('.particles');
    const colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ffeead'];

    for(let i = 0; i < 50; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';

        particle.style.left = `${Math.random() * 100}%`;
        particle.style.width = particle.style.height =
            `${Math.random() * 3 + 2}px`;
        particle.style.background = colors[Math.floor(Math.random() * colors.length)];
        particle.style.animationDuration =
            `${Math.random() * 5 + 5}s`;
        particle.style.animationDelay =
            `${Math.random() * 5}s`;

        particlesContainer.appendChild(particle);
    }
}

function animateAstronautTools() {
    const toolbox = document.querySelector('.toolbox');
    let angle = 0;

    setInterval(() => {
        angle = (angle + 2) % 360;
        toolbox.style.transform = `rotate(${angle}deg)`;
    }, 50);
}

document.querySelector('.notify-btn').addEventListener('click', () => {
    const btn = document.querySelector('.notify-btn');
    btn.innerHTML = '✔️ Удачного поиска!';
    btn.style.background = 'linear-gradient(45deg, #4ecdc4, #45b7d1)';
    btn.style.pointerEvents = 'none';

    // Здесь можно добавить логику подписки
});