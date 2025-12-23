const scene = new THREE.Scene();
const container = document.getElementById('three-container');
const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setSize(container.clientWidth, container.clientHeight);
container.appendChild(renderer.domElement);

const light = new THREE.AmbientLight(0xffffff, 2);
scene.add(light);
camera.position.z = 5;

document.getElementById('file-selector').addEventListener('change', function(e) {
    const file = e.target.files[0];
    const url = URL.createObjectURL(file);

    if (file.name.endsWith('.glb') || file.name.endsWith('.gltf')) {
        const loader = new THREE.GLTFLoader();
        loader.load(url, (gltf) => {
            scene.clear();
            scene.add(light);
            scene.add(gltf.scene);
            animate();
        }, undefined, (err) => console.error("Load error:", err));
    }
});

function animate() {
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
}
const aiToggle = document.getElementById("ai-shutoff");
const statusDot = document.querySelector(".status-dot");
const statusText = document.querySelector(".status-text");

aiToggle.addEventListener("change", () => {
    if (aiToggle.checked) {
        statusDot.className = "status-dot error";
        statusText.textContent = "AI: DISABLED";
        console.warn("AI shutoff engaged — hardware commands blocked.");
    } else {
        statusDot.className = "status-dot idle";
        statusText.textContent = "AI: IDLE";
    }
});

function setAIRunning() {
    if (!aiToggle.checked) {
        statusDot.className = "status-dot running";
        statusText.textContent = "AI: RUNNING";
    }
}
const modeIndicator = document.getElementById("mode-indicator");
const aiToggle = document.getElementById("ai-shutoff");
const statusDot = document.querySelector(".status-dot");
const statusText = document.querySelector(".status-text");

const toolButtons = document.querySelectorAll(".tool-btn");

function setStatus(state, text) {
    statusDot.className = `status-dot ${state}`;
    statusText.textContent = `AI: ${text}`;
}

function setMode(mode) {
    modeIndicator.textContent = `MODE: ${mode}`;
    console.log(`Switched to ${mode}`);
}

toolButtons.forEach(btn => {
    btn.addEventListener("click", () => {
        const action = btn.getAttribute("title");

        switch (action) {
            case "Settings":
                setMode("SETTINGS");
                alert("Settings panel coming soon");
                break;

            case "AI Tools":
                if (aiToggle.checked) {
                    alert("AI is disabled by shutoff switch.");
                    return;
                }
                setMode("AI TOOL SELECTION");
                setStatus("idle", "READY");
                break;

            case "Graphs / Analysis":
                setMode("ANALYSIS");
                setStatus("idle", "IDLE");
                break;

            case "Captured Images":
                setMode("IMAGE REVIEW");
                break;

            case "Human TEM Control":
                aiToggle.checked = true;
                setMode("HUMAN CONTROL");
                setStatus("error", "DISABLED");
                break;

            case "Automated TEM":
                if (aiToggle.checked) {
                    alert("Disable AI shutoff to enable automation.");
                    return;
                }
                setMode("AUTOMATED TEM");
                setStatus("running", "RUNNING");
                break;

            default:
                console.warn("Unknown toolbar action:", action);
        }
    });
});
