import os
import sys
import tkinter as tk
from PIL import Image
from tkinter import ttk, filedialog, messagebox
import subprocess
import threading
from pathlib import Path
from typing import Optional

try:
    # Drag & drop support (Windows/macOS/Linux) via tkinterdnd2
    from tkinterdnd2 import TkinterDnD, DND_FILES
except Exception:
    TkinterDnD = None
    DND_FILES = None

# Import the logger we created
from logging_config import logger


def get_resource_path(relative_path: str) -> str:
    """获取资源文件路径（兼容 PyInstaller onefile/onedir）。"""
    base_path = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base_path, relative_path)


class ImageToVideoConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("图片转视频转换器")
        self.root.geometry("600x400")
        self.root.minsize(500, 350)

        self.input_file: Optional[str] = None
        # 批量队列（拖拽多个文件/文件夹时使用）
        self.input_files: list[str] = []
        # 默认输出目录：与输入图片同级目录（选择文件后自动更新）
        self.output_dir: str = ""
        self.duration: tk.IntVar = tk.IntVar(value=3)  # Default 3 seconds

        # 批量转换状态
        self._batch_total: int = 0
        self._batch_index: int = 0
        self._is_converting: bool = False

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

        # Buttons row
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        btn_frame.columnconfigure(2, weight=1)

        self.convert_btn = ttk.Button(
            btn_frame,
            text="开始转换",
            command=self.convert,
            state=tk.DISABLED
        )
        self.convert_btn.grid(row=0, column=1, padx=6)

        # Image convert controls (for .webp)
        self.img_format_var = tk.StringVar(value="png")
        self.img_format_combo = ttk.Combobox(
            btn_frame,
            textvariable=self.img_format_var,
            values=["png", "jpg"],
            width=5,
            state="disabled"
        )
        self.img_format_combo.grid(row=0, column=0, sticky=tk.E, padx=6)

        self.img_convert_btn = ttk.Button(
            btn_frame,
            text="图片转换",
            command=self.convert_image_format,
            state=tk.DISABLED
        )
        self.img_convert_btn.grid(row=0, column=2, sticky=tk.W, padx=6)

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
        self._bind_click_recursive(self.drop_frame, self.browse_file)
        self._bind_hover_recursive(self.drop_frame)

        # Drag and drop support (tkinterdnd2)
        self._setup_drag_and_drop()

    def on_enter(self, event):
        self.drop_frame.configure(style='Drop.TLabelframe')

    def on_leave(self, event):
        self.drop_frame.configure(style='TLabelframe')

    def _setup_drag_and_drop(self):
        """启用拖拽上传（需要安装 tkinterdnd2）。"""
        if TkinterDnD is None or DND_FILES is None:
            logger.info("tkinterdnd2 not available; drag-and-drop disabled.")
            return

        try:
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind('<<Drop>>', self.on_drop)

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

        norm = []
        for f in files:
            f = f.strip().strip('"')
            if f:
                norm.append(os.path.normpath(f))
        return norm

    def _collect_images_from_paths(self, paths: list[str]) -> list[str]:
        """把拖入的文件/文件夹解析成图片文件列表（支持递归遍历文件夹）。"""
        images: list[str] = []

        for p in paths:
            if not p:
                continue

            try:
                if os.path.isdir(p):
                    for root_dir, _dirs, files in os.walk(p):
                        for name in files:
                            fp = os.path.join(root_dir, name)
                            if os.path.isfile(fp) and self.is_supported_file(fp):
                                images.append(fp)
                elif os.path.isfile(p):
                    if self.is_supported_file(p):
                        images.append(p)
            except Exception:
                logger.exception(f"Failed to collect images from path: {p}")

        seen = set()
        uniq = []
        for f in images:
            if f not in seen:
                seen.add(f)
                uniq.append(f)
        return uniq

    def on_drop(self, event):
        """拖拽文件到区域后的处理：支持多文件 + 文件夹。"""
        try:
            paths = self._parse_drop_files(getattr(event, 'data', ''))
            if not paths:
                self._log_append("未识别到拖拽的文件路径。\n")
                return

            images = self._collect_images_from_paths(paths)
            if not images:
                self._set_status("未找到可用图片")
                self._log_append("拖拽内容中未找到支持的图片文件（支持：jpg/png/bmp/tiff/webp）。\n")
                return

            # 更新队列
            self.input_files = images

            # 只更新 UI 显示与默认输出目录（不要在这里调用 set_input_file，否则会把 input_files 覆盖成单张）
            self.input_file = images[0]
            try:
                self.output_dir = str(Path(images[0]).resolve().parent)
            except Exception:
                self.output_dir = os.path.dirname(images[0])

            self.output_var.set(f"输出目录: {self.output_dir}")
            self.convert_btn.config(state=tk.NORMAL)

            if len(images) == 1:
                self.drop_label.config(text=os.path.basename(images[0]))
                self._set_status(f"已选择: {images[0]}")
            else:
                self.drop_label.config(text=f"已选择 {len(images)} 张图片（将批量转换）")
                self._set_status(f"已加入队列：{len(images)} 张图片")

            self._log_append(f"已接收 {len(images)} 个图片任务（来自拖拽多文件/文件夹）。\n")
            logger.info(f"Drop received. images={len(images)}")

            # 根据是否包含 webp 启用/禁用图片转换功能
            self._update_image_convert_controls(self.input_files)

        except Exception as e:
            self._set_status("拖拽解析失败")
            self._log_append(f"处理拖拽时出错：\n{str(e)}\n")
            logger.exception("Error handling drop event")

    def _bind_click_recursive(self, widget, callback):
        try:
            widget.bind("<Button-1>", callback)
        except Exception:
            pass

        for child in widget.winfo_children():
            self._bind_click_recursive(child, callback)

    def _bind_hover_recursive(self, widget):
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

        try:
            self.output_dir = str(Path(file_path).resolve().parent)
        except Exception:
            self.output_dir = os.path.dirname(file_path)

        logger.info(f"Default output directory set to: {self.output_dir}")
        self.output_var.set(f"输出目录: {self.output_dir}")
        self.drop_label.config(text=os.path.basename(file_path))
        self.convert_btn.config(state=tk.NORMAL)
        self.status_var.set(f"已选择: {file_path}")

        # 单选时同步批量队列
        self.input_files = [file_path]

        # 根据是否为 webp 启用/禁用图片转换功能
        self._update_image_convert_controls(self.input_files)

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
        try:
            self.root.update_idletasks()
            self.root.update()
        except Exception:
            pass

    def _update_image_convert_controls(self, files: list[str]):
        """根据是否包含 webp 文件启用/禁用图片转换控件。"""
        has_webp = any(str(f).lower().endswith('.webp') for f in (files or []))
        state = tk.NORMAL if has_webp else tk.DISABLED

        try:
            self.img_convert_btn.config(state=state)
        except Exception:
            pass

        try:
            self.img_format_combo.config(state='readonly' if has_webp else 'disabled')
        except Exception:
            pass

    def convert_image_format(self):
        """将当前队列中的 webp 文件转换成 png 或 jpg，并输出到输出目录。"""
        if self._is_converting:
            self._log_append("正在转换视频中，请稍候再进行图片转换。\n")
            return

        if not self.input_files:
            messagebox.showerror("错误", "请先选择或拖拽图片文件")
            return

        fmt = (self.img_format_var.get() or 'png').lower().strip()
        if fmt not in ('png', 'jpg'):
            fmt = 'png'

        webps = [p for p in self.input_files if str(p).lower().endswith('.webp') and os.path.isfile(p)]
        if not webps:
            messagebox.showinfo("提示", "当前选择中不包含 WebP 文件")
            self._update_image_convert_controls(self.input_files)
            return

        if not self.output_dir:
            # 默认输出到第一个文件所在目录
            try:
                self.output_dir = str(Path(webps[0]).resolve().parent)
            except Exception:
                self.output_dir = os.path.dirname(webps[0])
            self.output_var.set(f"输出目录: {self.output_dir}")

        os.makedirs(self.output_dir, exist_ok=True)

        self._log_append(f"开始转换图片：WebP -> {fmt.upper()}，共 {len(webps)} 个文件\n")

        ok = 0
        fail = 0
        out_files: list[str] = []

        for src in webps:
            try:
                src_path = Path(src)
                dst_path = Path(self.output_dir) / f"{src_path.stem}.{fmt}"

                with Image.open(src_path) as im:
                    if fmt == 'jpg':
                        # jpg 不支持透明，转换为 RGB
                        if im.mode in ('RGBA', 'LA'):
                            bg = Image.new('RGB', im.size, (255, 255, 255))
                            bg.paste(im, mask=im.split()[-1])
                            im_out = bg
                        else:
                            im_out = im.convert('RGB')
                        im_out.save(dst_path, 'JPEG', quality=95, optimize=True)
                    else:
                        im.save(dst_path, 'PNG', optimize=True)

                ok += 1
                out_files.append(str(dst_path))
                self._log_append(f"成功：{src_path.name} -> {dst_path.name}\n")
            except Exception as e:
                fail += 1
                self._log_append(f"失败：{os.path.basename(src)}，原因：{str(e)}\n")

        self._log_append(f"图片转换完成：成功 {ok}，失败 {fail}\n")

        # 转换完成后不弹出二次确认，避免打断用户操作。
        # 如需生成视频，用户可直接点击“开始转换”（支持 webp 直接转 mp4）。
        if ok > 0:
            self._set_status(f"图片转换完成：成功 {ok}，失败 {fail}")

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
            self.root.after(100, self.root.quit)
            return False

    def _convert_one(self, file_path: str, on_done=None):
        """转换单张图片。on_done(success: bool)"""
        if not file_path or not os.path.exists(file_path):
            self._set_status("转换失败")
            self._log_append(f"图片不存在：{file_path}\n")
            if on_done:
                on_done(False)
            return

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)

        input_path = Path(file_path)
        output_path = Path(self.output_dir) / f"{input_path.stem}.mp4"

        duration = self.duration.get()
        cmd = [
            "ffmpeg",
            "-y",
            # 降低内存占用：限制线程数（部分机器/环境下大图编码可能出现 Cannot allocate memory）
            "-threads", "1",
            "-thread_type", "slice",
            "-loop", "1",
            "-framerate", "30",
            "-i", str(input_path),
            "-t", str(duration),
            # stillimage + 限制分辨率 + pad 到偶数，提升兼容性并减少编码压力
            "-vf", "fps=30,scale=1280:-2:force_original_aspect_ratio=decrease,pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p",
            "-c:v", "libx264",
            # ultrafast 内存/CPU压力更小；stillimage 更适合静态图
            "-preset", "ultrafast",
            "-tune", "stillimage",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-f", "mp4",
            str(output_path)
        ]

        ffmpeg_cmd_str = " ".join(cmd)
        logger.info(f"Starting conversion. Input: {input_path}, Output: {output_path}, Duration: {duration}s")
        logger.info("FFmpeg command: " + ffmpeg_cmd_str)
        self._log_append("FFmpeg 指令:\n" + ffmpeg_cmd_str + "\n\n")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                creationflags=(subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
            )

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
                            self._log_append(
                                f"转换成功！\n输出文件: {output_path}\n大小: {output_path.stat().st_size} bytes\n"
                            )
                            if on_done:
                                on_done(True)
                        else:
                            debug = []
                            debug.append("转换失败（请查看下方日志/错误信息）\n")
                            debug.append("FFmpeg 命令:\n" + ffmpeg_cmd_str)
                            debug.append(f"返回码: {return_code}")
                            if output_path.exists():
                                debug.append(f"输出文件大小: {output_path.stat().st_size} bytes")
                            else:
                                debug.append("输出文件不存在")
                            if err:
                                debug.append("\nFFmpeg 错误输出(stderr):\n" + err)
                            if out:
                                debug.append("\nFFmpeg 标准输出(stdout):\n" + out)
                            self._log_append("\n\n".join(debug) + "\n")
                            if on_done:
                                on_done(False)

                    self.root.after(0, update_ui)

                except Exception as e:
                    logger.exception("worker_wait exception")

                    def update_ui_error():
                        self._log_append(f"等待 FFmpeg 结束时发生异常:\n{str(e)}\n")
                        if on_done:
                            on_done(False)

                    self.root.after(0, update_ui_error)

            threading.Thread(target=worker_wait, daemon=True).start()

        except Exception as e:
            self._log_append(f"执行 FFmpeg 时出错:\n{str(e)}\n")
            logger.exception("Exception while running FFmpeg")
            if on_done:
                on_done(False)

    def convert(self):
        if self._is_converting:
            self._log_append("正在转换中，请稍候...\n")
            return

        queue = self.input_files if self.input_files else ([self.input_file] if self.input_file else [])
        queue = [q for q in queue if q and os.path.exists(q) and self.is_supported_file(q)]

        if not queue:
            messagebox.showerror("错误", "请选择有效的图片文件")
            return

        self._is_converting = True
        self._batch_total = len(queue)
        self._batch_index = 0

        self._log_clear()
        self.convert_btn.config(state=tk.DISABLED)

        results = {"ok": 0, "fail": 0}

        def finish():
            self._is_converting = False
            self.convert_btn.config(state=tk.NORMAL)
            self._set_status(f"批量完成：成功 {results['ok']}，失败 {results['fail']}")
            self._log_append(f"\n批量完成：成功 {results['ok']}，失败 {results['fail']}\n")

        def run_next(prev_ok=None):
            if prev_ok is True:
                results["ok"] += 1
            elif prev_ok is False:
                results["fail"] += 1

            if self._batch_index >= self._batch_total:
                finish()
                return

            current = queue[self._batch_index]
            self._batch_index += 1

            self._set_status(f"正在转换（{self._batch_index}/{self._batch_total}）：{os.path.basename(current)}")
            self._convert_one(current, on_done=lambda ok: run_next(ok))

        # 启动第一张
        run_next(None)


def main():
    # 若安装了 tkinterdnd2，则必须使用 TkinterDnD.Tk() 才能接收系统文件拖拽
    if TkinterDnD is not None:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    # 设置窗口图标（左上角标题栏图标）。
    # 注意：PyInstaller 的 icon= 只影响 EXE 文件/任务栏分组图标，Tk 窗口左上角需要在代码里设置。
    try:
        icon_path = get_resource_path('icon.ico')
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        # 不影响主流程
        pass

    style = ttk.Style()
    style.configure('Drop.TLabelframe', background='#f0f0f0')

    app = ImageToVideoConverter(root)
    root.mainloop()


if __name__ == "__main__":
    main()
