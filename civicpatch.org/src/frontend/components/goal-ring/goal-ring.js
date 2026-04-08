import "./goal-ring.css";
import { html } from "lit-html";
import { component } from "haunted";

function GoalRing({ resolved, goal }) {
  const progress = goal > 0 ? Math.min(resolved / goal, 1) : 0;
  const pct = Math.round(progress * 100);

  return html`
    <div class="goal-bar">
      <div class="goal-bar__labels">
        <span class="goal-bar__today">${resolved} / ${goal} today</span>
        <span class="goal-bar__pct">${pct}%</span>
      </div>
      <div class="goal-bar__track">
        <div class="goal-bar__fill" style="width:${pct}%"></div>
      </div>
    </div>
  `;
}

customElements.define("civ-goal-ring", component(GoalRing, { useShadowDOM: false }));
