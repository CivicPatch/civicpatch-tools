import "../basic/modal.js";
import "./post-form.js";
import { html } from "lit-html";
import { component } from "haunted";
import type { RoleOption } from "./posts-model.js";
import { CANCEL_EVENT } from "./post-form.js";
import { hostDispatch } from "../../utils/host-dispatch.js";

type PostAddHost = HTMLElement & {
  jurisdictionOcdid?: string;
  organizationId?: string;
  roles?: RoleOption[];
  initialRoleId?: string;
  initialDivisionOcdid?: string;
};

// The post form in its own modal, for a caller that is not already one. The form's `added` and
// `cancel` bubble out through this element.
function PostAdd(host: PostAddHost) {
  const handleClose = () => hostDispatch(host, CANCEL_EVENT);
  const form = html`<civ-post-form
    .jurisdictionOcdid=${host.jurisdictionOcdid}
    .organizationId=${host.organizationId}
    .roles=${host.roles}
    .initialRoleId=${host.initialRoleId}
    .initialDivisionOcdid=${host.initialDivisionOcdid}
  ></civ-post-form>`;

  return html`
    <civ-modal
      .title=${"Add a post"}
      .content=${form}
      .footer=${html``}
      .modalProps=${{ open: true, onClose: handleClose }}
    ></civ-modal>
  `;
}

customElements.define("civ-post-add", component(PostAdd, { useShadowDOM: false }));
