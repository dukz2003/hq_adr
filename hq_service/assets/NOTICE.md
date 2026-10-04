# Provenance and redistribution notice

These four binary resources were copied without modification from
`zhangbaio/hongguo`, commit `5f8a58d`, `windows-package-src`.
`manifest.json` records their SHA-256 digests; startup verifies all four.

Upstream reference: https://github.com/zhangbaio/hongguo/tree/5f8a58d/unidbg-sign

Upstream describes FqTrace as a Fanqie-overseas Metasec cross-app signer
accepted by the fqnovel backend for Hongguo requests at the time of testing.
It cites `zero199901/fqnovel-unidbg` for the native libraries/certificate.
This is not a claim that these resources originate from the latest Hongguo APK.

The upstream checkout did not include a root LICENSE. Bundling these files
for the user's local integration does not establish permission for public or
commercial redistribution. Review the original authors' and native-library
owners' terms before distributing a release containing them. Preserve this
notice and the provenance manifest. Do not upload device IDs, signatures,
CDN URLs, content keys, or account credentials into public issue reports.

Python MP4 logic follows the offline spade-v1/AES-CTR flow documented by
`frida/unwrap_spade.py`, `frida/decutil.py` in the same upstream revision;
this integration adds strict format checks, cancellable remux and full decode.
