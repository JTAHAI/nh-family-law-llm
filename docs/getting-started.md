---
layout: default
title: Get started
description: Try the fictional sample in New Hampshire Family Law LLM and learn how to create a local workspace.
permalink: /getting-started/
---

<section class="page-hero"><div class="shell"><h1>Start with the fictional sample.</h1><p class="lead">Explore the desktop workbench before you add personal records. This website provides instructions and source links.</p></div></section>
<div class="content-wrap">
  <ol class="start-steps">
    <li><h2>Open the Windows app</h2><p>Check release status and the repository for the available source and Windows build instructions. The current x64 MSIX is a qualification candidate.</p><p><a class="button button--primary" href="{{ '/release-status/' | relative_url }}">Check release status</a> <a href="{{ site.github_url }}">Open GitHub</a></p></li>
    <li><h2>Build and open the sample</h2><p>In the launcher, choose the fictional NH sample option. Open Local AI Chat and use the sample matter to inspect records and supporting excerpts.</p></li>
    <li><h2>Choose your source scope</h2><p>Ask about the active matter or consult admitted New Hampshire authority separately. Open the source card and check the exact support, date, and jurisdiction.</p></li>
    <li><h2>Create your own local matter</h2><p>When you are ready, create a new case corpus and select the documents you want to include. Check the active matter before importing, drafting, or exporting.</p></li>
  </ol>

  <details class="setup-details">
    <summary>Run from source on Windows</summary>
    <p>Open the copy of the repository on your PC and follow the versioned Windows setup instructions.</p>
    <p><a href="{{ site.github_url }}/blob/{{ site.release.source_ref }}/README.md#quick-start">Open the Windows source instructions</a></p>
  </details>
  <details class="setup-details">
    <summary>Troubleshoot a local launch</summary>
    <p>Use <strong>Repair / Troubleshoot</strong> in the launcher. Logs are under <code>%LOCALAPPDATA%\NHFamilyLawLLM\logs</code>. Remove private details before sharing a log or screenshot.</p>
  </details>
  <p><a href="{{ '/privacy/' | relative_url }}">Read the privacy policy</a> · <a href="{{ '/safety/' | relative_url }}">Understand the review safeguards</a></p>
</div>
