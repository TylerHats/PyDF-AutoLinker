#!/usr/bin/env python3
import os
import re
import fitz  # PyMuPDF
import sys

# --- SETTINGS ---
DEBUG_MODE = False

fitz.TOOLS.mupdf_display_errors(False)

def error_exit(message):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)

def clean_match(text, is_email=False):
    # Strip standard punctuation from the very end of the matched block
    text = text.rstrip(".,;:!) \n\r")
    if not text:
        return ""

    parts = text.split('\n')
    valid_text = parts[0]

    # URL Continuation Heuristic
    for part in parts[1:]:
        part_clean = part.strip()
        if not part_clean:
            break

        if is_email:
            # Emails only break at the @ or .
            if valid_text.endswith('@') or valid_text.endswith('.'):
                valid_text += '\n' + part
            elif part.startswith('@') or part.startswith('.'):
                valid_text += '\n' + part
            else:
                break
        else:
            # URLs can break on hyphens, slashes, or if the next line has URL-like characters
            if valid_text.endswith('\xad') or valid_text.endswith('\u00ad') or valid_text.endswith('-'):
                valid_text += '\n' + part
            elif part.startswith('/'):
                valid_text += '\n' + part
            elif re.search(r'[0-9/=_?&+\-]', part_clean):
                # If the next line contains numbers or URL symbols, it's part of the link
                valid_text += '\n' + part
            else:
                # If it's just a normal word (like "After"), it's a new sentence. Stop here.
                break

    # Final cleanup of trailing punctuation just in case
    valid_text = valid_text.rstrip(".,;:!) \n\r")
    return valid_text

def inject_links(input_pdf, output_pdf):
    print("Starting Pass 1: Injecting hyperlinks...")
    try:
        doc = fitz.open(input_pdf)
        links_added = 0

        # --- Strict Regex Definitions ---
        # We only allow newlines if they are explicitly surrounded by URL punctuation
        PUNC_CLASS = r"[/.\-=_?&@+\xad\u00ad]"
        SAFE_NL = rf"(?:(?<={PUNC_CLASS})\n|\n(?={PUNC_CLASS}))"
        URL_CHARS = r"[a-zA-Z0-9./?=_%:\-@+&\xad\u00ad]"

        EMAIL_CHARS = r"[a-zA-Z0-9._%+\-\xad\u00ad]"
        EMAIL_PUNC = r"[.\-_\xad\u00ad@]"
        EMAIL_SAFE_NL = rf"(?:(?<={EMAIL_PUNC})\n|\n(?={EMAIL_PUNC}))"

        email_regex = re.compile(rf"(?<![a-zA-Z0-9._%+\-])(?:{EMAIL_CHARS}|{EMAIL_SAFE_NL})+@(?:{EMAIL_CHARS}|{EMAIL_SAFE_NL})+\.[a-zA-Z\xad\u00ad]{{2,}}", re.IGNORECASE)

        p1 = rf"(?:https?://\n?|www\.\n?)(?:{URL_CHARS}|{SAFE_NL})+"
        p2 = rf"\b[a-zA-Z0-9.\-\xad\u00ad]+\.(?:com|org|net|edu|gov|io|co|us|uk|ca)(?:/(?:{URL_CHARS}|{SAFE_NL})*)?"
        url_regex = re.compile(f"({p1}|{p2})", re.IGNORECASE)

        for page in doc:
            full_text = ""
            char_bboxes = []

            # Step 1: Extract every single character AND calculate missing spaces
            data = page.get_text("rawdict")
            for block in data.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    prev_rect = None
                    for span in line.get("spans", []):
                        font_size = span.get("size", 10)
                        space_thresh = font_size * 0.20 # 20% of font size is a standard gap

                        for char in span.get("chars", []):
                            c = char["c"]
                            r = fitz.Rect(char["bbox"])

                            if c == " ":
                                full_text += " "
                                char_bboxes.append(r)
                                prev_rect = r
                                continue

                            # If there's a mathematical gap between letters, inject a space
                            if prev_rect and (r.x0 - prev_rect.x1) > space_thresh:
                                full_text += " "
                                char_bboxes.append(None)

                            full_text += c
                            char_bboxes.append(r)
                            prev_rect = r

                    full_text += "\n"
                    char_bboxes.append(None)
                full_text += "\n"
                char_bboxes.append(None)

            used_indices = set()

            # Step 2: Process the mapped string
            def process_matches(pattern, is_email):
                nonlocal links_added
                for match in pattern.finditer(full_text):
                    start, end = match.span()

                    if any(i in used_indices for i in range(start, end)):
                        continue

                    raw_match_text = match.group(0)
                    valid_text = clean_match(raw_match_text, is_email)

                    if not valid_text:
                        continue

                    actual_len = len(valid_text)
                    used_indices.update(range(start, start + actual_len))

                    link_rects = []
                    for i in range(start, start + actual_len):
                        if i < len(char_bboxes):
                            rect = char_bboxes[i]
                            if rect:
                                link_rects.append(rect)

                    if not link_rects:
                        continue

                    # Merge character boxes into tight line boxes
                    link_rects.sort(key=lambda r: (round(r.y0, 1), r.x0))
                    merged_rects = []
                    current_rect = fitz.Rect(link_rects[0])

                    for r in link_rects[1:]:
                        if abs(current_rect.y0 - r.y0) < 5 and abs(current_rect.y1 - r.y1) < 5:
                            current_rect |= r
                        else:
                            merged_rects.append(current_rect)
                            current_rect = fitz.Rect(r)
                    merged_rects.append(current_rect)

                    # Fix Scribus soft-hyphens by turning them into real hyphens
                    clean_uri = valid_text.replace('\n', '').replace('\xad', '-').replace('\u00ad', '-')
                    clean_uri = clean_uri.replace('--', '-') # Prevent double hyphens

                    if is_email:
                        final_uri = f"mailto:{clean_uri}"
                    else:
                        final_uri = clean_uri if clean_uri.startswith("http") else "https://" + clean_uri

                    # Draw the links
                    for mr in merged_rects:
                        page.insert_link({"kind": fitz.LINK_URI, "from": mr, "uri": final_uri})
                        if DEBUG_MODE:
                            page.draw_rect(mr, color=(1, 0, 0), width=0.5)

                    links_added += 1

            process_matches(email_regex, is_email=True)
            process_matches(url_regex, is_email=False)

        doc.save(output_pdf)
        doc.close()
        print(f"Pass 1 Complete! Successfully created {links_added} clickable hyperlink items.")
        if DEBUG_MODE:
            print(">>> DEBUG MODE ON: Look for the red boxes in the Blurb-Online PDF! <<<")

    except Exception as e:
        error_exit(f"Failed during link injection:\n{e}")

def shrink_and_shimmy(input_pdf, output_pdf):
    print("Starting Pass 2: Formatting MagCloud layout...")
    try:
        src_doc = fitz.open(input_pdf)
        dest_doc = fitz.open()
        scale_factor = 0.98

        for i in range(len(src_doc)):
            src_page = src_doc[i]
            w = src_page.rect.width
            h = src_page.rect.height

            scaled_w = w * scale_factor
            scaled_h = h * scale_factor

            y0 = (h - scaled_h) / 2
            y1 = y0 + scaled_h

            if (i + 1) % 2 != 0:
                x0 = 0
                x1 = scaled_w
            else:
                x0 = w - scaled_w
                x1 = w

            target_rect = fitz.Rect(x0, y0, x1, y1)
            new_page = dest_doc.new_page(width=w, height=h)
            new_page.show_pdf_page(target_rect, src_doc, i)

        dest_doc.save(output_pdf)
        src_doc.close()
        dest_doc.close()
        print(f"Pass 2 Complete! Saved to: {output_pdf}")

    except Exception as e:
        error_exit(f"Failed during shrink and shimmy:\n{e}")

def main():
    pdf_files = [f for f in os.listdir('.') if f.endswith('.pdf') and 'Blurb-Online' not in f and 'MagCloud' not in f]

    if not pdf_files:
        error_exit("No source PDF found in this folder. Make sure your Scribus export is here.")

    if len(pdf_files) > 1:
        error_exit("Multiple source PDFs found. Please only keep the original Scribus export in this folder to avoid mix-ups.")

    input_file = pdf_files[0]
    base_name = os.path.splitext(input_file)[0]

    blurb_output = f"{base_name}-Blurb-Online.pdf"
    magcloud_output = f"{base_name}-MagCloud.pdf"

    print(f"Found source file: {input_file}")
    print("-" * 40)

    inject_links(input_file, blurb_output)
    print("-" * 40)
    shrink_and_shimmy(input_file, magcloud_output)

    print("-" * 40)
    print("All processes finished successfully!")

if __name__ == "__main__":
    main()
