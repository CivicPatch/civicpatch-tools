const ACTIVE_CLASS = "blog-post__toc-link--active";

// Which heading counts as "current" flips once it crosses the upper third of
// the viewport, not only once it hits the very top.
const ROOT_MARGIN = "0px 0px -70% 0px";

function initBlogTocScrollspy() {
  const links = [...document.querySelectorAll<HTMLAnchorElement>(".blog-post__toc nav a[href^='#']")];
  if (!links.length) return;

  const linkById = new Map(links.map((link) => [link.hash.slice(1), link]));
  const headings = links
    .map((link) => document.getElementById(link.hash.slice(1)))
    .filter((el): el is HTMLElement => el !== null);
  if (!headings.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        linkById.get(entry.target.id)?.classList.toggle(ACTIVE_CLASS, entry.isIntersecting);
      }
    },
    { rootMargin: ROOT_MARGIN },
  );
  headings.forEach((heading) => observer.observe(heading));
}

if (document.querySelector(".blog-post__toc")) {
  initBlogTocScrollspy();
}
