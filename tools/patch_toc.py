# -*- coding: utf-8 -*-
"""Исправляет block_size TOC-блока корневого контейнера на 0x200.

v8unpack пишет в заголовок TOC-блока block_size = фактическому размеру данных, хотя место
под блок резервирует 512 байт. Платформа 1С в своих файлах пишет 0x200 (проверено на
реальном образце ВнешняяОбработка803.epf: TOC «000000a8 00000200»). Меняем только это поле
и только если следующий блок действительно начинается не раньше 16 + 31 + 512.
Идея и описание проблемы: Pradushkoai/1c-ai-dev-env, adr/0007, scripts/patch_epf_blocksize.py.
"""
import struct


def patch(path):
    b = bytearray(open(path, "rb").read())
    assert b[:4] == b"\xff\xff\xff\x7f", "не контейнер 1С"
    hdr = b[16:47].decode("ascii")
    doc, bs, nxt = [int(x, 16) for x in hdr.split()]
    toc = bytes(b[47:47 + doc])
    first = min(struct.unpack("<I", toc[i:i + 4])[0] for i in range(0, len(toc), 12))
    if bs == 0x200:
        return {"doc_size": doc, "block_size": bs, "changed": False}
    assert doc <= 0x200 and first >= 47 + 0x200, "нет места под TOC 512 байт — патч небезопасен"
    b[16:47] = f"\r\n{doc:08x} {0x200:08x} {nxt:08x} \r\n".encode("ascii")
    open(path, "wb").write(bytes(b))
    return {"doc_size": doc, "block_size_was": bs, "block_size": 0x200, "first_entry_offset": first, "changed": True}


# Фиксированное время файлов внутри контейнера, чтобы сборка была побайтно воспроизводимой.
# Формат 1С: десятые доли миллисекунды от 01.01.0001. По умолчанию 01.11.2026 00:00:00.
FIXED_TIME_1C = (1793491200 + 62135596800) * 10000


def _entries(b, base=0):
    hdr = b[base + 16:base + 47].decode("ascii")
    doc = int(hdr.split()[0], 16)
    toc = bytes(b[base + 47:base + 47 + doc])
    return [struct.unpack("<II", toc[i:i + 8]) for i in range(0, len(toc) - 11, 12)]


def normalize_times(path, value=FIXED_TIME_1C):
    """Переписывает время создания/изменения в атрибутах файлов корневого контейнера."""
    b = bytearray(open(path, "rb").read())
    n = 0
    for attr_off, _ in _entries(b):
        p = attr_off + 31
        b[p:p + 16] = struct.pack("<QQ", value, value)
        n += 1
    open(path, "wb").write(bytes(b))
    return n
