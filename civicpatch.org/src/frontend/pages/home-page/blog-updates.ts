import { html } from "lit-html";
import "../../components/panel/panel.css";
import "./blog-updates.css";
import type { BlogUpdate } from "./use-blog-updates.ts";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function renderBlogUpdates({ updates }: { updates: BlogUpdate[] }) {
  if (updates.length === 0) return "";

  return html`
    <div class="panel blog-updates">
      <div class="panel__cap">
        <b>updates</b>
        <a class="panel__cap-right" href="/blog">all updates</a>
      </div>
      <div class="blog-updates__list">
        ${updates.map(
          (post) => html`
            <article class="blog-updates__row">
              <a class="blog-updates__title" href="/blog/${post.slug}"
                >${post.title}</a
              >
              <div class="blog-updates__meta">
                ${formatDate(post.date)} by ${post.author}
              </div>
              ${post.description
                ? html`<p class="blog-updates__desc">${post.description}</p>`
                : ""}
            </article>
          `,
        )}
      </div>
    </div>
  `;
}
