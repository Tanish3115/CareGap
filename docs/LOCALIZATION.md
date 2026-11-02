# Interface languages

The selected language set is exactly Kannada (`kn`), Telugu (`te`), Tamil (`ta`), Malayalam (`ml`), English (`en`) and Hindi (`hi`). This supersedes the earlier suggestion to support all scheduled Indian languages.

The navigation language selector uses native language names. A valid selection persists in the browser and updates the page language and direction after hydration. Unsupported saved choices fall back to English. Only the language preference is stored locally; authentication stays in HttpOnly cookies.

English is the source interface copy. Hindi, Kannada, Telugu, Tamil and Malayalam each cover all 1003 reference entries, including consent disclosures, provenance labels, clinical workflow controls and status messages. Unknown future interface text can still fall back to English, with a visible notice whenever reference coverage is incomplete. Technical identifiers, blood groups and example email addresses remain unchanged. Complete catalog coverage is distinct from independent native-language medical review.

Patient names, document titles, original text, medication names, source quotes and recorded clinical values retain their original language. Choosing a language does not translate or reinterpret clinical records. Translations remain development copy and need native-speaker review before patient deployment.

Patient-owned local reminder preferences support the same six languages independently of the interface preference. All channel deliveries remain local mocks; messages contain a generic sign-in prompt rather than clinical details. Existing delivery history is unchanged. Migration `0018` preserves notification preferences and refuses a downgrade that would discard a newly selected language.

Run `node scripts/check_locales.cjs` from the project root to check the exact language set, complete key coverage, native scripts, damaged encoding, technical exceptions and interpolation placeholders. It also tests prototype-named unknown-text fallback and locale guards. Browser coverage verifies every language, reload persistence, invalid saved-language handling, translated authenticated controls, preservation of patient names/source titles and mobile layout. Count-based success messages retain their templates so switching languages also translates existing notices.
