# 🎯 Tactical Block-Based Medical OCR

A precision OCR system that allows users to visually select specific blocks of medical documents for targeted Amazon Nova processing.

## 🌟 **Key Features**

### **Visual Block Selection**
- **Interactive UI** - Click and drag to select document regions
- **Real-time Preview** - See selected blocks with visual highlighting
- **Precise Coordinates** - Percentage-based positioning for accuracy
- **Multiple Blocks** - Select and process multiple regions simultaneously

### **Targeted OCR Processing**
- **Block-Specific Prompts** - Specialized Nova prompts for each block type
- **Higher Accuracy** - Focused processing improves extraction quality
- **Structured Output** - Each block returns structured JSON data
- **Error Isolation** - Failed blocks don't affect others

### **Smart Block Types**
- 🏥 **Hospital Information** - Name, address, phone, department
- 👤 **Patient Information** - Name, DOB, ID, address
- 👨‍⚕️ **Provider Information** - Name, title, license, signature
- 🩺 **Diagnosis** - Primary/secondary diagnosis, ICD codes
- 💊 **Medications** - Medications, dosages, frequencies, instructions
- 📅 **Dates** - Issue date, service date, follow-up dates
- 📝 **General Text** - Free-form text extraction

## 🚀 **How It Works**

### **Step 1: Upload Document**
```
Upload → Display → Ready for Block Selection
```

### **Step 2: Select Blocks**
1. **Click and drag** on the document to create selection rectangles
2. **Choose block type** from dropdown (patient info, diagnosis, etc.)
3. **Add custom label** for identification
4. **Click "Add Block"** to confirm selection
5. **Repeat** for multiple blocks

### **Step 3: Process Blocks**
- Click **"Process Selected Blocks"**
- Each block is cropped and sent to Nova with specialized prompts
- Results are displayed with structured data for each block

## 📋 **Usage Examples**

### **Medical Prescription Processing**
```
Block 1: Patient Info → Extract name, DOB, address
Block 2: Provider Info → Extract doctor name, license
Block 3: Medications → Extract drug names, dosages
Block 4: Dates → Extract prescription date, refill dates
```

### **Lab Report Processing**
```
Block 1: Patient Info → Patient demographics
Block 2: Hospital Info → Lab facility information
Block 3: Test Results → Specific lab values
Block 4: Provider Info → Ordering physician
```

### **Discharge Summary Processing**
```
Block 1: Patient Info → Patient details
Block 2: Diagnosis → Primary and secondary diagnoses
Block 3: Medications → Discharge medications
Block 4: Follow-up → Appointment instructions
```

## 🎯 **Advantages Over Full-Document OCR**

| Feature | Full Document OCR | Tactical Block OCR |
|---------|------------------|-------------------|
| **Accuracy** | General prompts | Specialized prompts per block |
| **Precision** | Processes everything | Processes only selected areas |
| **Control** | Automated | User-controlled selection |
| **Error Handling** | All-or-nothing | Block-level error isolation |
| **Customization** | Fixed structure | Flexible block types |
| **Performance** | Processes full image | Processes only selected regions |

## 🔧 **Technical Implementation**

### **Frontend (JavaScript)**
- **Canvas-based selection** - Drag-to-select functionality
- **Coordinate calculation** - Percentage-based positioning
- **Real-time feedback** - Visual block highlighting
- **Dynamic UI** - Add/remove blocks interactively

### **Backend (Python/Flask)**
- **Image cropping** - PIL-based block extraction
- **Targeted prompts** - Block-type-specific Nova prompts
- **Parallel processing** - Multiple blocks processed simultaneously
- **Structured output** - JSON results per block

### **AWS Integration**
- **S3 Storage** - Original images and cropped blocks
- **Nova Processing** - Specialized prompts per block type
- **Result Storage** - Combined results saved to S3

## 📊 **Block-Specific Data Structures**

### **Patient Information Block**
```json
{
  "patient_name": "John Doe",
  "date_of_birth": "1980-01-15",
  "patient_id": "P123456",
  "address": "123 Main St, City, State"
}
```

### **Hospital Information Block**
```json
{
  "hospital_name": "General Hospital",
  "hospital_address": "456 Medical Ave",
  "phone_number": "(555) 123-4567",
  "department": "Cardiology"
}
```

### **Diagnosis Block**
```json
{
  "primary_diagnosis": "Hypertension",
  "secondary_diagnosis": ["Diabetes", "High Cholesterol"],
  "icd_codes": ["I10", "E11.9"],
  "diagnosis_date": "2024-01-20"
}
```

### **Medications Block**
```json
{
  "medications": ["Lisinopril", "Metformin"],
  "dosages": ["10mg", "500mg"],
  "frequencies": ["Daily", "Twice daily"],
  "instructions": "Take with food"
}
```

## 🎮 **User Interface Guide**

### **Block Selection Controls**
- **Block Type Dropdown** - Choose the type of information to extract
- **Block Label Input** - Custom name for identification
- **Add Block Button** - Confirm block selection
- **Clear All Button** - Remove all selected blocks
- **Block Counter** - Shows number of selected blocks

### **Visual Feedback**
- **Blue Border** - Active selection in progress
- **Green Border** - Confirmed block ready for processing
- **Block Labels** - Show block names on the document
- **Resize Handles** - Adjust block boundaries (future feature)

## 🚀 **Getting Started**

### **1. Start the Application**
```bash
cd /Users/buckylee/Documents/playground/rpa_ocr
source /Users/buckylee/Documents/playground/bedrock/.env_test/bin/activate
python block_ocr_app.py
```

### **2. Open Browser**
Navigate to `http://localhost:5002`

### **3. Upload Document**
- Drag and drop or click to upload medical document
- Supported formats: PNG, JPG, JPEG, PDF, TIFF

### **4. Select Blocks**
- Click and drag on document to create selection rectangles
- Choose block type and add label
- Click "Add Block" to confirm
- Repeat for multiple blocks

### **5. Process**
- Click "Process Selected Blocks"
- Wait for Nova processing
- Review structured results for each block

## 🔍 **Use Cases**

### **Medical Records Digitization**
- **Selective Processing** - Extract only relevant sections
- **Quality Control** - Focus on critical information areas
- **Batch Processing** - Process multiple documents with consistent block patterns

### **Insurance Claims Processing**
- **Patient Verification** - Extract patient demographics
- **Provider Validation** - Extract provider information
- **Diagnosis Coding** - Extract diagnosis for coding

### **Clinical Research**
- **Data Extraction** - Extract specific data points for research
- **Quality Assurance** - Verify critical information accuracy
- **Standardization** - Consistent data structure across documents

## 🛠️ **Customization**

### **Adding New Block Types**
1. **Update block_ocr_app.py** - Add new prompt template
2. **Update HTML** - Add option to dropdown
3. **Define data structure** - Specify expected JSON output

### **Custom Prompts**
Modify the `process_block_with_nova()` function to add specialized prompts for your use case.

## 📈 **Performance Benefits**

- **Faster Processing** - Only selected regions processed
- **Higher Accuracy** - Specialized prompts per block type
- **Better Error Handling** - Block-level error isolation
- **Cost Optimization** - Process only necessary content
- **User Control** - Manual quality control through selection

## 🔒 **Security & Privacy**

- **Temporary Storage** - Images stored temporarily in S3
- **Block Isolation** - Only selected regions processed
- **Secure Transmission** - HTTPS for all communications
- **Access Control** - AWS profile-based authentication

## 🎯 **Future Enhancements**

- **Auto-Block Detection** - AI-powered automatic block identification
- **Template System** - Save and reuse block patterns
- **Batch Processing** - Process multiple documents with same block pattern
- **OCR Confidence Scoring** - Per-block confidence metrics
- **Export Options** - Multiple output formats (CSV, XML, HL7 FHIR)

---

**The Tactical Block-Based OCR system provides unprecedented control and accuracy for medical document processing, allowing users to extract exactly what they need with maximum precision.**
