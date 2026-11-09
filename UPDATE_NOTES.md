# DocuMind Research update

## Included changes
- Main navigation page is now named **Papers Discussions**. Launch with `streamlit run Papers_Discussions.py`.
- Existing `app.py` is retained as a compatibility entry point; chat, conversation history, PDF viewer and evidence highlighting remain in place.
- PDFs uploaded in Papers Discussions are automatically registered in the shared Research Workspace library.
- Duplicate PDFs are detected by SHA-256 content hash.
- Metadata is inferred from selectable PDF text and PDF document properties: title, authors (best-effort), year, venue, DOI, abstract and keywords. The metadata form remains editable.
- Existing library records are backfilled when the same PDF is uploaded again through Papers Discussions.

## Known limitations
- Metadata extraction is heuristic and should be reviewed, especially author lists and venue names because PDF layouts vary.
- Scanned/image-only PDFs still need OCR; the library importer reports that no selectable text was found.
- The first-time upload creates the shared-library entry; existing papers already in an older Research Workspace database can be backfilled by uploading the same PDF again in Papers Discussions.
- This update does not claim that all research-analysis features are scientifically validated. Results still require checking against the cited source pages.

## Run
```bash
streamlit run Papers_Discussions.py
```
Keep your existing `.env` file private and copy it into this project folder; it is intentionally not included in the ZIP.
