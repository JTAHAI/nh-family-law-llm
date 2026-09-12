# Pass 8 — NH desktop source and wheel integration

Version **8.0.10**, build **80**. This is a **development checkpoint, not a
production release or a qualified Windows installer**. Four further passes are
planned; unresolved checks below are carried into that work, not declared done.

## What actually changed

The real production gateway now serves `/nh-review`, linked from the existing
workbench. The new screen uses the approved New Hampshire banner and mark, navy,
granite and red styling, a question/date/facts form, review findings, missing-fact
and authority-gap sections, a source-summary inspector, and a local JSON export.
It calls the existing NH legal-behavior engine; it is not a new made-up legal
model. No cloud/model download is needed for this deterministic review screen.
The larger chat workbench still needs its separately configured model.

The new source and status routes preserve role/tenant, loopback-origin and audit
controls. Source content is read once, bounded, hash checked and returned from
those exact bytes. Absolute paths, traversal, symlinks and malformed hashes are
rejected. Known future amendments still prevent an expired summary from being
presented as currently usable. A missing configured manifest remains an error.
Local filesystem locations are no longer exposed by the new error responses.

The UI renders untrusted strings as text, clears old findings when inputs change,
rejects array/non-object fact JSON, cancels superseded requests, and does not
save case inputs in browser storage. Its export retains review-required flags
and a hash of the exact serialized report. **Browser execution/export behavior
has not been qualified in this environment**; see the blocked-browser receipts.

Wheel packaging was repaired rather than tested from an accidental source-tree
import. The wheel includes the actual HTML/CSS/JS, images, brand resources,
reviewed authority snapshot and 19 read-only runtime configurations. Installed
module paths and the embedded manifest were verified using Python `-I` outside
source import resolution. A startup failure caused by missing deliberation
configuration was reproduced, fixed and retested; the failed receipt is kept.
The runtime UI inventory now hashes both the workbench and the review desk.

`nhfl desktop` starts the actual production ASGI gateway on `127.0.0.1` only.
It keeps ownership of its bound socket, supports an ephemeral port, reports a
process/instance-bound startup handshake and does not open a browser or contact
an external model automatically. A new fixed-view `nhfl:` URI parser rejects
arbitrary paths, arguments, query strings and command text. Its Windows manifest
registration is a **source template only**, not proof of installed activation.

The inherited publisher identifier was replaced in the example with a clearly
marked local-QA identity. The MSIX script requires an explicit development opt-in
or the separately supplied approved NH signing identity. Templates cannot create
an actual Microsoft Store registration. Source and Windows qualification scripts
and a CI workflow were added; the Windows/CI jobs have not run here.

A leftover demo citation index was removed from the development-only citation
endpoint. The unsafe legacy endpoint remains disabled in the production gateway.
Several positive NH fixtures still contained another state's structured title
and section; those were corrected and the legacy scanner extended. Synthetic
storage fixtures now preserve the production outside-source boundary without
writing QA data outside this checkout. The deliberation path guard no longer
mistakes a harmless `data` ancestor for the forbidden `programdata` directory;
actual forbidden names and the source-root boundary remain rejected.

## Recorded checks

See `artifacts/pass-08/validation-report.json` for structured results and logs.
Groups below overlap and must not be summed as a unique-test total.

| Check | Observed result |
|---|---|
| Focused Pass 6/7/8 and authority-release regressions | 86 passed |
| Existing UI/version regression batch | 84 passed |
| Production gateway boundary suite | 29 passed |
| Existing runtime/conversation/store batch | 19 passed, **3 failed**, 10 Windows-only skips |
| Wider authority-acceptance + gateway batch | 45 passed, **13 failed** |
| Synthetic Pass 7 engineering evaluation | 34/34; not attorney-reviewed gold |
| Python syntax parsing | 1,355 files; no parse errors |
| Test collection | 2,700 collected; full execution not claimed |
| Actual source-mode HTTP launch/restart | 2 launches, 20 route/behavior checks |
| Installed-wheel HTTP launch/restart | 2 launches, 20 checks; host API dependencies borrowed |
| Isolated no-dependency wheel core | Engine, activation and embedded manifest passed |
| Source/wheel packaging gate | Passed; see source-gate.json |
| Current/future capsule integrity | 37 current reviewed capsules; 2 future overlays; 76 inventory rows |
| Expanded active legacy-authority scan | No findings outside its documented exclusions |
| Live browser and offline file preview | **Blocked by administrator navigation policy** |
| Declared dependency installation | **Blocked by package-index DNS failure** |
| Windows frozen EXE, MSIX, signing, WACK, clean machine | **Not run** |

The three conversation failures reference two evaluation datasets already absent
from the supplied Pass 7 ZIP. Their absence is verified in
`input-provenance.json`; no fabricated dataset or automatic skip was substituted.
The wider authority-acceptance failures expose older fixture/source-root and
verifier-contract gaps. They remain failures in the included log. They block a
full regression or release claim and need follow-up, not a green label.

The declared dependency requirements were **not lowered to fit this host**. A
valid wheel was built with the available setuptools backend and installed without
dependencies for the isolated core test. The installed HTTP test borrowed the
host's preinstalled API dependencies through a controlled virtual environment;
it proves package/resource integration, **not** a fresh installation of the
project's pinned dependencies. Exact versions are recorded in `environment.json`.

No browser policy was bypassed. There is no claim of a screenshot-based design
review, executed browser JSON export, screen-reader session, keyboard acceptance,
Windows protocol activation, signed package, WACK or clean-machine result.

## Authority and privacy boundaries

**Zero legal authorities were added or promoted.** The existing 37 reviewed
records remain non-verbatim capsules, not downloaded originals or a complete NH
statutes/rules/forms/opinions corpus. Their hashes identify the capsule bytes, not
the original government documents. The review desk repeats that distinction.
Historical dates in engineering fixtures are intentional; a user-facing review
defaults to the actual local date and still observes the amendment gates.

Only synthetic qualification inputs were used. The private message screenshot
and the brother's identifying case facts are excluded. The ZIP contains no
model weights, private signing keys, virtual environment or Git database.

## Run from source (Windows example)

```powershell
py -3.13 -m venv dist\run-env
.\dist\run-env\Scripts\python.exe -m pip install ".[api]"
.\dist\run-env\Scripts\nhfl.exe desktop --port 8000
```

Open the printed loopback `/nh-review` address. The existing main workbench also
links to the review desk. Port `0` selects an available ephemeral port. Keep the
terminal open while using the service; stop it with Ctrl+C. Declared dependencies
must be installed successfully; their network installation could not be completed
in this build environment.

A wheel is also included under `installables/`. It is a Python distribution, not
a standalone Windows executable. The PowerShell qualification entry point is
`scripts/windows/qualify-pass-08.ps1`; it creates its own repository-local test
environments and records real results on a Windows host. It does not sign or
certify an MSIX package.

## Work carried forward

Next is the full RSA/agency coverage-audit pass with original-source acquisition
and explicit gaps, not automatic promotion. Later planned work covers case-law
and later treatment, independent attorney/editor review, then dependency, full
regression, security/accessibility and Windows release qualification. The 16
observed wider-test failures, browser restrictions and Windows gates remain
visible until actually resolved. Four planned passes is an estimate, not a
promise that unresolved release gates disappear after a counter reaches zero.

## Technical source references

These are implementation references, not family-law authorities:

- Setuptools package-data guidance: https://setuptools.pypa.io/en/stable/userguide/datafiles.html
- PyInstaller platform build boundary: https://www.pyinstaller.org/en/stable/
- Windows package identity: https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/grant-identity-to-nonpackaged-apps
- Packaged URI extensions: https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/desktop-to-uwp-extensions

The configured workflows and scripts are future verification entry points, not
receipts of work already run on GitHub or Windows. This checkpoint was edited
locally from the supplied ZIP; no GitHub repository publication is claimed.
