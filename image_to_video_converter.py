import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import threading
from pathlib import Path
from typing import Optional

# Import the logger we created
from logging_config import logger

try:
    # Drag & drop support (Windows/macOS/Linux) via tkinterdnd2
    from tkinterdnd2 import TkinterDnD, DND_FILES
except Exception:
    TkinterDnD = None
    DND_FILES = None


class ImageToVideoConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("图片转视频转换器")
        self.root.geometry("600x400")
        self.root.minsize(500, 350)
        
        self.input_file: Optional[str] = None
        # 默认输出目录：与输入图片同级目录（选择文件后自动更新）
        self.output_dir: str = ""
        self.duration: tk.IntVar = tk.IntVar(value=5)  # Default 5 seconds
        
        logger.info("Application started.")
        self.setup_ui()
        self.check_ffmpeg()
    
    def setup_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Drag and drop area
        self.drop_frame = ttk.LabelFrame(main_frame, text="拖放图片到这里", padding="20")
        self.drop_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.drop_label = ttk.Label(
            self.drop_frame, 
            text="点击或拖放图片文件到此处",
            font=('Helvetica', 12)
        )
        self.drop_label.pack(expand=True)
        
        # Duration control
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(control_frame, text="视频时长 (秒):").pack(side=tk.LEFT, padx=5)
        
        duration_spin = ttk.Spinbox(
            control_frame, 
            from_=1, 
            to=60, 
            textvariable=self.duration, 
            width=5
        )
        duration_spin.pack(side=tk.LEFT, padx=5)
        
        # Output directory
        output_frame = ttk.Frame(main_frame)
        output_frame.pack(fill=tk.X, pady=5)
        
        self.output_var = tk.StringVar(value="输出目录: (将默认保存到图片所在目录)")
        ttk.Label(output_frame, textvariable=self.output_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            output_frame, 
            text="更改目录", 
            command=self.change_output_dir
        ).pack(side=tk.RIGHT, padx=5)
        
        # Convert button
        self.convert_btn = ttk.Button(
            main_frame,
            text="开始转换",
            command=self.convert,
            state=tk.DISABLED
        )
        self.convert_btn.pack(pady=10)

        # Log / error output area (shown below the button)
        log_frame = ttk.LabelFrame(main_frame, text="日志/错误信息", padding=(8, 6))
        log_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 6))

        self.log_text = tk.Text(log_frame, height=6, wrap="word")
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        # 默认只读（需要写入时临时解锁）
        self.log_text.configure(state=tk.DISABLED)

        # Status bar
        self.status_var = tk.StringVar(value="就绪")
        self.status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Bind click events (make the whole big area clickable)
        # 注意：ttk.LabelFrame 的标题区域与内部控件是不同的窗口区域，
        # 仅绑定 drop_frame 往往只能点到边框/标题附近。
        # 因此这里同时给容器与内部所有子控件都绑定点击事件。
        self._bind_click_recursive(self.drop_frame, self.browse_file)
        self._bind_hover_recursive(self.drop_frame)
        
        # Drag and drop support (tkinterdnd2)
        self._setup_drag_and_drop()
    
    def on_enter(self, event):
        self.drop_frame.configure(style='Drop.TLabelframe')
    
    def on_leave(self, event):
        self.drop_frame.configure(style='TLabelframe')
    
    def _setup_drag_and_drop(self):
        """启用拖拽上传（需要安装 tkinterdnd2）。

        说明：原生 Tkinter 不支持系统级文件拖拽。若 tkinterdnd2 不可用，
        本方法会降级为仅点击选择。
        """
        if TkinterDnD is None or DND_FILES is None:
            logger.info("tkinterdnd2 not available; drag-and-drop disabled.")
            return

        try:
            # 注册拖拽目标
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind('<<Drop>>', self.on_drop)

            # 有些情况下事件会落在内部 label 上，因此也给 label 注册
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind('<<Drop>>', self.on_drop)

            logger.info("Drag-and-drop enabled via tkinterdnd2.")
        except Exception as e:
            logger.exception("Failed to enable drag-and-drop")
            self._log_append(f"启用拖拽失败（将仅支持点击选择）：\n{str(e)}\n")

    def _parse_drop_files(self, data: str):
        """解析 tkinterdnd2 传入的文件列表字符串，返回路径列表。"""
        if not data:
            return []

        data = data.strip()

        # tkdnd 在 Windows 常见格式：
        # 1) {C:/path with space/a.jpg}
        # 2) C:/a.jpg
        # 3) {C:/a.jpg} {C:/b.jpg}
        files = []
        buf = ''
        in_brace = False
        for ch in data:
            if ch == '{':
                in_brace = True
                buf = ''
                continue
            if ch == '}':
                in_brace = False
                if buf:
                    files.append(buf)
                buf = ''
                continue
            if ch == ' ' and not in_brace:
                if buf:
                    files.append(buf)
                    buf = ''
                continue
            buf += ch
        if buf:
            files.append(buf)

        # 规范化路径（tkdnd 可能给 / 或 \ 混用）
        norm = []
        for f in files:
            f = f.strip().strip('"')
            if f:
                norm.append(os.path.normpath(f))
        return norm

    def on_drop(self, event):
        """拖拽文件到区域后的处理。"""
        try:
            paths = self._parse_drop_files(getattr(event, 'data', ''))
            if not paths:
                self._log_append("未识别到拖拽的文件路径。\n")
                return

            # 只取第一个文件
            file_path = paths[0]

            if os.path.isfile(file_path) and self.is_supported_file(file_path):
                self.set_input_file(file_path)
            else:
                self._set_status("拖拽文件无效")
                self._log_append(f"拖拽的文件不是支持的图片：{file_path}\n")
        except Exception as e:
            self._set_status("拖拽解析失败")
            self._log_append(f"处理拖拽时出错：\n{str(e)}\n")
            logger.exception("Error handling drop event")

    def _bind_click_recursive(self, widget, callback):
        """给 widget 及其所有子控件绑定左键点击。

        ttk.LabelFrame 的标题/边框与内部控件有时不会触发同一个 bind，
        所以用递归绑定确保点击“大框任意位置”都能唤起选择文件窗口。
        """
        try:
            widget.bind("<Button-1>", callback)
        except Exception:
            pass

        for child in widget.winfo_children():
            self._bind_click_recursive(child, callback)

    def _bind_hover_recursive(self, widget):
        """递归绑定 hover 效果，让整个区域鼠标移入/移出都变色。"""
        try:
            widget.bind("<Enter>", self.on_enter)
            widget.bind("<Leave>", self.on_leave)
        except Exception:
            pass

        for child in widget.winfo_children():
            self._bind_hover_recursive(child)
    
    def is_supported_file(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
    
    def browse_file(self, event=None):
        file_path = filedialog.askopenfilename(
            title="选择图片文件",
            filetypes=(
                ("图片文件", "*.jpg;*.jpeg;*.png;*.bmp;*.tiff;*.webp"),
                ("所有文件", "*.*")
            )
        )
        if file_path:
            self.set_input_file(file_path)
    
    def set_input_file(self, file_path: str):
        self.input_file = file_path
        logger.info(f"Input file selected: {file_path}")

        # 默认输出目录：输入文件同级目录
        try:
            self.output_dir = str(Path(file_path).resolve().parent)
        except Exception:
            self.output_dir = os.path.dirname(file_path)

        logger.info(f"Default output directory set to: {self.output_dir}")
        self.output_var.set(f"输出目录: {self.output_dir}")
        self.drop_label.config(text=os.path.basename(file_path))
        self.convert_btn.config(state=tk.NORMAL)
        self.status_var.set(f"已选择: {file_path}")
    
    def change_output_dir(self):
        dir_path = filedialog.askdirectory(initialdir=self.output_dir)
        if dir_path:
            self.output_dir = dir_path
            logger.info(f"Output directory changed to: {dir_path}")
            self.output_var.set(f"输出目录: {dir_path}")
    
    def _log_clear(self):
        if not hasattr(self, "log_text"):
            return
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _log_append(self, text: str):
        if not hasattr(self, "log_text"):
            return
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _set_status(self, text: str):
        self.status_var.set(text)
        # 强制刷新一次 UI：update_idletasks 仅处理绘制队列；
        # 某些情况下（尤其是打包后的 exe）需要再补一次 update，确保状态栏立刻重绘。
        try:
            self.root.update_idletasks()
            self.root.update()
        except Exception:
            pass

    def check_ffmpeg(self):
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True
        except FileNotFoundError:
            messagebox.showerror(
                "错误",
                "未找到 FFmpeg。请确保已安装 FFmpeg 并添加到系统 PATH 环境变量中。\n\n"
                "您可以从 https://ffmpeg.org/download.html 下载 FFmpeg。"
            )
            self.root.after(100, self.root.quit)  # Close the app after showing the error
            return False
    
    def convert(self):
        if not self.input_file or not os.path.exists(self.input_file):
            messagebox.showerror("错误", "请选择有效的图片文件")
            return
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
        
        input_path = Path(self.input_file)
        output_path = Path(self.output_dir) / f"{input_path.stem}.mp4"
        
        # Check if output file already exists
        if output_path.exists():
            if not messagebox.askyesno(
                "文件已存在", 
                f"文件 {output_path.name} 已存在。是否覆盖？"
            ):
                return
        
        # Build FFmpeg command
        duration = self.duration.get()
        
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output file if it exists
            "-loop", "1",
            "-i", str(input_path),
            "-t", str(duration),
            "-vf", f"fps=30,scale=1920:-2:force_original_aspect_ratio=decrease,format=yuv420p",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-f", "mp4",
            str(output_path)
        ]
        
        logger.info(f"Starting conversion. Input: {input_path}, Output: {output_path}, Duration: {duration}s")
        ffmpeg_cmd_str = " ".join(cmd)
        logger.info("FFmpeg command: " + ffmpeg_cmd_str)

        self._log_clear()
        self._log_append("FFmpeg 指令:\n" + ffmpeg_cmd_str + "\n\n")
        self._set_status("正在转换...")

        # 转换期间禁用按钮，避免重复启动多个 ffmpeg
        self.convert_btn.config(state=tk.DISABLED)
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                creationflags=(subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
            )

            logger.info("Started ffmpeg process, waiting in background thread...")

            def worker_wait():
                try:
                    out, err = process.communicate()
                    return_code = process.returncode

                    file_ok = output_path.exists() and output_path.stat().st_size > 0
                    logger.info(
                        f"FFmpeg exited. return_code={return_code}, file_ok={file_ok}, output_exists={output_path.exists()}"
                    )

                    def update_ui():
                        if return_code == 0 and file_ok:
                            self._set_status(f"转换完成: {output_path}")
                            self._log_append(
                                f"转换成功！\n输出文件: {output_path}\n大小: {output_path.stat().st_size} bytes\n"
                            )
                            logger.info(
                                f"Conversion succeeded. Output file: {output_path} ({output_path.stat().st_size} bytes)"
                            )

                            # 恢复按钮
                            self.convert_btn.config(state=tk.NORMAL)

                            # 弹窗前再刷新一次 UI，避免视觉上状态栏未更新
                            self.root.update_idletasks()

                            messagebox.showinfo(
                                "成功",
                                f"视频已保存到:\n{output_path}"
                            )
                            os.startfile(output_path.parent)
                        else:
                            self._set_status("转换失败")
                            debug = []
                            debug.append("转换失败（请查看下方日志/错误信息）\n")
                            debug.append("FFmpeg 命令:\n" + " ".join(cmd))
                            debug.append(f"返回码: {return_code}")
                            if output_path.exists():
                                debug.append(f"输出文件大小: {output_path.stat().st_size} bytes")
                            else:
                                debug.append("输出文件不存在")
                            if err:
                                debug.append("\nFFmpeg 错误输出(stderr):\n" + err)
                            if out:
                                debug.append("\nFFmpeg 标准输出(stdout):\n" + out)

                            # 写到 UI 下方日志框
                            self._log_append("\n\n".join(debug) + "\n")

                            logger.error(
                                "Conversion failed. " + " | ".join([d.replace("\n", " ") for d in debug])
                            )
                            if err:
                                logger.error("FFmpeg stderr:\n" + err)
                            if out:
                                logger.info("FFmpeg stdout:\n" + out)

                            # 恢复按钮（允许重试）
                            self.convert_btn.config(state=tk.NORMAL)

                    # 必须切回主线程更新 Tk UI
                    self.root.after(0, update_ui)

                except Exception as e:
                    logger.exception("worker_wait exception")

                    def update_ui_error():
                        self._set_status("转换失败")
                        self._log_append(f"等待 FFmpeg 结束时发生异常:\n{str(e)}\n")
                        try:
                            self.convert_btn.config(state=tk.NORMAL)
                        except Exception:
                            pass

                    self.root.after(0, update_ui_error)

            threading.Thread(target=worker_wait, daemon=True).start()
            
        except Exception as e:
            self._set_status("转换失败")
            self._log_append(f"执行 FFmpeg 时出错:\n{str(e)}\n")
            logger.exception("Exception while running FFmpeg")
            # 恢复按钮（允许重试）
            try:
                self.convert_btn.config(state=tk.NORMAL)
            except Exception:
                pass
            messagebox.showerror("错误", f"执行 FFmpeg 时出错:\n{str(e)}")


def main():
    # 若安装了 tkinterdnd2，则必须使用 TkinterDnD.Tk() 才能接收系统文件拖拽
    if TkinterDnD is not None:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    
    # Configure styles
    style = ttk.Style()
    style.configure('Drop.TLabelframe', background='#f0f0f0')
    
    app = ImageToVideoConverter(root)
    root.mainloop()


if __name__ == "__main__":
    main()
