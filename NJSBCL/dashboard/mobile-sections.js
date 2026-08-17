/* NJSBCL Scout — collapsible sections on mobile. Marks every top-level <section id="..."> in
   <main> as collapsible and starts it collapsed; the CSS that actually hides section content is
   scoped to the mobile nav breakpoint (780px, see styles.css), so on desktop this class has no
   visual effect and the page renders exactly as before. Only wired into pages with several
   sections worth compacting (index.html, charts.html, methodology.html) — pages with a single
   section (recap.html) don't include this script, since collapsing their only section would
   hide the whole page behind one tap. */
(function () {
  "use strict";

  document.querySelectorAll("main > section[id]").forEach((section) => {
    const h2 = section.querySelector(":scope > h2");
    if (!h2) return;
    const chevron = document.createElement("span");
    chevron.className = "collapse-chevron";
    chevron.textContent = "▾";
    h2.appendChild(chevron);
    h2.addEventListener("click", () => section.classList.toggle("collapsed"));
    section.classList.add("collapsible", "collapsed");
  });
})();
