# Reddit account export CSV profile 1.0.0

This is a local, observed-layout profile, not a Reddit-guaranteed export standard.
Its machine contract is `profile.json`. The profile binding is SHA-256 of canonical
`{profile: <parsed profile.json>, readme_sha256: <SHA-256 of README.md bytes>}`.
This binds both machine fields and the mapping rules below in normalized provenance. Both required files must have the exact ordered header. Extra ZIP
members are not opened. Duplicate selected member names, unsafe selected inputs,
invalid CSV/UTF-8, missing/extra columns, invalid/empty IDs and exceeded limits
fail the whole normalization. Files are read directly, never extracted.

The caller explicitly declares `export_subject` when these contribution files
are supplied as one account's export, or `unknown` when attribution is not
established. This is supplier context, not source verification or a native
account identity. The subject key is `source_id#export-subject` in collection
`accounts`. The archive filename, local path and current clock are never evidence.

Native comment and post IDs remain strings in distinct collections under
`urn:ahif:service:reddit`. The accepted lower-case ASCII alphanumeric spelling
includes arbitrarily large decimal-looking IDs within AHIF's key length limit.
No numeric conversion, case folding or trimming occurs.

`comments.csv` is reply/native comment; `posts.csv` is post/native submission.
`date` is the contribution date, with only the documented literal UTC spelling
converted. Invalid/unrecognized dates remain unknown with their raw spelling;
valid date-only values remain coarse. Edit state, update, acquisition, observed
and as-of times are unknown. No calendar date is taken from the archive name.

`body` and post `title` each retain their exact decoded string and CSV locator.
Locators are `member#row=N;column=NAME`, where N is the 1-based logical data row,
not a physical line (quoted newlines do not increment N). Row provenance omits
`;column=...`. CSV quoting is transport decoding, not text correction. A field
hash receipt verifies every body/title, including empty fields and exact sentinel
strings. Sentinels are stored in the namespaced metadata extension, with declared
marker interpretation; they are not presented as authored prose. No whitespace
is removed to recognize a sentinel. Whitespace-surrounded markers stay literal.

Retained body/title text has unknown completeness and lifecycle except an exact
sentinel declares deleted/removed. Title with unavailable body remains partial
scope (unknown completeness). Blank fields never prove a complete text-free post.
Body markup is preserved as `other`, variant `Reddit-export-unknown`; this is
not a claim that Reddit's dialect equals CommonMark. Quotes/code/HTML-looking
syntax remain inside the native body field; no inference identifies who wrote
embedded text. This profile **does not support prose projection into AHAS**.

The permalink route `/r/COMMUNITY/comments/POST/SLUG[/COMMENT]/` on
`reddit.com`, `www.reddit.com` or `old.reddit.com` establishes a thread root only
when its native record ID matches the row and its community matches the supplied
label. The comment `link` accepts `/r/COMMUNITY/comments/POST` (the observed export spelling) or the same route with `/SLUG/`. A supplied comment `link` must agree with the permalink root and community. Ambiguous/unrecognized routes are retained without a derived thread key.
A bare comment `parent` is a post key only when it equals that established thread
root; otherwise, with an established thread root, it is a comment key (the comment file's native parent convention). Without an established root its collection remains unresolved.
An empty parent remains unknown, not an inferred root. References need no target
row. The raw parent/link strings remain in metadata for review. No parent times
are manufactured. Community names are handle-scoped labels, not permanent IDs.
`url` is a native destination link; it is never appended to body or resolved.

IP, gilding and media columns are not normalized. Their original bytes remain in
the owner's unmodified input, bound only by the selected CSV member hashes. No
raw evidence, credentials, messages, profiles or account mappings are published.
Coverage is unknown for the supplied rows, not all lifetime contributions. No
reported account totals or rights are invented.
