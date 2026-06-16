# PDF Packet Builder

![CI](https://github.com/RichieGarafola/PDFMerger/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/streamlit-1.57-FF4B4B)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

A lightweight Streamlit application for merging multiple PDF files into a single, professionally ordered packet — ready for stakeholder review, delivery, or internal distribution.

Upload order becomes merge order. Encrypted, empty, oversized, or malformed files are skipped with clear messages rather than silently failing or crashing the app.

---

## Features

- **Drag-and-drop upload** — upload up to 25 PDF files at once
- **Ordered merge** — upload order is preserved exactly in the final packet
- **Validation with feedback** — per-file and batch-level checks with plain-English error messages
- **Safe filename sanitization** — the output filename is cleaned before download
- **Custom output filename** — name the packet before downloading
- **Download in one click** — no server-side storage, no accounts, no data retained
- **Docker-ready** — Dockerfile with healthcheck included
- **Tested service layer** — merge logic is fully tested without Streamlit

---

## Tech stack

| Layer | Technology |
|---|---|
| UI | [Streamlit](https://streamlit.io) |
| PDF processing | [pypdf](https://github.com/py-pdf/pypdf) |
| Runtime | Python 3.10+ |
| Container | Docker |
| CI | GitHub Actions |

---

## Project structure

```text
PDFMerger/
├── app.py                     # Streamlit UI — thin orchestration layer only
├── services/
│   ├── __init__.py
│   └── pdf_service.py         # Merge logic, validation, error handling
├── utils/
│   ├── __init__.py
│   └── file_utils.py          # Filename sanitization and formatting helpers
├── tests/
│   └── test_pdf_service.py    # Service-layer unit tests (no Streamlit dependency)
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions CI — tests on Python 3.10, 3.11, 3.12
├── .dockerignore
├── .gitignore
├── Dockerfile
├── requirements.txt
└── README.md
```

### Why this structure

- `app.py` owns only the UI. It imports and calls the service layer — no merge logic lives here.
- `services/pdf_service.py` owns validation, merge behavior, error classification, and logging.
- `utils/file_utils.py` holds reusable filename and formatting helpers.
- `tests/test_pdf_service.py` covers the merge path independently of Streamlit, so tests run in CI without a browser or display server.

---

## Local setup

### Prerequisites

- Python 3.10 or newer
- `pip`

### Steps

1. **Clone the repository**

   ```bash
   git clone https://github.com/RichieGarafola/PDFMerger.git
   cd PDFMerger
   ```

2. **Create and activate a virtual environment**

   Windows (PowerShell):

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   macOS / Linux:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Start the app**

   ```bash
   streamlit run app.py
   ```

   The app opens at `http://localhost:8501`.

---

## How to use

1. Open the app in your browser.
2. Upload one or more PDF files using the file uploader. Upload order is merge order.
3. Set the output filename in the text box (a `.pdf` extension is enforced automatically).
4. Click **Merge PDFs**.
5. Click **Download merged PDF** to save the packet.

If any file is unreadable, encrypted, empty, or oversized, it is skipped and the reason is shown in the UI. If every file fails validation, the app surfaces a clear error instead of producing an empty or corrupt output.

---

## Operational limits

| Limit | Default |
|---|---|
| Maximum files per merge | 25 |
| Maximum size per file | 25 MB |
| Maximum total upload size | 100 MB |

These limits are configured in a single `UploadLimits` dataclass in `app.py` and enforced consistently across the UI and service layer.

---

## Running tests

```bash
python -m unittest discover -s tests -v
```

All tests are in `tests/test_pdf_service.py` and cover:

- Merging multiple PDFs and verifying page count and order
- Skipping invalid or malformed files while preserving valid ones
- Rejecting batches that exceed the configured file-count limit

---

## Deployment

### Streamlit Community Cloud

1. Push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and create a new app pointing at `app.py`.
3. Streamlit Community Cloud reads `requirements.txt` automatically — no additional configuration required.

### Docker

Build and run locally:

```bash
docker build -t pdf-packet-builder .
docker run --rm -p 8501:8501 pdf-packet-builder
```

The container exposes Streamlit on port `8501` and includes a healthcheck.

---

## Architecture note

Merge logic is fully isolated in `services/pdf_service.py`. The same service can be imported by a scheduler, REST API endpoint, or automation worker without any changes — the service has no dependency on Streamlit. The current Streamlit UI is one possible front end, not an architectural requirement.

---

## Future enhancements

- [ ] Page preview thumbnails before merge
- [ ] Drag-and-drop reordering of uploaded files
- [ ] Per-file page range selection (merge only selected pages)
- [ ] Watermark or header/footer injection on merge
- [ ] REST API endpoint using the existing service layer (FastAPI)
- [ ] Support for password-protected PDFs (with user-supplied password)

---

## License

[MIT](LICENSE)
