from __future__ import annotations

import base64
import io
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps
from PyQt6.QtCore import QByteArray, QMimeData, Qt, QUrl
from PyQt6.QtGui import QAction, QColor, QGuiApplication, QIcon, QImage, QKeySequence, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

ICON_SIZES = [16, 24, 32, 48, 64, 96, 128, 256]
SUPPORTED_IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.webp *.tiff *.gif);;All Files (*.*)"


def resolve_app_icon_path() -> Path | None:
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "icon.ico")

    candidates.append(Path(__file__).resolve().parents[2] / "icon.ico")
    candidates.append(Path.cwd() / "icon.ico")

    for path in candidates:
        if path.exists():
            return path
    return None


def qimage_to_pil(image: QImage) -> Image.Image:
    image_rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    width = image_rgba.width()
    height = image_rgba.height()
    bits = image_rgba.bits()
    buffer = bits.asstring(image_rgba.sizeInBytes())
    return Image.frombytes("RGBA", (width, height), buffer)


def pil_to_qimage(image: Image.Image) -> QImage:
    rgba = image.convert("RGBA")
    qimage = QImage(
        rgba.tobytes("raw", "RGBA"),
        rgba.width,
        rgba.height,
        QImage.Format.Format_RGBA8888,
    )
    return qimage.copy()


def pil_to_pixmap(image: Image.Image) -> QPixmap:
    return QPixmap.fromImage(pil_to_qimage(image))


def copy_png_to_clipboard(image: Image.Image) -> None:
    temp_root = Path(os.getenv("TEMP") or os.getenv("TMP") or str(Path.home() / "AppData" / "Local" / "Temp"))
    temp_dir = temp_root / "IconGenerationTool" / "clipboard"
    temp_dir.mkdir(parents=True, exist_ok=True)
    for old_file in temp_dir.glob("tmp_transparent_*.png"):
        try:
            old_file.unlink()
        except OSError:
            # Best-effort cleanup; continue if old temp file is in use.
            pass

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    temp_path = temp_dir / f"tmp_transparent_{timestamp}.png"
    image.convert("RGBA").save(temp_path, format="PNG")

    file_url = QUrl.fromLocalFile(str(temp_path))
    uri_payload = QByteArray((file_url.toString() + "\r\n").encode("utf-8"))

    mime_data = QMimeData()
    mime_data.setUrls([file_url])
    mime_data.setData("text/uri-list", uri_payload)
    mime_data.setText(str(temp_path))
    mime_data.setImageData(pil_to_qimage(image))
    QGuiApplication.clipboard().setMimeData(mime_data)


def rgb_to_hex(color: tuple[int, int, int]) -> str:
    r, g, b = color
    return f"#{r:02X}{g:02X}{b:02X}"


def save_svg_with_embedded_png(source: Image.Image, destination: Path) -> None:
    rgba = source.convert("RGBA")
    width, height = rgba.size

    png_buffer = io.BytesIO()
    rgba.save(png_buffer, format="PNG")
    encoded = base64.b64encode(png_buffer.getvalue()).decode("ascii")

    svg = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"{height}\" viewBox=\"0 0 {width} {height}\">\n"
        f"  <image width=\"{width}\" height=\"{height}\" href=\"data:image/png;base64,{encoded}\" />\n"
        "</svg>\n"
    )
    destination.write_text(svg, encoding="utf-8")


def invert_colors_preserving_alpha(source: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(source).convert("RGBA")
    r, g, b, a = image.split()
    inverted_rgb = ImageOps.invert(Image.merge("RGB", (r, g, b)))
    inv_r, inv_g, inv_b = inverted_rgb.split()
    return Image.merge("RGBA", (inv_r, inv_g, inv_b, a))


def remove_background(
    source: Image.Image,
    mode: str,
    threshold: int,
    fill_color: tuple[int, int, int] | None = None,
) -> Image.Image:
    image = ImageOps.exif_transpose(source).convert("RGBA")
    threshold = max(0, min(255, threshold))

    pixels = image.getdata()
    output: list[tuple[int, int, int, int]] = []

    white_limit = 255 - threshold
    for r, g, b, a in pixels:
        if a == 0:
            output.append((r, g, b, a))
            continue

        if mode == "black":
            is_background = max(r, g, b) <= threshold
        else:
            is_background = min(r, g, b) >= white_limit

        if is_background and fill_color is not None:
            output.append((fill_color[0], fill_color[1], fill_color[2], 255))
        else:
            output.append((r, g, b, 0 if is_background else a))

    result = Image.new("RGBA", image.size)
    result.putdata(output)
    return result


def scale_to_square(source: Image.Image, size: int) -> Image.Image:
    resized = source.copy()
    resized.thumbnail((size, size), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - resized.width) // 2
    y = (size - resized.height) // 2
    canvas.paste(resized, (x, y), resized)
    return canvas


def render_preview(source: Image.Image, width: int, height: int) -> Image.Image:
    resized = source.copy()
    resized.thumbnail((width, height), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (width, height), (245, 245, 245, 255))
    x = (width - resized.width) // 2
    y = (height - resized.height) // 2
    canvas.paste(resized, (x, y), resized)
    return canvas


def render_icon_variants(source: Image.Image, sizes: Iterable[int]) -> list[Image.Image]:
    prepared = source.convert("RGBA")
    variants: list[Image.Image] = []
    for size in sorted(set(sizes)):
        variants.append(scale_to_square(prepared, size))
    return variants


def save_multi_icon(source: Image.Image, destination: Path, sizes: Iterable[int]) -> None:
    icon_sizes = sorted(set(sizes))
    variants = render_icon_variants(source, icon_sizes)
    if not variants:
        raise ValueError("No icon size configured.")

    base = variants[-1]
    base.save(destination, format="ICO", append_images=variants[:-1], sizes=[(s, s) for s in icon_sizes])


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Icon Generator (up to 256x256)")
        self.resize(400, 583)

        icon_path = resolve_app_icon_path()
        if icon_path is not None:
            app_icon = QIcon(str(icon_path))
            if not app_icon.isNull():
                QApplication.setWindowIcon(app_icon)
                self.setWindowIcon(app_icon)

        self.source_image: Image.Image | None = None
        self.processed_image: Image.Image | None = None
        self.current_source_desc = ""
        self.remove_mode = "white"
        self.threshold = 60
        self.cutout_mode_enabled = False
        self.invert_mode_enabled = False
        self.fill_mode_enabled = False
        self.always_on_top_enabled = False
        self.fill_color = (255, 255, 255)

        self.preview_label = QLabel("Import an image or paste it with Ctrl+V")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(420, 300)
        self.preview_label.setStyleSheet("border: 1px dashed #999; padding: 12px; background: #f5f5f5;")

        self.info_label = QLabel("Export ICO sizes: 16, 24, 32, 48, 64, 96, 128, 256")
        self.info_label.setWordWrap(True)

        self.import_button = QPushButton("Import Image")
        self.import_button.clicked.connect(self.import_image)

        self.paste_button = QPushButton("Paste Image (Ctrl+V)")
        self.paste_button.clicked.connect(self.paste_from_clipboard)

        self.export_button = QPushButton("Export ICO")
        self.export_button.clicked.connect(self.export_icon)
        self.export_button.setEnabled(False)

        self.cutout_mode_button = QPushButton("Cutout Mode: OFF")
        self.cutout_mode_button.setCheckable(True)
        self.cutout_mode_button.toggled.connect(self._toggle_cutout_mode)

        self.invert_mode_button = QPushButton("Invert: OFF")
        self.invert_mode_button.setCheckable(True)
        self.invert_mode_button.toggled.connect(self._toggle_invert_mode)

        self.remove_white_button = QPushButton("Remove White")
        self.remove_white_button.setCheckable(True)
        self.remove_white_button.setChecked(True)
        self.remove_white_button.clicked.connect(lambda: self._set_remove_mode("white"))

        self.remove_black_button = QPushButton("Remove Black")
        self.remove_black_button.setCheckable(True)
        self.remove_black_button.clicked.connect(lambda: self._set_remove_mode("black"))

        self.remove_mode_group = QButtonGroup(self)
        self.remove_mode_group.setExclusive(True)
        self.remove_mode_group.addButton(self.remove_white_button)
        self.remove_mode_group.addButton(self.remove_black_button)

        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(0, 255)
        self.threshold_slider.setValue(self.threshold)
        self.threshold_slider.valueChanged.connect(self._on_threshold_changed)

        self.threshold_progress = QProgressBar()
        self.threshold_progress.setRange(0, 255)
        self.threshold_progress.setValue(self.threshold)
        self.threshold_progress.setFormat("Threshold: %v / 255")

        self.fill_mode_button = QPushButton("Fill Mode: OFF")
        self.fill_mode_button.setCheckable(True)
        self.fill_mode_button.toggled.connect(self._toggle_fill_mode)

        self.fill_color_button = QPushButton("")
        self.fill_color_button.clicked.connect(self._choose_fill_color)
        self.fill_color_button.setEnabled(False)
        self._update_fill_color_button_appearance()

        action_layout = QHBoxLayout()
        action_layout.addWidget(self.import_button)
        action_layout.addWidget(self.paste_button)
        action_layout.addWidget(self.export_button)
        action_layout.addWidget(self.cutout_mode_button)
        action_layout.addStretch(1)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Background Removal:"))
        mode_layout.addWidget(self.remove_white_button)
        mode_layout.addWidget(self.remove_black_button)
        mode_layout.addWidget(self.invert_mode_button)
        mode_layout.addStretch(1)

        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("Threshold:"))
        threshold_layout.addWidget(self.threshold_slider, stretch=1)
        threshold_layout.addWidget(self.threshold_progress)

        fill_layout = QHBoxLayout()
        fill_layout.addWidget(QLabel("Background Fill:"))
        fill_layout.addWidget(self.fill_mode_button)
        fill_layout.addWidget(self.fill_color_button)
        fill_layout.addStretch(1)

        root_layout = QVBoxLayout()
        root_layout.addLayout(action_layout)
        root_layout.addLayout(mode_layout)
        root_layout.addLayout(threshold_layout)
        root_layout.addLayout(fill_layout)
        root_layout.addWidget(self.preview_label, stretch=1)
        root_layout.addWidget(self.info_label)

        root = QWidget()
        root.setLayout(root_layout)
        self.setCentralWidget(root)
        
        self.pin_top_button = QPushButton("Always On Top: OFF")
        self.pin_top_button.setCheckable(True)
        self.pin_top_button.toggled.connect(self._toggle_always_on_top)
        self.statusBar().addPermanentWidget(self.pin_top_button)

        self._create_shortcuts()
        self._update_export_button_text()

    def _create_shortcuts(self) -> None:
        paste_action = QAction("Paste", self)
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        paste_action.triggered.connect(self.paste_from_clipboard)
        self.addAction(paste_action)

    def _set_remove_mode(self, mode: str) -> None:
        if mode not in {"white", "black"}:
            return
        self.remove_mode = mode
        self._reprocess_image()

    def _on_threshold_changed(self, value: int) -> None:
        self.threshold = value
        self.threshold_progress.setValue(value)
        self._reprocess_image()

    def _toggle_cutout_mode(self, enabled: bool) -> None:
        self.cutout_mode_enabled = enabled
        self.cutout_mode_button.setText("Cutout Mode: ON" if enabled else "Cutout Mode: OFF")
        self._update_export_button_text()
        self._reprocess_image()

    def _toggle_invert_mode(self, enabled: bool) -> None:
        self.invert_mode_enabled = enabled
        self.invert_mode_button.setText("Invert: ON" if enabled else "Invert: OFF")
        self._reprocess_image()

    def _toggle_fill_mode(self, enabled: bool) -> None:
        self.fill_mode_enabled = enabled
        self.fill_mode_button.setText("Fill Mode: ON" if enabled else "Fill Mode: OFF")
        self.fill_color_button.setEnabled(enabled)
        self._reprocess_image()

    def _toggle_always_on_top(self, enabled: bool) -> None:
        self.always_on_top_enabled = enabled
        self.pin_top_button.setText("Always On Top: ON" if enabled else "Always On Top: OFF")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        self.show()

    def _choose_fill_color(self) -> None:
        current = QColor(*self.fill_color)
        color = QColorDialog.getColor(current, self, "Select Fill Color")
        if not color.isValid():
            return
        self.fill_color = (color.red(), color.green(), color.blue())
        self._update_fill_color_button_appearance()
        self._reprocess_image()

    def _update_fill_color_button_appearance(self) -> None:
        color_hex = rgb_to_hex(self.fill_color)
        text_color = "#000000" if sum(self.fill_color) > 382 else "#FFFFFF"
        self.fill_color_button.setText(f"Fill Color ({color_hex})")
        self.fill_color_button.setStyleSheet(f"background-color: {color_hex}; color: {text_color};")

    def _update_export_button_text(self) -> None:
        self.export_button.setText("Export PNG/SVG" if self.cutout_mode_enabled else "Export ICO")

    def import_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", SUPPORTED_IMAGE_FILTER)
        if not file_path:
            return

        try:
            image = Image.open(file_path)
            image.load()
        except Exception as exc:
            QMessageBox.critical(self, "Read Failed", f"Could not open image:\n{exc}")
            return

        self._set_source_image(image, f"Source: {file_path}")

    def paste_from_clipboard(self) -> None:
        clipboard = QGuiApplication.clipboard()
        qimage = clipboard.image()
        if qimage.isNull():
            QMessageBox.warning(self, "No Image", "Clipboard does not contain image data.")
            return

        self._set_source_image(qimage_to_pil(qimage), "Source: Clipboard")

    def _set_source_image(self, image: Image.Image, source_desc: str) -> None:
        self.source_image = image
        self.current_source_desc = source_desc
        self.export_button.setEnabled(True)
        self._reprocess_image()

    def _reprocess_image(self) -> None:
        if self.source_image is None:
            self.processed_image = None
            self._refresh_preview()
            return

        processing_source = self.source_image
        if self.invert_mode_enabled:
            processing_source = invert_colors_preserving_alpha(processing_source)

        fill_color = self.fill_color if self.fill_mode_enabled else None
        self.processed_image = remove_background(
            processing_source,
            self.remove_mode,
            self.threshold,
            fill_color=fill_color,
        )

        if self.cutout_mode_enabled:
            copy_png_to_clipboard(self.processed_image)

        self._refresh_preview()

    def _refresh_preview(self) -> None:
        if self.processed_image is None or self.source_image is None:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("Import an image or paste it with Ctrl+V")
            self.info_label.setText("Export ICO sizes: 16, 24, 32, 48, 64, 96, 128, 256")
            return

        preview = render_preview(self.processed_image, 420, 320)
        self.preview_label.setText("")
        self.preview_label.setPixmap(pil_to_pixmap(preview))

        mode_text = "White" if self.remove_mode == "white" else "Black"
        invert_text = "ON" if self.invert_mode_enabled else "OFF"
        cutout_text = "ON (PNG copied to clipboard)" if self.cutout_mode_enabled else "OFF"
        fill_text = f"ON ({rgb_to_hex(self.fill_color)})" if self.fill_mode_enabled else "OFF"
        export_text = "PNG/SVG" if self.cutout_mode_enabled else f"ICO ({', '.join(str(s) for s in ICON_SIZES)})"

        self.info_label.setText(
            f"{self.current_source_desc} | Original: {self.source_image.width}x{self.source_image.height} | "
            f"Remove: {mode_text} | Invert: {invert_text} | Threshold: {self.threshold} | Fill: {fill_text} | "
            f"Cutout: {cutout_text} | Export: {export_text}"
        )

    def export_icon(self) -> None:
        if self.processed_image is None:
            QMessageBox.information(self, "No Image", "Please import or paste an image first.")
            return

        if self.cutout_mode_enabled:
            self._export_cutout_asset()
            return

        self._export_ico()

    def _export_ico(self) -> None:
        if self.processed_image is None:
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save ICO", "icon.ico", "Icon Files (*.ico)")
        if not file_path:
            return

        target = Path(file_path)
        if target.suffix.lower() != ".ico":
            target = target.with_suffix(".ico")

        try:
            save_multi_icon(self.processed_image, target, ICON_SIZES)
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Could not export ICO:\n{exc}")
            return

        QMessageBox.information(self, "Export Complete", f"Saved to:\n{target}")

    def _export_cutout_asset(self) -> None:
        if self.processed_image is None:
            return

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Cutout",
            "cutout.png",
            "PNG Files (*.png);;SVG Files (*.svg)",
        )
        if not file_path:
            return

        target = Path(file_path)
        selected_is_svg = selected_filter.startswith("SVG")
        if target.suffix.lower() not in {".png", ".svg"}:
            target = target.with_suffix(".svg" if selected_is_svg else ".png")

        export_svg = target.suffix.lower() == ".svg"
        try:
            if export_svg:
                save_svg_with_embedded_png(self.processed_image, target)
            else:
                self.processed_image.convert("RGBA").save(target, format="PNG")
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Could not export cutout:\n{exc}")
            return

        QMessageBox.information(self, "Export Complete", f"Saved to:\n{target}")


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
