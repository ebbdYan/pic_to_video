import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
from pathlib import Path
from typing import Optional

# Import the logger we created
from logging_config import logger

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
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(
            self.root, 
            textvariable=self.status_var, 
            relief=tk.SUNKEN, 
            anchor=tk.W
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Bind drag and drop events
        self.drop_frame.bind("<Button-1>", self.browse_file)
        self.drop_frame.bind("<Enter>", self.on_enter)
        self.drop_frame.bind("<Leave>", self.on_leave)
        
        # Drag and drop (Tkinter 原生不支持，需要额外库，如 tkinterdnd2)
        # 为保证 EXE 可直接运行，这里默认关闭拖拽；如需拖拽我可以给你集成 tkinterdnd2 的版本。
    
    def on_enter(self, event):
        self.drop_frame.configure(style='Drop.TLabelframe')
    
    def on_leave(self, event):
        self.drop_frame.configure(style='TLabelframe')
    
    def on_drop(self, event):
        # Get the file path from the drop event
        file_path = event.data.strip('{}')
        if os.path.isfile(file_path) and self.is_supported_file(file_path):
            self.set_input_file(file_path)
        else:
            messagebox.showerror("错误", "请拖放有效的图片文件")
    
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
        logger.info("FFmpeg command: " + " ".join(cmd))

        self.status_var.set("正在转换...")
        self.root.update()
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                creationflags=(subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
            )

            # 轮询进程结束；结束后务必读取 stdout/stderr（避免缓冲区导致异常/卡死），并检查输出文件大小
            def check_process():
                return_code = process.poll()
                if return_code is None:
                    self.root.after(150, check_process)
                    return

                out, err = process.communicate()

                # 如果 ffmpeg 返回 0 但文件为 0KB，也视为失败并提示日志
                file_ok = output_path.exists() and output_path.stat().st_size > 0

                if return_code == 0 and file_ok:
                    self.status_var.set(f"转换完成: {output_path}")
                    messagebox.showinfo(
                        "成功",
                        f"视频已保存到:\n{output_path}"
                    )
                    logger.info(f"Conversion succeeded. Output file: {output_path} ({output_path.stat().st_size} bytes)")
                    os.startfile(output_path.parent)
                else:
                    self.status_var.set("转换失败")
                    debug = []
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

                    logger.error("Conversion failed. " + " | ".join([d.replace("\n", " ") for d in debug]))
                    if err:
                        logger.error("FFmpeg stderr:\n" + err)
                    if out:
                        logger.info("FFmpeg stdout:\n" + out)
                    messagebox.showerror("错误", "\n\n".join(debug))

            self.root.after(150, check_process)
            
        except Exception as e:
            self.status_var.set("转换失败")
            logger.exception("Exception while running FFmpeg")
            messagebox.showerror("错误", f"执行 FFmpeg 时出错:\n{str(e)}")


def main():
    root = tk.Tk()
    
    # Configure styles
    style = ttk.Style()
    style.configure('Drop.TLabelframe', background='#f0f0f0')
    
    app = ImageToVideoConverter(root)
    root.mainloop()


if __name__ == "__main__":
    main()
