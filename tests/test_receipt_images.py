import math

import pytest
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PyQt6.QtGui import QImage, QImageIOHandler, QImageWriter

from receipt_images import (
    MAX_EDGE, MAX_PATCHES, MAX_STRIPS, PATCH, ImageError, load_image, plan_strips, prepare_images
)


def patches(width, height):
    return math.ceil(width / PATCH) * math.ceil(height / PATCH)


def assert_readable_at_full_size(size, strips):
    width, height = size
    for _, strip_height in strips:
        assert max(width, strip_height) <= MAX_EDGE
        assert patches(width, strip_height) <= MAX_PATCHES


def assert_covers(size, strips):
    _, height = size
    assert strips[0][0] == 0
    assert strips[-1][0] + strips[-1][1] == height
    for (top, h), (next_top, _) in zip(strips, strips[1:]):
        assert next_top < top + h  # overlapping, no gap


def test_small_image_is_left_alone():
    assert plan_strips(800, 1000) == ((800, 1000), [(0, 1000)])


def test_phone_photo_is_cut_into_full_resolution_strips():
    size, strips = plan_strips(3000, 4000)
    assert size[0] == MAX_EDGE
    assert len(strips) > 1
    assert_readable_at_full_size(size, strips)
    assert_covers(size, strips)


def test_tall_screenshot_keeps_its_width():
    size, strips = plan_strips(1080, 6000)
    assert size == (1080, 6000)
    assert len(strips) == 3
    assert_readable_at_full_size(size, strips)
    assert_covers(size, strips)


def test_extremely_long_receipt_is_shrunk_to_the_strip_limit():
    size, strips = plan_strips(1000, 60000)
    assert len(strips) <= MAX_STRIPS
    assert size[1] < 60000
    assert_readable_at_full_size(size, strips)
    assert_covers(size, strips)


@pytest.mark.parametrize("width, height", [(4000, 3000), (1, 1), (2577, 10), (500, 2600)])
def test_any_shape_fits(width, height):
    size, strips = plan_strips(width, height)
    assert_readable_at_full_size(size, strips)
    assert_covers(size, strips)


def encoded(image, fmt):
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, fmt)
    return bytes(data)


def test_prepare_images_returns_jpeg_strips(qapp):
    image = QImage(1080, 6000, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    small = QImage(400, 300, QImage.Format.Format_RGB32)
    small.fill(Qt.GlobalColor.gray)

    prepared = prepare_images([encoded(image, "JPEG"), encoded(small, "PNG")])

    assert len(prepared) == 4
    for data in prepared:
        assert data.startswith(b"\xff\xd8")  # JPEG
    assert load_image(prepared[0]).size().width() == 1080
    assert load_image(prepared[-1]).size().height() == 300


def test_transparent_screenshot_gets_a_white_background(qapp):
    image = QImage(100, 100, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    (data,) = prepare_images([encoded(image, "PNG")])

    assert load_image(data).pixelColor(50, 50).lightness() > 240


def test_photo_is_turned_upright_by_its_exif_orientation(qapp):
    image = QImage(200, 100, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    writer = QImageWriter(buffer, b"jpeg")
    writer.setTransformation(QImageIOHandler.Transformation.TransformationRotate90)
    assert writer.write(image)

    upright = load_image(bytes(data))

    assert (upright.width(), upright.height()) == (100, 200)


def test_unreadable_picture_is_explained(qapp):
    with pytest.raises(ImageError, match="can't be read"):
        prepare_images([b"not an image"])
