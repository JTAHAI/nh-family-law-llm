# Windows Frozen/MSIX Verification Matrix

Status vocabulary: **PASS**, **FAIL**, **BLOCKED**, or **NOT RUN**. A source-tree
check is not evidence of a Windows package check.

| Gate | Required evidence | Current status |
|---|---|---|
| NH product identity | `config/product_identity.json`, source verifier | PASS |
| Frozen executable creation | Build log and executable SHA-256 | NOT RUN |
| Launch on clean Windows 11 VM | Screen recording/log, OS build | NOT RUN |
| App title/icon/theme | Screenshot from installed build | NOT RUN |
| `nhfl:` protocol activation | Activation transcript | NOT RUN |
| Offline corpus startup | Runtime log with network disabled | NOT RUN |
| Export branding | PDF/DOCX/HTML samples and hashes | NOT RUN |
| MSIX manifest validation | MakeAppx output | NOT RUN |
| Package signing | Signature chain/status | NOT RUN |
| WACK | Complete WACK report | NOT RUN |
| Install/upgrade/uninstall | Clean-machine transcript | NOT RUN |
| No Maine authority in package | Extracted-package scanner report | NOT RUN |
| Accessibility keyboard/screen reader | Test notes and defects | NOT RUN |

`packaging/windows/AppxManifest.template.xml` is a source template. Its publisher
must be replaced with the actual certificate/Store identity before packaging.
