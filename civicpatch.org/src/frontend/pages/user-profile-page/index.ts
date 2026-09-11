// A light, admin-only view of one user: who they are, with a link into their history (where
// rollback lives). No profile bio, no activity feed inline — just enough to confirm this is
// the right person before going further.

import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { fetchAdminUser } from "../../api.js";
import { type AdminUser, userLabel } from "./shared.js";
import { SectionNav, userSection } from "../../components/section-nav/index.js";
import "./user-profile-page.css";

interface UserProfilePageProps {
  target_user_id: string;
  username: string;
}

function UserProfilePage({ target_user_id, username }: UserProfilePageProps) {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [userLoadError, setUserLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!target_user_id) return;
    fetchAdminUser(target_user_id)
      .then((result: { data: AdminUser }) => setUser(result.data))
      .catch((err: Error) => setUserLoadError(err.message));
  }, [target_user_id]);

  const label = userLabel(user, username);

  const profilePath = `/~${username}`;

  return html`
    <main class="user-profile-page page-content">
      <div class="sectioned">
        ${SectionNav("user", userSection(username), profilePath)}
        <div class="secbody">
          <div class="user-profile-page__header">
            <h1 class="user-profile-page__title">${label}</h1>
            ${user
              ? html`
                  <dl class="user-profile-page__meta">
                    <dt>Role</dt>
                    <dd>${user.role}</dd>
                    <dt>Last login</dt>
                    <dd>
                      ${user.last_login_at
                        ? new Date(user.last_login_at).toLocaleString()
                        : "—"}
                    </dd>
                  </dl>
                `
              : null}
            ${userLoadError
              ? html`<p class="user-profile-page__error">${userLoadError}</p>`
              : null}
          </div>

          <a class="history-widget" href="${profilePath}/history">
            <i class="fa-solid fa-clock-rotate-left history-widget__icon"></i>
            <span class="history-widget__text">
              <span class="history-widget__title">History</span>
              <span class="history-widget__hint">View edits and roll back changes</span>
            </span>
            <i class="fa-solid fa-arrow-right history-widget__arrow"></i>
          </a>
        </div>
      </div>
    </main>
  `;
}

customElements.define(
  "user-profile-page",
  component(UserProfilePage as any, {
    useShadowDOM: false,
    observedAttributes: ["target_user_id", "username"],
  }),
);
export default UserProfilePage;
