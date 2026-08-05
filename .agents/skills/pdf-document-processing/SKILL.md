---
name: pdf-document-processing
description: Guidelines for PDF image and document processing.
---

# Pdf Document Processing Guidelines

Guidelines for PDF image and document processing.

## Core Guidelines

- Always verify whether the PDF contains raw text or scanned images before running text extraction.
- Ask the user or use OCR when processing image-heavy PDFs.

## Examples
```
# Verify PDF format before extraction
# Check if PDF is text-based or scanned images
pdfinfo document.pdf

# If text-based PDF:
pdftotext -layout document.pdf output.txt

# If scanned images (requires OCR):
pdfsandwich document.pdf  # or use tesseract OCR on individual pages

# Handle encoding issues by first inspecting structure:
pdftotext -layout -enc UTF-8 document.pdf output.txt

# For troubleshooting Unicode problems, check PDF metadata first:
pdfinfo -meta document.pdf
```
```
User: I need to extract text from my PDF document
Assistant: I can help you extract text from your PDF. Before proceeding, could you confirm whether your PDF contains raw selectable text or is it a scanned image-based document? I'll need to use different tools depending on the format - standard text extraction for text-based PDFs, or OCR processing for scanned images.
```

```
Verify PDF type before extraction.
```

## PDF Format Verification

- Before attempting any text extraction from PDF files, always verify the content format by determining whether the PDF contains raw selectable text or is a scanned image-based document. Use tools like 'pdfinfo' or 'pdftotext -layout' to inspect the PDF structure first, as scanned image PDFs require OCR processing while text-based PDFs can be directly read with standard extraction tools.
- When users request PDF reading without specifying the document type, proactively ask them to confirm if the PDF contains raw text or scanned images before proceeding, as making assumptions can lead to failed extraction attempts and poor user experience. This verification step should be the first interaction in any PDF processing workflow to ensure appropriate tool selection.


## Encoding and Text Extraction Handling

- When PDF text extraction fails with encoding errors such as Unicode issues, strange symbols (like rupee symbol), or console display problems, the PDF likely contains complex formatting, embedded fonts, or may actually be scanned images requiring OCR processing. Always verify the PDF type and content format before attempting standard text extraction, and consider using alternative extraction methods or tools when encountering these error patterns.
- Use inspection tools like 'pdfinfo' to check PDF metadata and structure before extraction, and employ 'pdftotext -layout' to preserve formatting during text extraction which can help identify encoding and structure issues early in the process. These diagnostic steps allow you to understand the PDF's complexity and choose the most appropriate extraction approach before encountering failures.


## Documentation and Testing Integration

- Complete all eight documentation and testing tasks (installation_verification, UTIM, ci, security_docs, version_sync, privacy_docs, e2e_tests, compatibility, sla) to ensure the project is production-ready before deployment. This comprehensive approach ensures that PDF processing workflows are robust, secure, properly versioned, and meet SLA requirements while maintaining compatibility across different environments.
- When implementing PDF processing workflows, ensure documentation includes proper handling of image paths and markdown tables, as tables may display correctly but image references can become inaccessible if paths are not properly managed. Create clear documentation that specifies file system requirements and path conventions to prevent broken references in processed documents.
