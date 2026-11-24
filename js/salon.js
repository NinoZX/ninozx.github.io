"use strict";

// Progressive enhancement: navigation, details and image links work without JS.
const siteHeader = document.querySelector(".site-header");
const menuToggle = document.querySelector(".menu-toggle");
const navigation = document.querySelector("#main-nav");
const mobileMenu = window.matchMedia("(max-width: 820px)");
if (siteHeader && menuToggle && navigation) {
  const setMenuOpen = (open) => {
    menuToggle.setAttribute("aria-expanded", String(open));
    menuToggle.querySelector(".menu-label").textContent = open
      ? "Zatvori"
      : "Izbornik";
    navigation.classList.toggle("is-open", open);
  };
  menuToggle.hidden = false;
  siteHeader.classList.add("nav-enhanced");
  menuToggle.addEventListener("click", () =>
    setMenuOpen(menuToggle.getAttribute("aria-expanded") !== "true"),
  );
  navigation.addEventListener("click", (event) => {
    if (event.target.closest("a")) setMenuOpen(false);
  });
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape" &&
      menuToggle.getAttribute("aria-expanded") === "true"
    ) {
      setMenuOpen(false);
      menuToggle.focus();
    }
  });
  document.addEventListener("click", (event) => {
    if (!siteHeader.contains(event.target)) setMenuOpen(false);
  });
  mobileMenu.addEventListener("change", () => setMenuOpen(false));
}

const lightbox = document.querySelector(".lightbox");
if (lightbox && typeof lightbox.showModal === "function") {
  const image = lightbox.querySelector("img");
  const caption = lightbox.querySelector("#lightbox-caption");
  let openingLink = null;
  document.querySelectorAll(".gallery-link").forEach((link) => {
    link.addEventListener("click", (event) => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
        return;
      event.preventDefault();
      openingLink = link;
      image.src = link.href;
      image.alt = link.querySelector("img").alt;
      caption.textContent = image.alt;
      lightbox.showModal();
      document.body.classList.add("dialog-open");
    });
  });
  lightbox
    .querySelector(".lightbox-close")
    .addEventListener("click", () => lightbox.close());
  lightbox.addEventListener("click", (event) => {
    if (event.target === lightbox) lightbox.close();
  });
  lightbox.addEventListener("close", () => {
    document.body.classList.remove("dialog-open");
    openingLink?.focus();
  });
}
const copyrightYear = document.querySelector("#copyright-year");
if (copyrightYear) copyrightYear.textContent = String(new Date().getFullYear());
