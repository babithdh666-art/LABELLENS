# LabelLens

LabelLens is a local-first prototype for checking visible information on
packaged-product labels in India. It can run OCR on a JPG, JPEG, or PNG image,
lets you correct the recognized text, and checks for common label fields using
transparent rules.

It checks for:

- Maximum Retail Price (MRP)
- Net quantity and unit
- Manufacturer or packer name and possible address
- Manufacturing or packing date
- Consumer-care contact information
- Expiry or best-before wording

These findings are **not** a legal or compliance determination. Requirements
can vary by product category and applicable rules. OCR errors, cropped images,
small print, and incomplete text can produce false warnings. Always verify the
physical package and consult the rules that apply to the product.

## Requirements

- Python 3.10 or newer
- Tesseract OCR for image text extraction
- A web browser

The sample mode and manual text entry work without Tesseract.

## Run on Windows

1. Install Python from [python.org](https://www.python.org/downloads/). During
   setup, enable **Add Python to PATH**.
2. Install Tesseract OCR for Windows. Use a trusted installer and make sure
   `tesseract.exe` is added to PATH. If it is installed but not on PATH, add its
   installation folder (commonly `C:\Program Files\Tesseract-OCR`) to PATH and
   reopen the terminal.
3. Open PowerShell in the `label-lens` folder.
4. Install the Python packages:

   ```powershell
   py -m pip install -r requirements.txt
   ```

5. (Optional) Configure GroqCloud AI. Create an API key in your GroqCloud console, then set it in PowerShell for the current terminal session:

   ```powershell
   $env:GROQ_API_KEY="your_api_key_here"
   ```

   Never paste your API key into source code or share it in screenshots. This setting lasts only for the current terminal session. You can optionally set `GROQ_MODEL` to a model available to your account. If no key is configured, basic OCR and rule-based checks remain available.

6. Start the app:

   ```powershell
   py -m streamlit run app.py
   ```

7. Open the local address Streamlit prints in the terminal.

## Run in this Replit project

From the project root, start the LabelLens workflow. The source app is in
`label-lens/`; its Python dependencies are listed in that folder's
`requirements.txt`.

## Run the tests

From the `label-lens` folder:

```powershell
py -m unittest discover -s tests -v
```

The tests use fictional sample strings and do not require Tesseract or network
access.

## Privacy and limitations

- The core OCR and rule-based checks work without an AI API. Optional AI-assisted review uses GroqCloud and requires an API key, internet access, and available API quota.
- Image recognition uses Tesseract through `pytesseract`; the Python package
  alone does not install the Tesseract program.
- The app does not save uploaded images to app files or send them to an AI
  provider.
- The three demo labels are fictional and are clearly marked as sample data.
- Text matching is intentionally conservative. It may miss alternate wording,
  languages, unusual layouts, or fields not visible in the supplied image.
