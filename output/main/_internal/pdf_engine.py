import os
import asyncio
import tempfile
import concurrent.futures
from datetime import datetime
import urllib.parse
import re
import fitz
from playwright.async_api import async_playwright

class PDFEngine:
    def __init__(self, app_state, log_callback, progress_callback):
        self.app_state = app_state
        self.log = log_callback
        self.progress = progress_callback
        self.max_concurrent_tabs = 5 

    async def _wait_if_paused(self):
        while self.app_state['is_paused'] and not self.app_state['is_cancelled']:
            await asyncio.sleep(0.5)

    def _get_compression_settings(self, comp_level):
        if comp_level == 0: return 0, False
        elif comp_level == 25: return 1, True
        elif comp_level == 50: return 2, True
        elif comp_level == 75: return 3, True
        else: return 4, True 

    def _extract_base_name(self, src, index):
        if src.startswith("file://"):
            base_name = os.path.basename(src).replace("file://", "")
            base_name = re.sub(r'\.html?$', '', base_name, flags=re.IGNORECASE)
        else:
            parsed = urllib.parse.urlparse(src)
            path_parts = [p for p in parsed.path.split('/') if p]
            if path_parts:
                base_name = urllib.parse.unquote(path_parts[-1])
            else:
                base_name = parsed.netloc

            base_name = re.sub(r'[\\/*?:"<>|]', "", base_name)
        
        if not base_name.strip():
            base_name = f"web_document_{index:04d}"
            
        return base_name

    async def _fetch_single_page(self, context, src, index, work_dir, total, sem):
        async with sem:
            await self._wait_if_paused()
            if self.app_state['is_cancelled']: return index, None
            
            self.log(f"[FETCH] Async Task {index+1}/{total} started: {src[:60]}...")
            page = await context.new_page()
            try:
                await page.goto(src, wait_until="networkidle", timeout=60000)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
                
                await page.add_style_tag(content="""
                    [class*='cookie'], [id*='cookie'], [class*='consent'], 
                    .modal, .overlay { display: none !important; }
                """)

                base_name = self._extract_base_name(src, index)

                if work_dir != self.app_state.get('out_dir_cache', ''): 
                    file_name = f"{index:04d}_{base_name}.pdf"
                else:
                    file_name = f"{base_name}.pdf"
                    
                out_file = os.path.join(work_dir, file_name)
                
                counter = 1
                while os.path.exists(out_file):
                    out_file = os.path.join(work_dir, f"{base_name} ({counter}).pdf")
                    counter += 1
                
                await page.pdf(path=out_file, format="A4", print_background=True)
                await page.close()
                self.log(f"  └── [SUCCESS] Rendered Task {index+1}: {os.path.basename(out_file)}")
                return index, out_file
            except Exception as e:
                await page.close()
                self.log(f"  └── [ERROR] Task {index+1} failed: {str(e)}")
                return index, None

    def _compress_single_pdf(self, file_path, garbage_val, do_deflate):
        if self.app_state['is_cancelled']: return False
        try:
            tmp_path = file_path + ".tmp"
            doc = fitz.open(file_path)
            doc.save(tmp_path, garbage=garbage_val, deflate=do_deflate)
            doc.close()
            os.replace(tmp_path, file_path)
            return True
        except:
            return False

    async def process_all(self, sources, out_dir, options):
        total_files = len(sources)
        if total_files == 0: return
        
        self.app_state['out_dir_cache'] = out_dir 
        comp_level = options['compression']
        do_merge = options['merge']
        do_split = options['split']
        use_max_cpu = options['max_cpu']
        garbage_val, do_deflate = self._get_compression_settings(comp_level)
        
        temp_dir_obj = tempfile.TemporaryDirectory() if do_merge else None
        work_dir = temp_dir_obj.name if do_merge else out_dir
        
        converted_files_dict = {} 
        
        self.log(f"\n[SYSTEM] Initializing Async Rendering Engine (Max {self.max_concurrent_tabs} concurrent streams).")
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
                
                sem = asyncio.Semaphore(self.max_concurrent_tabs)
                tasks = [self._fetch_single_page(context, src, i, work_dir, total_files, sem) for i, src in enumerate(sources)]
                
                completed_count = 0
                for task in asyncio.as_completed(tasks):
                    index, out_file = await task
                    completed_count += 1
                    self.progress(completed_count / total_files * 0.5)
                    if out_file:
                        converted_files_dict[index] = out_file
                
                await browser.close()
                self.log(f"[SYSTEM] Async Rendering Engine terminated.")
        except Exception as e:
            self.log(f"[FATAL] Engine initialization failure: {e}")

        if self.app_state['is_cancelled'] or not converted_files_dict:
            if temp_dir_obj: temp_dir_obj.cleanup()
            return

        converted_files = [converted_files_dict[i] for i in sorted(converted_files_dict.keys())]

        if do_merge:
            self.log(f"\n[MERGE] Initiating sequential merge to preserve structure...")
            merged_doc = fitz.open()
            total_merge = len(converted_files)
            for i, f in enumerate(converted_files):
                await self._wait_if_paused()
                if self.app_state['is_cancelled']: break
                try:
                    with fitz.open(f) as doc: merged_doc.insert_pdf(doc)
                except: pass
                self.progress(0.5 + ((i+1)/total_merge)*0.25)
            
            if not self.app_state['is_cancelled']:
                date_str = datetime.now().strftime("%d%m%Y_%H%M")
                merged_path = os.path.join(out_dir, f"pdf_merged_{date_str}.pdf")
                merged_doc.save(merged_path, garbage=garbage_val, deflate=do_deflate)
                merged_doc.close()
                self.log(f"[SUCCESS] Compiled merged document: {os.path.basename(merged_path)}")

                if do_split and options['split_pages'] > 0:
                    self.log("\n[SPLIT] Initiating pagination routine...")
                    step = options['split_pages']
                    doc = fitz.open(merged_path)
                    base_name = os.path.basename(merged_path).replace(".pdf", "")
                    total_pages = len(doc)
                    for i in range(0, total_pages, step):
                        await self._wait_if_paused()
                        if self.app_state['is_cancelled']: break
                        new_doc = fitz.open()
                        new_doc.insert_pdf(doc, from_page=i, to_page=min(i+step-1, total_pages-1))
                        split_path = os.path.join(out_dir, f"{base_name}_part_{i//step + 1}.pdf")
                        new_doc.save(split_path, garbage=garbage_val, deflate=do_deflate)
                        new_doc.close()
                        self.progress(0.75 + ((i+step)/total_pages)*0.25)
                    doc.close()
                    
                    try:
                        os.remove(merged_path)
                        self.log("[INFO] Base document discarded.")
                    except: pass
                    self.log("[SUCCESS] Pagination completed.")

            temp_dir_obj.cleanup()

        else:
            if comp_level > 0:
                cpu_cores = os.cpu_count() or 4
                max_workers = cpu_cores if use_max_cpu else max(1, cpu_cores // 2)
                
                self.log(f"\n[COMPRESS] Distributing workloads across CPU cores...")
                self.log(f"[INFO] Allocated Threads: {max_workers} / {cpu_cores} (Max CPU: {'ON' if use_max_cpu else 'OFF'})")
                
                loop = asyncio.get_running_loop()
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                    compress_tasks = [
                        loop.run_in_executor(pool, self._compress_single_pdf, f, garbage_val, do_deflate)
                        for f in converted_files
                    ]
                    
                    completed_count = 0
                    for task in asyncio.as_completed(compress_tasks):
                        await task
                        completed_count += 1
                        self.progress(0.5 + (completed_count/len(converted_files))*0.5)

        self.progress(1.0)
        self.log("\n[SUCCESS] ALL OPERATIONS EXECUTED SUCCESSFULLY.")