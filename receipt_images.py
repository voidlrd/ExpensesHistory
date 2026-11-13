import math

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PyQt6.QtGui import QImage, QImageReader, QPainter

# what Claude reads at full resolution (28 px patches); Gemini tiles at 768 px, so this suits it too
PATCH = 28
MAX_EDGE = 2576
MAX_PATCHES = 4784
OVERLAP = 0.1
MAX_STRIPS = 8
JPEG_QUALITY = 90


class ImageError(ValueError):
    pass


def plan_strips(width, height):
    """Scaled (width, height) and the (top, height) of each overlapping strip, so no strip gets downscaled."""
    scale = min(1.0, MAX_EDGE / width)
    while True:
        w, h = max(1, round(width * scale)), max(1, round(height * scale))
        strip = min(MAX_EDGE, MAX_PATCHES // math.ceil(w / PATCH) * PATCH)
        if h <= strip:
            return (w, h), [(0, h)]
        overlap = round(strip * OVERLAP)
        count = math.ceil((h - overlap) / (strip - overlap))
        if count <= MAX_STRIPS:
            step = (h - strip) / (count - 1)
            return (w, h), [(round(i * step), strip) for i in range(count)]
        # too long even in strips: shrink until it fits
        scale *= MAX_STRIPS / count


def load_image(data):
    """Decode a photo, turned upright by its EXIF orientation."""
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        raise ImageError("This picture can't be read. Use a JPEG or PNG photo or screenshot.")
    return image


def encode_jpeg(image):
    if image.hasAlphaChannel():
        flat = QImage(image.size(), QImage.Format.Format_RGB32)
        flat.fill(Qt.GlobalColor.white)
        painter = QPainter(flat)
        painter.drawImage(0, 0, image)
        painter.end()
        image = flat

    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "JPEG", JPEG_QUALITY)
    return bytes(data)


def prepare_images(photos):
    """JPEG strips of each photo (bytes), top to bottom, each within what the model reads at full resolution."""
    prepared = []
    for data in photos:
        image = load_image(data)
        (w, h), strips = plan_strips(image.width(), image.height())
        if (w, h) != (image.width(), image.height()):
            image = image.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        prepared += [encode_jpeg(image.copy(0, top, w, height)) for top, height in strips]
    return prepared
