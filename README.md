![App Screenshot](Screenshot.png)
# PDF Reaper v1.0

PDF Reaper is a high-performance desktop utility designed to convert web URLs and local HTML files into professional-grade PDF documents. It features an asynchronous rendering engine and multi-core compression for maximum efficiency.

## Features

- **Async Rendering**: Uses Playwright to handle JavaScript-heavy pages, lazy-loading content, and automatic cookie banner removal.
- **Parallel Processing**: Multi-threaded execution allows for simultaneous rendering of multiple sources.
- **Advanced Compression**: Utilizes the PyMuPDF engine for variable compression levels (0-100%) to optimize file size.
- **Workflow Options**:
    - **Merge**: Combine multiple sources into a single PDF document.
    - **Split**: Automatically paginate large documents into equal parts.
    - **Quick Compress**: Dedicated engine for optimizing existing PDF files on disk.
- **Modern Interface**: Built with CustomTkinter for a native dark-mode experience with Drag & Drop support.

## Installation

### Prerequisites
- Python 3.8 or higher
- Node.js (Required for Playwright browser binaries)

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/moonlightspeed/PDF-Reaper.git
   cd PDF-Reaper 
2. Install dependencies:
    ```bash
    pip install -r requirements.txt
3. Install Chromium binaries for the rendering engine:
    ```bash
    playwright install chromium

## Usage

Launch the application:
```bash
python main.py 
```

## Technical Guides

### 1. Handling Tree-Link Documentations (e.g., Unity Docs)
To convert an entire documentation tree (like the Unity Manual) into one PDF, you need a list of all sub-page URLs. Instead of copying manually, use the browser **Console Inspect**:

1. Open the documentation page (e.g., Unity Manual) in Chrome/Edge.
2. Press `F12` or `Ctrl+Shift+I` to open **Developer Tools**.
3. Go to the **Console** tab.
4. Paste the following script and press `Enter` to extract all links from the sidebar/ToC:
   ```javascript
   // Example for standard sidebars
   var links = [];
   document.querySelectorAll('a').forEach(a => {
       if (a.href.includes('Manual')) { // Filter keyword
           links.push(a.href);
       }
   });
   console.log(links.join('\n'));
5. Copy the output list and use the Quick paste links button in PDF Reaper. 
6. Enable Merge all files into one PDF to generate your offline manual.

### 2. Chromium Engine Setup
PDF Reaper requires the Chromium browser engine to render web pages.
- For Developers:
  After installing dependencies, run this command in your terminal:
```bash
playwright install chromium
```
- For End Users (Compiled version):
If you are using the .exe version, the engine is usually bundled. If the app fails to render, ensure you have an active internet connection on the first run so it can verify the internal browser binaries.

### Build Executable
To package the application for Windows:
```bash
pyinstaller --noconfirm --onedir --windowed --add-data "pdf_engine.py;." --icon "reap.ico" --name "PDF_Reaper" --collect-all playwright main.py
```

## Project Structure
- main.py: GUI and application orchestration.
- pdf_engine.py: Multi-threaded rendering and compression logic.
- reap.ico: Application icon.
- github.png: UI asset.
- requirements.txt: List of Python dependencies.

## Technical Notes
- CPU Utilization: The tool scales based on available hardware. Maximize CPU usage can be toggled to balance performance and system stability.
- Compression: Level 0 provides lossless output, while higher levels apply structural cleaning and stream deflation.

## License
Distributed under the MIT License. See LICENSE for more information.