import React from "react";

export function NHBrandHero(): JSX.Element {
  return (
    <section className="nh-hero" aria-labelledby="nh-brand-title">
      <img src="/nh-family-law-llm-banner.png" alt="" aria-hidden="true" />
      <div style={{ padding: "1.25rem 1.5rem" }}>
        <h1 id="nh-brand-title">New Hampshire Family Law LLM</h1>
        <p>Source-grounded legal AI for New Hampshire family law.</p>
      </div>
    </section>
  );
}
