import pytest
from jobs.people_collector.steps.step_04_preprocess_page_content.clean_html import clean_html

pytestmark = pytest.mark.integration


class DummyLogger:
    def debug(self, *a): pass
    def info(self, *a): pass
    def warning(self, *a): pass
    def error(self, *a): pass


# TMM-style HTML: email link wraps an img, all nested inside divs — no text on the <a> itself.
OAK_LEAF_HTML = """
<div class="tmm_container">
  <div class="tmm_member">
    <div class="tmm_textblock">
      <div class="tmm_names"><span class="tmm_fname">Tom</span> <span class="tmm_lname">Leverentz</span></div>
      <div class="tmm_job">Mayor</div>
      <div class="tmm_scblock">
        <a class="tmm_sociallink" href="mailto:tleverentz@oakleaftexas.org" title="email">
          <img alt="email" src="https://example.org/email.png">
        </a>
      </div>
    </div>
  </div>
  <div class="tmm_member">
    <div class="tmm_textblock">
      <div class="tmm_names"><span class="tmm_fname">Mitchell</span> <span class="tmm_lname">Burnett</span></div>
      <div class="tmm_job">Place 1</div>
      <div class="tmm_scblock">
        <a class="tmm_sociallink" href="mailto:mburnett@oakleaftexas.org" title="email">
          <img alt="email" src="https://example.org/email.png">
        </a>
      </div>
    </div>
  </div>
</div>
"""


def test_clean_html_preserves_mailto_links():
    result = clean_html(DummyLogger(), OAK_LEAF_HTML)
    assert "mailto:tleverentz@oakleaftexas.org" in result
    assert "mailto:mburnett@oakleaftexas.org" in result


def test_clean_html_preserves_mailto_links_after_div_unwrap():
    """Divs are stripped by clean_html — the <a> tags must survive."""
    result = clean_html(DummyLogger(), OAK_LEAF_HTML)
    assert "<a" in result
    assert 'href="mailto:' in result
