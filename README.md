# metadati_ocr
---
*Method: `get_partial_metadati(pdf_path, output_path)`*

This method processes a PDF file to extract key metadata using Optical Character Recognition (OCR). It is designed to read scanned or image-based PDF documents, analyze their content, and return a structured JSON object containing the relevant information.

The method requires two parameters:

* `pdf_path`: the full path to the PDF file to be read.
* `json_path`: the destination path where the resulting JSON file will be saved.

The function performs the following steps:

* Converts PDF pages into images.
* Applies OCR to recognize and extract text from specific regions of interest.
* Parses and identifies critical metadata such as form codes, dates, tax codes (Codice Fiscale), and handwritten weights.
* Structures the extracted data into a clean, machine-readable JSON format for further processing or integration.

This function is ideal for automating data extraction from structured forms, especially those used in document workflows like RENTRI or similar regulatory systems.
