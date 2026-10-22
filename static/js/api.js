async function api(url, method = "GET", body) {
    const r = await fetch(url, { method, headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined });
    const d = await r.json().catch(() => ({}));
    if (r.status === 401 && !url.includes("/api/login")) { location.href = "/login"; }
    if (!r.ok) throw new Error(d.error || "Ocurrió un error.");
    return d;
}
function abrirMenu() {
    document.getElementById("menu").classList.add("mostrar");
    document.querySelector(".fondo").classList.add("mostrar");
    document.querySelector(".menu-btn").setAttribute("aria-expanded", "true");
}
function cerrarMenu() {
    document.getElementById("menu").classList.remove("mostrar");
    document.querySelector(".fondo").classList.remove("mostrar");
    document.querySelector(".menu-btn").setAttribute("aria-expanded", "false");
}
document.addEventListener("DOMContentLoaded", () => {
    const b = document.getElementById("btnCerrarSesion");
    if (b) b.addEventListener("click", async e => {
        e.preventDefault();
        await api("/api/logout", "POST");
        location.href = "/login";
    });
});
