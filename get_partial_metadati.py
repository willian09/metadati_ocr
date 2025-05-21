import os
import sys
import fitz  # PyMuPDF
from PIL import Image
import json
import easyocr
import numpy as np
import cv2
import re

# Function to normalize date formats
def normalize_date(date_str):
    if not date_str or not isinstance(date_str, str):
        return ""

    # Replace dots or hyphens with slashes
    date_str = re.sub(r"[-.]", "/", date_str)

    # Split the date into day, month, and year
    parts = date_str.split("/")
    if len(parts) != 3:
        return ""

    day, month, year = parts

    # Add leading zero if necessary
    day = day.zfill(2)
    month = month.zfill(2)

    # If the year is in two digits, add "20" at the beginning
    if len(year) == 2:
        year = "20" + year

    return f"{day}/{month}/{year}"

def ocr_fir(pdf_path, json_path, page_number=0):
    
    if not os.path.exists(pdf_path):  # Check if the file exists
        print("Error: PDF file not found.")
        return
       
    doc = fitz.open(pdf_path) # Open the PDF
    if page_number >= len(doc):
        print(f'Page {page_number} does not exist in the PDF.')
        doc.close()
        return
    
    page = doc[page_number]  # Get the specified page

    # Render the page as an image to avoid black output issues
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    full_image_path = "full_page_rendered.png"
    pix.save(full_image_path)

    # Open the rendered image and resize it to A4 size
    a4_width, a4_height = 2480, 3508
    image = Image.open(full_image_path)
    image = image.resize((a4_width, a4_height), Image.LANCZOS)

    # Crop rectangles for different sections of the image
    crop_rectangles = [
        (a4_width // 2, 0, a4_width, 700),  # Crop 1 (Data e codice)
        (0, 0, 1000, 1700),  # Crop 2 (Produttore)(Impianto)(Trasportatore)(Intermediario)
        (a4_width // 2, 2900, a4_width, 3508)  # Crop 3 (nr mov e codice)
    ] 

    # Disable progress bar by setting verbose to False
    reader = easyocr.Reader(["it"], verbose=False)

    # Regular expression patterns
    rentri_pattern = r'\b[A-Z]{5} \d{6} [A-Z]{2,3}\b'
    rentri_pattern_14 = r'\b[A-Z]{5} \d{6} [A-Z]{1}\b'
    rentri_pattern_no_spaces = r'\b[A-Z]{5}[A-Za-z0-9]{6}[A-Z]{2}\b'
        
    date_pattern = r'\b\d{2}[-/.]\d{2}[-/.]\d{4}\b|\b\d{2}[-/.]\d{2}[-/.]\d{2}\b'
    
    cf_pattern = r'\b[01]\d{10}\b'
    cf_pattern_alternative = r'\b\d{11}\b|\b[A-Za-z0-9]{16}\b'
    cf_pattern_IT = r'\b[A-Za-z0-9]{2}\d{11}\b'
    
    nrMov_pattern = r'Mov\. nr\.\s(\d{3}\.\d{3})|Mov\. nr\s(\d{3}\.\d{3})|Mov\. nr\:\s(\d{3}\.\d{3})|Mov\. nr\;\s(\d{3}\.\d{3})'

    # Dictionary to store the extracted data
    extracted_data = {}

    # Process each crop
    for i, (x1, y1, x2, y2) in enumerate(crop_rectangles):
        cropped_image = image.crop((x1, y1, x2, y2))
        cropped_image_path = f'img_crop_{i+1}.png'
        cropped_image.save(cropped_image_path)

        # Perform OCR on the cropped image
        img_np = np.array(cropped_image)
        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        result = reader.readtext(img_np)
        crop_text = " ".join([text[1] for text in result])

        # Extract specific information based on crop
        if i == 0:  # Crop 1 (numero form e data emissione)

            #extracted_data["text1"] = [text[1] for text in result] # for debugging

            cod_rentri = re.findall(rentri_pattern, crop_text)
            if cod_rentri:
                cod_rentri = cod_rentri[0]
                cod_rentri = cod_rentri[:5].replace("O", "Q").replace("I", "T").replace("E", "F").replace("U", "V")+" "+cod_rentri[6:12]+" "+cod_rentri[13:].replace("O", "Q").replace("I", "T").replace("E", "F").replace("U", "V")
            else:
                cod_rentri_match = re.search(rentri_pattern_no_spaces, crop_text)
                if cod_rentri_match:
                    cod_rentri = cod_rentri_match.group(0)
                    cod_rentri_numeric_part = cod_rentri[5:11].replace('o', '0').replace('O', '0').replace('i', '1').replace('I', '1')
                    cod_rentri = f'{cod_rentri[:5].replace("O", "Q").replace("I", "T").replace("E", "F").replace("U", "V")} {cod_rentri_numeric_part} {cod_rentri[11:].replace("O", "Q").replace("I", "T").replace("E", "F").replace("U", "V")}'
                else:
                    cod_rentri = ""
           
            cod_rentri = cod_rentri[:15] if cod_rentri else ""
            extracted_data["numero_formulario"] = cod_rentri  
                                    
            date_emissione = re.findall(date_pattern, crop_text)
            extracted_data["date_emissione"] = normalize_date(date_emissione[0] if date_emissione else "")
            
        elif i == 1:  # Crop 2 (produttore_cf, impianto_cf, trasportatore_cf, intermediario_cf) 
            
            #extracted_data["text2"] = [text[1] for text in result] # for debugging
            
            crop_text = re.sub(r"\[", " [", crop_text) # Add space before '['
            crop_text = re.sub(r"\{", " {", crop_text) # Add space before '{'
            crop_text = re.sub(r"_", " _", crop_text) # Add space before '_',             
            crop_text = re.sub(r"\s+", " ", crop_text.replace(":", " ").replace("_", " ").replace(";", "1").replace(".", "")) # Remove extra spaces and replace ':', '_' and ';' with space            
            cleaned_text = re.sub(r'[^\w\s]', '', crop_text) # Remove special characters
            corrected_text = [] # New list to store corrected words
           
            #extracted_data["cleaned_text"] = cleaned_text # for debugging cleaned_text
            
            for word in cleaned_text.split():                
                substitutions = {'O': '0', 'o': '0', 'I': '1', 'i': '1'} # Mapping for replacements
                for old, new in substitutions.items(): # Loop through the replacements
                    word = word.replace(old, new) # Apply replacements   
                corrected_text.append(word)
            cleaned_text = " ".join(corrected_text)
            
            #extracted_data["cleaned_text"] = cleaned_text # for debugging cleaned_text
            
            cf_matches = re.findall(cf_pattern, cleaned_text) # First, try to find the fiscal codes using the main pattern
                
            #extracted_data["crop_text"] = crop_text # for debugging cf_matches
            
            if len(cf_matches) < 4: # If less than 4 matches are found, try to find the fiscal codes using an alternative pattern
                cf_matches = []
                matches = re.finditer(r'(Codice Fiscalej|Cocice Fiscelel|C0d1ce F1scalej|Flscalej|F1scalej|Fiscalej|Codica Flscalo|Codke Fiscale|Corlice Flscalo|Cadlicc Flscale|Cojico Fiscnlo|Corir Fi|CoceFicale|Cocice Fiscale|Cocico Fiscale|Ccdice Fiscale|codice fiscale|cocice Fiscale|Codice Fiscale|Flscole|Fiscala|Fiscalc|Fiscolo|Flscate|Fiscalo|Fiscele|Fiscnlo|Ficcalu|físcale|Fiscale|flscale|Flscale|Fiscaye|Fiscelel|fisca1e|fiscaié|físcaié|fiscaie|fiscaíe|fiscá1e|f1scale|f1scaie|f8scale|fiseale|fisoale|fiscále|fiscäle|fiscâle|fiscãle|fiscalé|fiscalè|fiscalê|fi5cale|fisçale|fizcale|fiscalee|ficale|fiscai|ficsale|fisacle|fiscvale|fiscnale)', crop_text, re.IGNORECASE)
                for match in matches:
                    start_index = match.end()
                    next_word_match = re.search(r'\b\w+\b', crop_text[start_index:])
                    if next_word_match:
                        value1 = next_word_match.group(0)
                        if len(value1) == 2: # If the next word is 2 characters long, check for the next word
                            next_start = next_word_match.end()
                            next_word2_match = re.search(r'\b\w+\b', crop_text[start_index + next_start:])
                            if next_word2_match:
                                cf_matches.append((value1 + next_word2_match.group(0)).strip())
                        else:
                            cf_matches.append(value1.strip())
            
            if len(cf_matches) < 4: # If still less than 4 matches are found, try to find the fiscal codes using the IT pattern
                cf_matches = re.findall(cf_pattern_IT, cleaned_text)
                
            #extracted_data["cf_matches"] = cf_matches # for debugging cf_matches 
                                       
            if len(cf_matches) < 4: # If still less than 4 matches are found, try to find the fiscal codes using the alternative pattern
                cf_matches = re.findall(cf_pattern_alternative, cleaned_text)
            
            if len(cf_matches) == 4:
                if (cf_matches[0] == "08443160158" or cf_matches[0] == "04636090963") and len(cf_matches[2]) != 11: # For Chanel and Gianni Versace
                    cf_matches[2] = "FRRLSN70E21D969W"
             
            #extracted_data["cf_matches"] = cf_matches # for debugging cf_matches
                      
            # Correct the fiscal codes
            corrected_cf_matches = [] # New list to store corrected fiscal codes
            for cf in cf_matches: # Loop through the matches
                
                substitutions = {'O': '0', 'o': '0', 'I': '1', 'i': '1', ';': '1', 'C': '0', 'c': '0'} # Mapping for replacements
                for old, new in substitutions.items(): # Loop through the replacements
                    cf = cf.replace(old, new) # Apply replacements
            
                if len(cf) == 13 and cf[0:2] in {'IT', '1T', 'I7', '17'}: # If the fiscal code has 13 characters and starts with items is the set, remove the first two characters
                    cf = cf[2:]
                elif len(cf) == 12 and cf[0] in {'7', '[', '{', 'J', 'j', 'L', 'l', '1', '/'}: # If the fiscal code has 12 characters and starts with items in the set, remove the first character
                    cf = cf[1:]
                elif len(cf) == 11 and cf[0] in {'b', 'p', '5', '6', '7', 'C', 'c'}: # If the fiscal code has 11 characters and starts with items in the set, remove the first character
                    cf = '0' + cf[1:]
                elif len(cf) == 10: # If the fiscal code has 10 characters, add '0' at the beginning
                    cf = "0" + cf
                              
                # Validate the corrected fiscal code
                if re.fullmatch(r'\b\d{11}\b|\b[A-Za-z0-9]{16}\b', cf):
                    if cf[0] == '7' and len(cf) == 11: # If the fiscal code starts with '7' and has 11 characters, add '1' at the beginning
                        cf = '1' + cf[1:]
                    corrected_cf_matches.append(cf)
                    
            extracted_data["produttore_cf"] = corrected_cf_matches[0] if len(corrected_cf_matches) == 4 else ""
            extracted_data["impianto_cf"] = corrected_cf_matches[1] if len(corrected_cf_matches) == 4 else ""
            extracted_data["trasportatore_cf"] = corrected_cf_matches[2] if len(corrected_cf_matches) == 4 else ""
            extracted_data["intermediario_cf"] = corrected_cf_matches[3] if len(corrected_cf_matches) == 4 else ""  
                
        elif i == 2:  # Crop 3 (nr mov e numero form se non trovato in crop 1)

            #extracted_data["text3"] = [text[1] for text in result] # for debugging
            
            mov_number = re.findall(nrMov_pattern, crop_text)
            mov_number = [next((val for val in tup if val), "") for tup in mov_number]           
            mov_number = [mov.replace(".", "").replace(":", "").replace(";", "") for mov in mov_number]
            extracted_data["numero_mov"] = mov_number[0] if mov_number else ""
            
            if extracted_data["numero_formulario"] == "":                
                cod_rentri = re.findall(rentri_pattern, crop_text)
                if cod_rentri:
                    cod_rentri = cod_rentri[0]
                    cod_rentri = cod_rentri[:5].replace("O", "Q").replace("I", "T").replace("E", "F").replace("U", "V")+" "+cod_rentri[6:12]+" "+cod_rentri[13:].replace("O", "Q").replace("I", "T").replace("E", "F").replace("U", "V")             
                else:
                    cod_rentri = ""
                
                if cod_rentri == "":    
                    cod_rentri_match = re.search(rentri_pattern_no_spaces, crop_text)
                    if cod_rentri_match:
                        cod_rentri = cod_rentri_match.group(0)
                        cod_rentri_numeric_part = cod_rentri[5:11].replace('o', '0').replace('O', '0').replace('i', '1').replace('I', '1')
                        cod_rentri = f'{cod_rentri[:5].replace("O", "Q").replace("I", "T").replace("E", "F").replace("U", "V")} {cod_rentri_numeric_part} {cod_rentri[11:].replace("O", "Q").replace("I", "T").replace("E", "F").replace("U", "V")}'
                    else:                        
                        cod_rentri = ""
                
                if cod_rentri == "":
                    cod_rentri_14_match = re.findall(rentri_pattern_14, crop_text)                    
                    if cod_rentri_14_match:
                        cod_rentri = cod_rentri_14_match[0]
                        if cod_rentri[-1] == "W":
                            cod_rentri = cod_rentri[:5].replace("O", "Q").replace("I", "T").replace("E", "F").replace("U", "V")+cod_rentri[5:12]+ " VV"
                        else:
                            cod_rentri = ""
                    else:
                        cod_rentri = ""
                
                cod_rentri = cod_rentri[:15] if cod_rentri else ""
                extracted_data["numero_formulario"] = cod_rentri  
    
    # Cleanup: remove temporary files    
    os.remove(full_image_path)
    for i in range(len(crop_rectangles)):
        os.remove(f"img_crop_{i+1}.png")
    
    if (extracted_data["numero_formulario"] == "" and
        extracted_data["date_emissione"] == "" and
        extracted_data["produttore_cf"] == "" and
        extracted_data["impianto_cf"] == "" and
        extracted_data["trasportatore_cf"] == "" and
        extracted_data["intermediario_cf"] == "" and
        extracted_data["numero_mov"] == "" and
        page_number == 0 and
        len(doc) > 1):
        ocr_fir(pdf_path, json_path, page_number=1)  # Process the next page if the first page is empty
        return
    
    # Close the PDF document
    doc.close()  
               
    # Create the output JSON
    json_result = json.dumps(extracted_data, ensure_ascii=False, indent=4)
    
    # Print the JSON result (formatted)
    print(json_result)

    # Save the JSON file to the specified path
    json_dir = os.path.dirname(json_path)
    os.makedirs(json_dir, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as json_file:
        json_file.write(json_result)

# Script execution
if __name__ == "__main__":
    if len(sys.argv) > 2:
        ocr_fir(sys.argv[1], sys.argv[2], page_number=0)
    else:
        print("Please provide the PDF file path and the JSON file path as arguments.")