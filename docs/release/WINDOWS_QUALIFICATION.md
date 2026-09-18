# Windows qualification record

The r7 MSIX is unsigned and static package audits passed. Its frozen runtime reports the sealed `essential` feature tier and the expected runtime feature checks pass. The executable was launched on the build machine as a responsive process titled `New Hampshire Family Law LLM v8.0.10`; this is smoke evidence only, not installed-MSIX qualification.

WACK was discovered at `C:\Program Files (x86)\Windows Kits\10\App Certification Kit\appcert.exe`, but an actual WACK session was not run: the repository runner was blocked by the local unsigned-script policy and no elevated session was started. The resulting hash-bound `not_run` receipt is `dist/store-submission-v8.0.10-prelaunch-r7/evidence/wack/wack-result.json`.

Still not run or blocked: installed MSIX launch, Start menu/taskbar, protocol activation, repeated launch/port collision, upgrade/uninstall, standard-user/non-ASCII path, offline/network observation, keyboard/screen reader/high-DPI checks, and clean-machine use. Do not reclassify this build as Store-qualified until those receipts exist for the exact package hash.
