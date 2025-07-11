import os
import sys
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QLineEdit, QFileDialog, QComboBox, 
                             QTextEdit, QProgressBar, QMessageBox, QGroupBox, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QColor
from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options

class FontConverterThread(QThread):
    progress_update = pyqtSignal(int)
    # Signal to emit log messages with a level (INFO, ERROR, WARN)
    log_update = pyqtSignal(str, str)
    completed = pyqtSignal(bool, str)

    """
    input_font_path: Path to the source font file
    url_text: URL for the list of common characters
    custom_text: Custom characters
    output_formats: List of formats to output
    """
    
    def __init__(self, input_font_path, url_text, custom_text, output_formats):
        super().__init__()
        self.input_font_path = input_font_path
        self.url_text = url_text
        self.custom_text = custom_text
        self.output_formats = output_formats
        
    def run(self):
        try:
            self.log_update.emit("加载字体文件...", "INFO")
            self.progress_update.emit(5)
            
            font = TTFont(self.input_font_path)
            font_name = font.get("name")
            family_name = ""
            full_name = ""
            
            # Get font name information for HTML display
            for record in font_name.names:
                if record.nameID == 1 and not family_name:  # Family name
                    if b'\000' in record.string:
                        family_name = record.string.decode('utf-16-be')
                    else:
                        family_name = record.string.decode('latin1')
                if record.nameID == 4 and not full_name:  # Full name
                    if b'\000' in record.string:
                        full_name = record.string.decode('utf-16-be')
                    else:
                        full_name = record.string.decode('latin1')
                        
            if not family_name:
                family_name = os.path.basename(self.input_font_path)
            if not full_name:
                full_name = family_name
                
            self.progress_update.emit(10)
            
            url_content = ""
            if self.url_text:
                self.log_update.emit("从URL下载字符...", "INFO")
                try:
                    response = requests.get(self.url_text, timeout=10)
                    response.raise_for_status()
                    url_content = response.text
                    self.log_update.emit(f"从URL下载了 {len(url_content)} 个字符", "INFO")
                except Exception as e:
                    self.log_update.emit(f"从URL下载失败: {str(e)}", "ERROR")
            self.progress_update.emit(20)
            
            final_text = url_content + self.custom_text
            if not final_text:
                self.log_update.emit("警告: 没有提供字符用于子集化", "WARN")
                final_text = None
            else:
                self.log_update.emit(f"使用 {len(final_text)} 个字符进行子集化", "INFO")
            
            self.progress_update.emit(30)
            options = Options()
            subsetter = Subsetter(options=options)
            
            if final_text:
                subsetter.populate(text=final_text)
                subsetter.subset(font)
            self.progress_update.emit(40)
    
            # Create result directory
            input_dir = os.path.dirname(self.input_font_path)
            result_dir = os.path.join(input_dir, "result")
            os.makedirs(result_dir, exist_ok=True)
            
            base_filename = os.path.splitext(os.path.basename(self.input_font_path))[0]
            
            # 格式扩展名映射
            extension_map = {
                "TTF": ".ttf",
                "OTF": ".otf",
                "WOFF": ".woff",
                "WOFF2": ".woff2",
                "SVG": ".svg",
                "EOT": ".eot"
            }
            
            # First, create a TTF version for subsequent conversions
            ttf_base_path = os.path.join(result_dir, f"{base_filename}-subset.ttf")
            font.save(ttf_base_path)
            saved_files = []
            self.log_update.emit(f"保存基础TTF格式...", "INFO")
            self.progress_update.emit(45)
            
            total_formats = len(self.output_formats)
            progress_per_format = 50 / total_formats if total_formats > 0 else 50 # Remaining 50% of progress is allocated to save operations
            
            # First save the basic TTF format, then convert to other formats
            ttf_output_path = os.path.join(result_dir, f"{base_filename}-subset.ttf")
            # Clear any existing flavor first
            if hasattr(font, 'flavor'):
                font.flavor = None
            font.save(ttf_output_path)
            
            # If TTF is in the output format list, add it to the saved files list
            if "TTF" in self.output_formats:
                saved_files.append(ttf_output_path)
                self.log_update.emit(f"保存TTF格式完成", "INFO")
            
            # Save font file information for HTML generation
            font_files = []
            
            # Process other formats
            for i, output_format in enumerate(self.output_formats):
                # Add TTF to the font file list if it's a selected format
                if output_format == "TTF":
                    font_files.append({
                        'format': 'TTF',
                        'path': f"{base_filename}-subset.ttf",
                        'rel_path': f"./{base_filename}-subset.ttf"
                    })
                    continue
                    
                current_format_progress = 50 + (i * progress_per_format)
                self.log_update.emit(f"转换为 {output_format} 格式...", "INFO")
                self.progress_update.emit(int(current_format_progress))
                
                output_filename = f"{base_filename}-subset{extension_map[output_format]}"
                output_path = os.path.join(result_dir, output_filename)
                
                try:
                    font_info_to_add = {
                        'format': output_format,
                        'path': output_filename,
                        'rel_path': f"./{output_filename}"
                    }
                    if output_format == "OTF":
                        # For OTF, save the TTF file as OTF
                        otf_font = TTFont(ttf_output_path)
                        # Note: This just changes the extension, it doesn't truly convert the format.
                        # Actual OTF conversion might require more specialized processing.
                        otf_font.save(output_path)
                        saved_files.append(output_path)
                        font_files.append(font_info_to_add)
                    elif output_format == "WOFF":
                        # Load TTF and set flavor to woff
                        woff_font = TTFont(ttf_output_path)
                        woff_font.flavor = "woff"
                        woff_font.save(output_path)
                        saved_files.append(output_path)
                        font_files.append(font_info_to_add)
                    elif output_format == "WOFF2":
                        # Load TTF and set flavor to woff2
                        try:
                            woff2_font = TTFont(ttf_output_path)
                            woff2_font.flavor = "woff2"
                            woff2_font.save(output_path)
                            saved_files.append(output_path)
                            font_files.append(font_info_to_add)
                        except Exception as e:
                            self.log_update.emit(f"转换WOFF2格式失败: {str(e)}", "ERROR")
                            self.log_update.emit("WOFF2转换需要安装brotli模块，请运行: pip install brotli", "WARN")
                    elif output_format == "SVG":
                        self.log_update.emit(f"注意：暂不支持SVG格式，跳过。", "WARN")
                    elif output_format == "EOT":
                        self.log_update.emit(f"注意：EOT格式需要额外工具支持，如ttf2eot。此处跳过。", "WARN")
                except Exception as e:
                    self.log_update.emit(f"转换 {output_format} 格式失败: {str(e)}", "ERROR")
                
                self.progress_update.emit(int(current_format_progress + progress_per_format / 2))
            
            # Prepare to generate HTML preview file
            self.log_update.emit("生成HTML预览文件...", "INFO")
            
            # Get the relative path of the original font to the result directory
            original_font_rel_path = self.input_font_path
            original_font_filename = os.path.basename(self.input_font_path)
            
            # Prepare test character set
            # If custom characters are empty, use some common Chinese characters for testing
            test_chars = self.custom_text[:100] if self.custom_text else "你好世界，这是字体瘦身工具的测试页面。中国北京上海广州深圳香港澳门台湾天津重庆成都武汉南京西安长沙杭州"
            
            # Add some numbers and English characters for testing
            test_extra = "0123456789 abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            
            # Generate HTML file
            html_content = self.generate_html_preview(
                family_name, 
                full_name,
                original_font_filename,
                original_font_rel_path,
                font_files,
                test_chars,
                test_extra
            )
            
            html_path = os.path.join(result_dir, "index.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            self.progress_update.emit(100)
            
            if saved_files:
                result_message = f"成功生成 {len(saved_files)} 个字体文件到 {result_dir}\n预览文件: {html_path}"
                self.completed.emit(True, result_message)
            else:
                self.completed.emit(False, "没有成功生成任何字体文件")
            
        except Exception as e:
            self.log_update.emit(f"发生严重错误: {str(e)}", "ERROR")
            self.completed.emit(False, str(e))
    
    def generate_html_preview(self, family_name, full_name, original_font_filename, original_font_rel_path, font_files, test_chars, test_extra):
        """Generates the HTML preview file"""
        
        # Create @font-face rules
        font_face_css = ""
        
        # @font-face for the original font
        font_face_css += f"""
@font-face {{
    font-family: '{family_name}-original';
    src: url('{original_font_rel_path}') format('truetype');
    font-weight: normal;
    font-style: normal;
}}
"""
        
        # @font-face for subsetted fonts
        format_to_mime = {
            'TTF': 'truetype',
            'OTF': 'opentype',
            'WOFF': 'woff',
            'WOFF2': 'woff2',
            'SVG': 'svg',
            'EOT': 'embedded-opentype'
        }
        
        # Create a comprehensive @font-face including all formats
        sources = []
        for font_file in font_files:
            src_format = format_to_mime.get(font_file['format'], 'truetype')
            sources.append(f"url('{font_file['rel_path']}') format('{src_format}')")
        
        if sources:
            combined_src = ",\n        ".join(sources)
            font_face_css += f"""
@font-face {{
    font-family: '{family_name}-subset';
    src: {combined_src};
    font-weight: normal;
    font-style: normal;
}}
"""
        
        # Create individual @font-face for each format
        for font_file in font_files:
            font_format = font_file['format']
            src_format = format_to_mime.get(font_format, 'truetype')
            font_face_css += f"""
@font-face {{
    font-family: '{family_name}-{font_format.lower()}';
    src: url('{font_file['rel_path']}') format('{src_format}');
    font-weight: normal;
    font-style: normal;
}}
"""
        
        # Generate font file size information
        font_size_info = f"""
<section class="font-sizes">
    <h2>字体文件大小对比</h2>
    <table>
        <tr>
            <th>字体文件</th>
            <th>大小</th>
        </tr>
        <tr>
            <td>{original_font_filename} (原始)</td>
            <td>{self.get_file_size(self.input_font_path)}</td>
        </tr>
"""
        for font_file in font_files:
            file_path = os.path.join(os.path.dirname(self.input_font_path), "result", font_file['path'])
            font_size_info += f"""
        <tr>
            <td>{font_file['path']} ({font_file['format']})</td>
            <td>{self.get_file_size(file_path)}</td>
        </tr>"""
        
        font_size_info += """
    </table>
</section>
"""
        
        # Generate HTML content
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{family_name} 字体瘦身预览</title>
    <style>
        {font_face_css}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
            line-height: 1.6;
            color: #333;
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        h1, h2, h3 {{
            margin: 20px 0 10px;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }}
        
        .font-info {{
            margin-bottom: 20px;
            background: #f9f9f9;
            padding: 15px;
            border-radius: 5px;
        }}
        
        .font-sizes {{
            margin: 20px 0;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        
        table, th, td {{
            border: 1px solid #ddd;
        }}
        
        th, td {{
            padding: 10px;
            text-align: left;
        }}
        
        th {{
            background-color: #f2f2f2;
        }}
        
        .font-preview {{
            display: flex;
            flex-direction: column;
            gap: 20px;
            margin: 20px 0;
        }}
        
        .preview-card {{
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 15px;
            background: white;
        }}
        
        .preview-card h3 {{
            margin-top: 0;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
            margin-bottom: 15px;
        }}
        
        .text-preview {{
            min-height: 100px;
            word-break: break-all;
        }}
        
        .preview-original {{
            font-family: '{family_name}-original', sans-serif;
        }}
        
        .preview-subset {{
            font-family: '{family_name}-subset', sans-serif;
        }}
        
        .preview-ttf {{
            font-family: '{family_name}-ttf', sans-serif;
        }}
        
        .preview-otf {{
            font-family: '{family_name}-otf', sans-serif;
        }}
        
        .preview-woff {{
            font-family: '{family_name}-woff', sans-serif;
        }}
        
        .preview-woff2 {{
            font-family: '{family_name}-woff2', sans-serif;
        }}
        
        .test-sizes {{
            margin: 20px 0;
        }}
        
        .size-example {{
            margin: 15px 0;
        }}
        
        footer {{
            margin-top: 50px;
            text-align: center;
            color: #666;
            font-size: 14px;
            border-top: 1px solid #eee;
            padding-top: 20px;
        }}
        
        @media (min-width: 768px) {{
            .font-preview {{
                flex-direction: row;
                flex-wrap: wrap;
            }}
            
            .preview-card {{
                flex: 1 0 45%;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{full_name} 字体瘦身预览</h1>
        <p>本页面用于比较原始字体与瘦身后的字体效果</p>
    </div>
    
    <div class="font-info">
        <h2>字体信息</h2>
        <p><strong>字体名称:</strong> {full_name}</p>
        <p><strong>字体族:</strong> {family_name}</p>
        <p><strong>原始文件:</strong> {original_font_filename}</p>
        <p><strong>生成格式:</strong> {', '.join([f['format'] for f in font_files])}</p>
    </div>
    
    {font_size_info}
    
    <section class="font-preview">
    <div class="preview-card">
            <h3>默认字体</h3>
            <div class="text-preview">
                <p>{test_chars}</p>
                <p>{test_extra}</p>
            </div>
        </div>
        <div class="preview-card">
            <h3>原始包</h3>
            <div class="text-preview preview-original">
                <p>{test_chars}</p>
                <p>{test_extra}</p>
            </div>
        </div>
        
        <div class="preview-card">
            <h3>瘦身包 (综合)</h3>
            <div class="text-preview preview-subset">
                <p>{test_chars}</p>
                <p>{test_extra}</p>
            </div>
        </div>
"""

        # Add a preview card for each format
        for font_file in font_files:
            font_format = font_file['format'].lower()
            html += f"""
        <div class="preview-card">
            <h3>瘦身包 ({font_file['format']})</h3>
            <div class="text-preview preview-{font_format}">
                <p>{test_chars}</p>
                <p>{test_extra}</p>
            </div>
        </div>"""
        
        html += f"""
    </section>
    
    <section class="test-sizes">
        <h2>不同字号测试</h2>
        
        <div class="size-example">
            <h3>原始包</h3>
            <p class="preview-original" style="font-size: 12px;">12px: 你好世界 Hello World 0123456789</p>
            <p class="preview-original" style="font-size: 16px;">16px: 你好世界 Hello World 0123456789</p>
            <p class="preview-original" style="font-size: 24px;">24px: 你好世界 Hello World 0123456789</p>
            <p class="preview-original" style="font-size: 36px;">36px: 你好世界 Hello World 0123456789</p>
        </div>
        
        <div class="size-example">
            <h3>瘦身包</h3>
            <p class="preview-subset" style="font-size: 12px;">12px: 你好世界 Hello World 0123456789</p>
            <p class="preview-subset" style="font-size: 16px;">16px: 你好世界 Hello World 0123456789</p>
            <p class="preview-subset" style="font-size: 24px;">24px: 你好世界 Hello World 0123456789</p>
            <p class="preview-subset" style="font-size: 36px;">36px: 你好世界 Hello World 0123456789</p>
        </div>
    </section>
    
    <footer>
        <p>由字体瘦身工具生成 - 生成时间: {self.get_current_time()}</p>
    </footer>
</body>
</html>
"""
        return html
    
    def get_file_size(self, file_path):
        """Gets file size and formats it"""
        try:
            size_bytes = os.path.getsize(file_path)
            if size_bytes < 1024:
                return f"{size_bytes} 字节"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes/1024:.2f} KB"
            else:
                return f"{size_bytes/(1024*1024):.2f} MB"
        except:
            return "未知"
    
    def get_current_time(self):
        """Gets the current time as a formatted string"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class FontConverterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("字体瘦身")
        self.setGeometry(100, 100, 800, 700) # Increased height for log
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # --- Input Group ---
        input_group = QGroupBox("选择文件")
        input_layout = QHBoxLayout()
        self.input_font_label = QLabel("未选择")
        self.browse_button = QPushButton("选择文件")
        self.browse_button.clicked.connect(self.browse_font)
        input_layout.addWidget(QLabel("字体源文件:"))
        input_layout.addWidget(self.input_font_label, 1)
        input_layout.addWidget(self.browse_button)
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)
        
        # --- Characters Group ---
        chars_group = QGroupBox("筛选字符")
        chars_layout = QVBoxLayout()
        
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("常用字列表(3500常用字):"))
        self.url_input = QLineEdit()
        default_url = "https://raw.githubusercontent.com/shinchanZ/-3500-/master/3500"
        self.url_input.setPlaceholderText(f"输入一个远程URL，例如{default_url}")
        self.url_input.setText(default_url)
        url_layout.addWidget(self.url_input)
        chars_layout.addLayout(url_layout)
        
        chars_layout.addWidget(QLabel("追加自定义字符:"))
        self.custom_chars = QTextEdit()
        example_chars = "犇骉淼焱"
        self.custom_chars.setPlaceholderText(f"添加你的自定义字符, 例如: {example_chars}")
        self.custom_chars.setMinimumHeight(80)
        chars_layout.addWidget(self.custom_chars)
        chars_group.setLayout(chars_layout)
        main_layout.addWidget(chars_group)
        
        # --- Output Group ---
        output_group = QGroupBox("输出选项")
        output_layout = QVBoxLayout()
        
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("输出格式:"))
        
        # Add output format checkboxes
        format_group_layout = QHBoxLayout()
        self.format_checkboxes = {}
        formats = ["TTF", "OTF", "WOFF", "WOFF2", "SVG", "EOT"]
        for fmt in formats:
            checkbox = QCheckBox(fmt)
            checkbox.setChecked(True)  # Checked by default
            
            # Set tooltips
            if fmt == "EOT" or fmt == "SVG":
                checkbox.setChecked(False)
                checkbox.setEnabled(False)
                checkbox.setToolTip("暂不支持")
            elif fmt == "WOFF2":
                checkbox.setText("WOFF2")
                checkbox.setToolTip("需安装brotli模块才能支持WOFF2格式")
            else:
                checkbox.setToolTip(f"转换为{fmt}格式")
                
            self.format_checkboxes[fmt] = checkbox
            format_group_layout.addWidget(checkbox)
        
        output_layout.addLayout(format_layout)
        output_layout.addLayout(format_group_layout)
        
        output_layout.addWidget(QLabel("所有文件将保存到源文件同级的 'result' 目录下"))
        
        # Add HTML preview file hint
        preview_html_label = QLabel("生成完成后，将在result目录生成index.html预览文件用于测试字体效果")
        preview_html_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        output_layout.addWidget(preview_html_label)
        
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)
        
        # --- Status and Log Group ---
        status_group = QGroupBox("状态和日志")
        status_layout = QVBoxLayout()
        self.status_label = QLabel("准备就绪")
        self.progress_bar = QProgressBar()
        
        # Add log output area
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(100)
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        status_layout.addWidget(QLabel("日志:"))
        status_layout.addWidget(self.log_output)
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        
        self.convert_button = QPushButton("开始处理")
        self.convert_button.setStyleSheet("font-size: 16px; padding: 10px;")
        self.convert_button.clicked.connect(self.start_conversion)
        main_layout.addWidget(self.convert_button)
    
        self.input_font_path = ""
        self.converter_thread = None
        
    def browse_font(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, "选择字体文件", "", "字体文件 (*.ttf *.otf *.woff *.woff2)"
        )
        if file_path:
            self.input_font_path = file_path
            self.input_font_label.setText(os.path.basename(file_path))
    
    def start_conversion(self):
        if not self.input_font_path:
            QMessageBox.warning(self, "提示", "请选择一个字体源文件。")
            return
        
        selected_formats = []
        for fmt, checkbox in self.format_checkboxes.items():
            if checkbox.isChecked():
                selected_formats.append(fmt)
        
        if not selected_formats:
            QMessageBox.warning(self, "提示", "请至少选择一种输出格式。")
            return
            
        self.progress_bar.setValue(0)
        self.log_output.clear() # Clear log on new run
        self.append_to_log("开始处理...", "INFO")
        self.convert_button.setEnabled(False)
        
        url_text = self.url_input.text().strip()
        custom_text = self.custom_chars.toPlainText()

        self.converter_thread = FontConverterThread(
            self.input_font_path, 
            url_text, 
            custom_text,
            selected_formats
        )
    
        self.converter_thread.progress_update.connect(self.update_progress)
        self.converter_thread.log_update.connect(self.append_to_log)
        self.converter_thread.completed.connect(self.conversion_completed)
        
        self.converter_thread.start()
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def append_to_log(self, message, level):
        """Appends a message to the log area with appropriate color."""
        self.status_label.setText(message) # Update the current status label
        
        if level == "ERROR":
            self.log_output.setTextColor(QColor("red"))
        elif level == "WARN":
            self.log_output.setTextColor(QColor("orange"))
        else:
            self.log_output.setTextColor(QColor("black"))
            
        self.log_output.append(message)
    
    def conversion_completed(self, success, message):
        self.convert_button.setEnabled(True)
        
        if success:
            self.append_to_log("处理成功!", "INFO")
            result_dir = os.path.join(os.path.dirname(self.input_font_path), "result")
            html_path = os.path.join(result_dir, "index.html")
            
            msg_box = QMessageBox()
            msg_box.setWindowTitle("成功")
            msg_box.setText(f"字体处理完成!\n{message}")
            msg_box.setInformativeText("是否打开预览HTML文件?")
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.Yes)
            
            if msg_box.exec_() == QMessageBox.Yes:
                # Open the HTML file
                import webbrowser
                webbrowser.open(f"file://{os.path.abspath(html_path)}")
        else:
            self.append_to_log(f"处理失败: {message}", "ERROR")
            QMessageBox.critical(
                self,
                "错误",
                f"字体处理失败: {message}"
            )

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def main():
    app = QApplication(sys.argv)
    # It's good practice to have an icon file in the same directory or provide a valid path
    # If 'font.ico' is not available, the application will run without an icon.
    icon_path = resource_path('font.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = FontConverterApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
