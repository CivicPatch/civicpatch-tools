import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import { fetchNotes, createNote } from "../../api.js";
import { STORAGE_KEYS } from "../../utils/storage-keys.js";

const PER_PAGE = 10;

function NotesPanel({ jurisdictionOcdid }) {
    const [open, setOpen] = useState(
        () => localStorage.getItem(STORAGE_KEYS.NOTES_PANEL_OPEN) !== "false"
    );
    const [notes, setNotes] = useState([]);
    const [loading, setLoading] = useState(false);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [newNoteBody, setNewNoteBody] = useState("");
    const [submitting, setSubmitting] = useState(false);

    useEffect(() => {
        if (!jurisdictionOcdid) return;
        let isMounted = true;
        setLoading(true);
        fetchNotes(jurisdictionOcdid, page, PER_PAGE)
            .then(res => {
                if (!isMounted) return;
                setNotes(res.data ?? []);
                setTotalPages(res.total_pages ?? 1);
            })
            .catch(() => {})
            .finally(() => { if (isMounted) setLoading(false); });
        return () => { isMounted = false; };
    }, [jurisdictionOcdid, page]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!newNoteBody.trim() || submitting) return;
        setSubmitting(true);
        try {
            await createNote(jurisdictionOcdid, newNoteBody.trim());
            setNewNoteBody("");
            setPage(1);
            const res = await fetchNotes(jurisdictionOcdid, 1, PER_PAGE);
            setNotes(res.data ?? []);
            setTotalPages(res.total_pages ?? 1);
        } catch (_) {
            // let it fail silently; the user sees nothing change
        } finally {
            setSubmitting(false);
        }
    };

    const formatDate = (iso) => {
        if (!iso) return "";
        return new Date(iso).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
    };

    return html`
        <div class="notes-panel ${open ? "notes-panel--open" : ""}">
            <button class="notes-panel__header" @click=${() => {
                const next = !open;
                localStorage.setItem(STORAGE_KEYS.NOTES_PANEL_OPEN, String(next));
                setOpen(next);
            }}>
                <span>Notes</span>
                <i class="fa-solid ${open ? "fa-chevron-up" : "fa-chevron-down"}"></i>
            </button>
            ${open ? html`
                <div class="notes-panel__body">
                    ${loading
                        ? html`<p class="notes-panel__loading">Loading…</p>`
                        : notes.length === 0
                            ? html`<p class="notes-panel__empty">No notes yet.</p>`
                            : html`
                                <ul class="notes-panel__list">
                                    ${notes.map(note => html`
                                        <li class="notes-panel__item">
                                            <div class="notes-panel__item-body">${note.body}</div>
                                            <div class="notes-panel__item-meta">
                                                ${note.avatar_url ? html`<img class="notes-panel__avatar" src="${note.avatar_url}" alt="" />` : ""}
                                                ${note.profile_url && note.display_name
                                                    ? html`<a class="notes-panel__author" href="${note.profile_url}" target="_blank" rel="noopener noreferrer">${note.display_name}</a>`
                                                    : note.display_name ?? ""}
                                                <span class="notes-panel__date">${formatDate(note.created_at)}</span>
                                            </div>
                                        </li>
                                    `)}
                                </ul>
                            `
                    }
                    ${totalPages > 1 ? html`
                        <div class="notes-panel__pagination">
                            <button
                                class="btn-sm"
                                ?disabled=${page <= 1}
                                @click=${() => setPage(p => p - 1)}
                            >← Prev</button>
                            <span class="notes-panel__page-info">${page} / ${totalPages}</span>
                            <button
                                class="btn-sm"
                                ?disabled=${page >= totalPages}
                                @click=${() => setPage(p => p + 1)}
                            >Next →</button>
                        </div>
                    ` : ""}
                    <form class="notes-panel__form" @submit=${handleSubmit}>
                        <textarea
                            class="notes-panel__textarea"
                            placeholder="Add a note…"
                            .value=${newNoteBody}
                            @input=${(e) => setNewNoteBody(e.target.value)}
                            rows="2"
                        ></textarea>
                        <button type="submit" class="btn-sm" ?disabled=${submitting || !newNoteBody.trim()}>
                            ${submitting ? "Saving…" : "Add note"}
                        </button>
                    </form>
                </div>
            ` : ""}
        </div>
    `;
}

customElements.define("civ-notes-panel", component(NotesPanel, { useShadowDOM: false }));
