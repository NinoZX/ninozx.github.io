(() => {
  const input = document.querySelector("#price-search");
  const sections = [...document.querySelectorAll(".price-category")];
  const rows = sections.flatMap((section) => [
    ...section.querySelectorAll("tbody tr"),
  ]);
  const normalize = (value) =>
    value
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/đ/g, "d");
  if (input && rows.length) {
    input.closest(".price-search")?.removeAttribute("hidden");
    const status = document.createElement("p");
    status.className = "price-search-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    input.closest(".price-search").after(status);
    const empty = document.createElement("p");
    empty.className = "price-empty";
    empty.textContent =
      "Nema usluga za ovaj pojam. Pokušajte s nazivom usluge ili duljinom kose.";
    empty.hidden = true;
    status.after(empty);
    const filter = () => {
      const terms = normalize(input.value.trim()).split(/\s+/).filter(Boolean);
      let count = 0;
      rows.forEach((row) => {
        const name = normalize(row.querySelector("th").textContent);
        row.hidden = !terms.every((term) => name.includes(term));
        if (!row.hidden) count += 1;
      });
      sections.forEach((section) => {
        section.hidden = ![...section.querySelectorAll("tbody tr")].some(
          (row) => !row.hidden,
        );
      });
      status.textContent = terms.length
        ? `Prikazano usluga: ${count} od ${rows.length}.`
        : `Sve usluge: ${rows.length}.`;
      empty.hidden = count > 0;
    };
    input.addEventListener("input", filter);
    document.querySelectorAll(".price-category-nav a").forEach((link) =>
      link.addEventListener("click", () => {
        input.value = "";
        filter();
      }),
    );
    filter();
  }
  const downloads = document.querySelector(".price-downloads");
  if (downloads) {
    const print = document.createElement("button");
    print.type = "button";
    print.textContent = "Ispišite cjenik";
    print.addEventListener("click", () => window.print());
    downloads.append(print);
  }
})();
