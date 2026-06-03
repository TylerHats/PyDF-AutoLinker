# PyDF-AutoLinker

A lightweight Python post-processing utility for [Scribus](https://www.scribus.net/) PDF exports and other PDFs with stadnard text frames. 

Because the internal Scribus Python API lacks the ability to map physical text coordinates to PDF Link Annotations, automating clickable links inside Scribus is virtually impossible. This script solves that problem by running as a post-processing pipeline using PyMuPDF. It reads your "flat" PDF, intelligently maps the text coordinates, injects native clickable PDF hyperlink boxes, and automatically generates a secondary formatted copy for print-on-demand services.

## ✨ Features

This script runs in two automated passes:

**Pass 1: The "Digital/Web/Standard Print" Version (`-Online.pdf`)**
* **Smart URL & Email Injection:** Scans the document and draws physical, native PDF link annotations over text URLs and emails.
* **Line-Wrap & Gap Detection:** Intelligently stitches URLs back together even if broken across multiple lines, soft-hyphens, or layout gaps. 
* **Native PDF Links:** Uses structural PDF URI annotations. It does not alter your text formatting or print artifacts.

**Pass 2: The "Print-On-Demand" Version (`-OnDemand.pdf`)**
* **Automated Scaling:** Duplicates your original file and scales the content of every page to **98%** to fit within specific print margins.
* **Shimmy:** Automatically pushes odd pages flush-left and even pages flush-right to account for binding bleed, perfectly preparing a standard 8.5x11 layout for print on demand services with tighter content margins.

## ⚙️ Prerequisites

This script requires **Python 3** and the **PyMuPDF** library. 

Install PyMuPDF via terminal:
`pip install pymupdf`

*(Note for Ubuntu/Debian: If your OS gives you an "externally managed environment" error, you can safely force the installation by running `pip install pymupdf --break-system-packages`).*

## 🚀 Usage

1. Place `PyDFAL.py` into a dedicated folder.
2. Export your final, flat PDF and place it in the same folder.
    * **Important:** Ensure there is only *one* source PDF in this folder at a time so the script knows which file to process.
3. Run the script.

**To run via Terminal:**
Navigate to the folder and run:
`python3 compile_magazine.py`

**To run via GUI (Double-Click in Linux):**
1. Right-click `PyDFAL.py` and go to **Properties**.
2. Under **Permissions**, check the box that says **Is executable**.
3. Double-click the file in your file manager to run it instantly in the background.

## 📂 Output

If your source file is named `MyMagazine.pdf`, the script will leave your original file untouched and generate two new files in the same directory:
* `MyMagazine-Online.pdf` (Fully hyperlinked for the web)
* `MyMagazine-OnDemand.pdf` (Scaled and shifted for on demand print)

## ⚠️ Known Limitations & Testing Notes

* **Debug Mode:** By setting `DEBUG_MODE = True` in PyDFAL.py, the *-Online.pdf output file will have all automatically placed links surrounded by a thin, red box. This allows you to confirm placement and detection of URLs and email addresses before commiting a final file.
* **Browser "Helpfulness":** Modern web browsers (like Chrome and Edge) automatically detect text that looks like a URL and temporarily turn it into a clickable link. **Do not use Chrome to test if this script worked.** Chrome's fake links will mask the real ones. To verify the physical PDF link annotations were generated correctly, use a dedicated PDF reader like **Okular**, **Adobe Acrobat**, or **Foxit**, and turn off "Automatic Link Detection" in the settings.
* **Regex Boundaries:** The script uses a strict set of rules to prevent accidentally turning normal sentences into URLs. It relies heavily on standard URL punctuation (`/`, `.`, `-`, `_`, `?`, `=`, `&`). Highly unusual URLs or completely unformatted text blocks with no spacing may require manual review.
