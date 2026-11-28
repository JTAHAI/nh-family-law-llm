---
layout: default
title: Release status
description: Current source and Windows package qualification for New Hampshire Family Law LLM.
permalink: /release-status/
---

<section class="page-hero"><div class="shell"><h1>Release status for v{{ site.release.source_version }}.</h1><p class="lead">Source, installed Windows testing, and Store distribution have separate release records.</p></div></section>
<div class="content-wrap">
  <dl class="release-facts">
    <div><dt>Current published source</dt><dd>v{{ site.release.source_version }}</dd><dd><a href="{{ site.github_url }}/tree/{{ site.release.source_ref }}">View the versioned source</a></dd></div>
    <div><dt>Windows test candidate</dt><dd>{{ site.release.package_version }} · x64</dd><dd><a href="{{ site.release.qualification_url }}">Clean Windows test evidence</a></dd></div>
    <div><dt>Microsoft Store</dt><dd>NH candidate in qualification</dd><dd><a href="{{ site.github_url }}/blob/{{ site.release.source_ref }}/docs/RELEASE_BLOCKERS.md">View the release blockers</a></dd></div>
  </dl>
  <h2>Windows testing</h2>
  <p>The shared-core candidate passed clean installation, restart, uninstall, reinstall, OCR, and transcription on an offline Windows 11 VM. WACK recorded 23 passes and one optional “Blocked executables” failure. The project’s engineering release gate remains blocked. <a href="{{ site.release.qualification_url }}">Read the package qualification record</a>.</p>
  <h2>Version 8.0.10 changes</h2>
  <p>The NH release work covers the corrected package identity, bounded chat layout, fictional sample, and source and privacy safeguards.</p>
  <p><a href="{{ site.github_url }}/blob/{{ site.release.source_ref }}/docs/release-notes.md">Read the release notes</a></p>
</div>
