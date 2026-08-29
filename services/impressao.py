from __future__ import annotations

import ctypes
import os


def raw_print(printer: str, content: str) -> None:
    if os.name != "nt":
        raise RuntimeError("Impressão direta está disponível apenas no Windows.")
    if not printer:
        raise RuntimeError("Informe o nome da impressora Zebra nas configurações.")
    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    handle = ctypes.c_void_p()
    if not winspool.OpenPrinterW(ctypes.c_wchar_p(printer), ctypes.byref(handle), None):
        raise OSError(ctypes.get_last_error(), f"Não foi possível abrir a impressora {printer}.")

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [("pDocName", ctypes.c_wchar_p), ("pOutputFile", ctypes.c_wchar_p), ("pDatatype", ctypes.c_wchar_p)]

    doc = DOC_INFO_1("Etiqueta Zebra", None, "RAW")
    # O ZPL gerado declara ^CI27 (UTF-8, ver services/zpl.py). Os bytes
    # enviados precisam usar o mesmo encoding, senão acentos (Ç, Ã, Á...)
    # chegam corrompidos ou somem — não use cp850 aqui.
    payload = content.encode("utf-8")
    written = ctypes.c_ulong()
    try:
        if not winspool.StartDocPrinterW(handle, 1, ctypes.byref(doc)):
            raise OSError(ctypes.get_last_error(), "Falha ao iniciar o documento.")
        try:
            winspool.StartPagePrinter(handle)
            if not winspool.WritePrinter(handle, payload, len(payload), ctypes.byref(written)):
                raise OSError(ctypes.get_last_error(), "Falha ao enviar os dados RAW.")
            winspool.EndPagePrinter(handle)
        finally:
            winspool.EndDocPrinter(handle)
    finally:
        winspool.ClosePrinter(handle)