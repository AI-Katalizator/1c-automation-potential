# -*- coding: utf-8 -*-
"""Минимальный читатель контейнера 1С (cf/epf) для проверок: список файлов и их содержимое."""
import struct
import zlib

END = 0x7FFFFFFF


def _hdr(b, o):
    p = b[o:o + 31].decode("ascii").split()
    return [int(x, 16) for x in p]


def _read(b, o):
    out = b""
    total = None
    while True:
        ds, bs, nx = _hdr(b, o)
        if total is None:
            total = ds
        out += b[o + 31:o + 31 + min(bs, total - len(out))]
        if nx == END or len(out) >= total:
            return out[:total]
        o = nx


def toc_header(b):
    return _hdr(b, 16)


def read_files(b, prefix=""):
    toc = _read(b, 16)
    res = {}
    for i in range(0, len(toc), 12):
        d, dt, _ = struct.unpack("<III", toc[i:i + 12])
        name = _read(b, d)[20:].decode("utf-16-le").rstrip("\x00")
        data = _read(b, dt)
        try:
            data = zlib.decompress(data, -15)
        except zlib.error:
            pass
        if data[:4] == b"\xff\xff\xff\x7f":
            res.update(read_files(data, prefix + name + "/"))
        else:
            res[prefix + name] = data
    return res
