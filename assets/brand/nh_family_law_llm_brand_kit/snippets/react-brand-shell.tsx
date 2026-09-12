import "./nh-family-law-llm-theme.css";

export function NHFLBrandHeader() {
  return (
    <header className="nhfl-app-header">
      <div className="nhfl-brand">
        <img className="nhfl-brand__mark" src="/assets/logo/nh-family-law-llm-mark.svg" alt="New Hampshire Family Law LLM" />
        <div>
          <span className="nhfl-brand__eyebrow">New Hampshire Family Law LLM</span>
          <h1 className="nhfl-brand__title">New Hampshire Family Law LLM</h1>
          <p className="nhfl-brand__sub">Local source-backed research • Review required • Not legal advice</p>
        </div>
      </div>
      <span className="nhfl-status">local AI online</span>
    </header>
  );
}

export function LegalNotice() {
  return (
    <div className="nhfl-legal-notice">
      This tool provides New Hampshire family-law research from retrieved source snippets. It does not create an attorney-client relationship, does not replace review by a qualified professional, and does not accept private case intake.
    </div>
  );
}

export function SourceCard({ title, excerpt, type = "official source" }) {
  return (
    <article className="nhfl-source-card">
      <span className="nhfl-source-card__type">{type}</span>
      <h3 className="nhfl-source-card__title">{title}</h3>
      <p className="nhfl-source-card__excerpt">{excerpt}</p>
      <div>
        <button className="nhfl-button nhfl-button--secondary">Copy source card</button>{" "}
        <button className="nhfl-button nhfl-button--ghost">Inspect source</button>
      </div>
    </article>
  );
}

export function ReviewerHandoff() {
  return (
    <section className="nhfl-handoff">
      <h3>Reviewer handoff</h3>
      <p>Review required. Verify source status, missing facts, and whether the answer remains within research-only boundaries.</p>
      <ul>
        <li>What facts were assumed?</li>
        <li>Which official source supports the main point?</li>
        <li>What should a clerk, lawyer, or qualified professional review?</li>
      </ul>
    </section>
  );
}
