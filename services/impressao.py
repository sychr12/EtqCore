"""Localiza a Zebra no Windows e envia comandos ZPL diretamente ao spooler."""

from __future__ import annotations

import ctypes
import os


def installed_printers() -> list[str]:
    """Lista impressoras locais e conectadas pelo spooler do Windows."""
    if os.name != "nt":
        return []

    from ctypes import wintypes

    class PRINTER_INFO_4W(ctypes.Structure):
        _fields_ = [
            ("pPrinterName", wintypes.LPWSTR),
            ("pServerName", wintypes.LPWSTR),
            ("Attributes", wintypes.DWORD),
        ]

    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    enum_printers = winspool.EnumPrintersW
    enum_printers.argtypes = [
        wintypes.DWORD, wintypes.LPWSTR, wintypes.DWORD,
        ctypes.POINTER(ctypes.c_byte), wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
    ]
    enum_printers.restype = wintypes.BOOL

    flags = 0x00000002 | 0x00000004  # PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
    needed = wintypes.DWORD()
    returned = wintypes.DWORD()
    enum_printers(flags, None, 4, None, 0, ctypes.byref(needed), ctypes.byref(returned))
    if not needed.value:
        return []

    buffer = (ctypes.c_byte * needed.value)()
    try:
        ok = enum_printers(
            flags, None, 4, buffer, needed.value,
            ctypes.byref(needed), ctypes.byref(returned),
        )
        if not ok:
            return []
        items = ctypes.cast(buffer, ctypes.POINTER(PRINTER_INFO_4W))
        names = [items[index].pPrinterName for index in range(returned.value) if items[index].pPrinterName]
    except (OSError, ValueError):
        return []
    return sorted(set(names), key=str.casefold)


def _printer_can_open(name: str) -> bool:
    """Confere diretamente com o spooler, inclusive nomes UNC salvos."""
    if os.name != "nt" or not name.strip():
        return False
    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    handle = ctypes.c_void_p()
    if not winspool.OpenPrinterW(ctypes.c_wchar_p(name.strip()), ctypes.byref(handle), None):
        return False
    winspool.ClosePrinter(handle)
    return True


def recommended_zebra(printers: list[str] | None = None) -> str | None:
    """Prefere a ZD220; se não houver, procura qualquer Zebra/ZDesigner."""
    printers = printers if printers is not None else installed_printers()
    ranked = sorted(
        printers,
        key=lambda name: (
            "zd220" not in name.casefold(),
            not any(word in name.casefold() for word in ("zebra", "zdesigner")),
            name.casefold(),
        ),
    )
    if ranked and any(word in ranked[0].casefold() for word in ("zd220", "zebra", "zdesigner")):
        return ranked[0]
    return None


def resolve_printer(configured: str) -> str:
    """Confirma o nome salvo ou escolhe automaticamente uma Zebra disponível."""
    printers = installed_printers()
    if configured:
        match = next((name for name in printers if name.casefold() == configured.casefold()), None)
        if match:
            return match
        # Impressoras compartilhadas podem ser abertas pelo nome salvo mesmo
        # quando o EnumPrinters ainda não as devolveu nesta sessão do Windows.
        if _printer_can_open(configured):
            return configured.strip()
    if configured:
        raise RuntimeError(
            f'A impressora "{configured}" não está instalada no Windows. '
            "Use Procurar impressoras nas configurações."
        )
    match = recommended_zebra(printers)
    if match:
        return match
    raise RuntimeError(
        "Nenhuma Zebra ZD220 foi encontrada no Windows. Instale o driver ZDesigner e tente novamente."
    )


def raw_print(printer: str, content: str) -> str:
    """Envia bytes ZPL puros, sem o Windows redesenhar ou redimensionar a etiqueta."""
    if os.name != "nt":
        raise RuntimeError("Impressão direta está disponível apenas no Windows.")
    printer = resolve_printer(printer)
    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    handle = ctypes.c_void_p()
    if not winspool.OpenPrinterW(ctypes.c_wchar_p(printer), ctypes.byref(handle), None):
        raise OSError(ctypes.get_last_error(), f"Não foi possível abrir a impressora {printer}.")

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [("pDocName", ctypes.c_wchar_p), ("pOutputFile", ctypes.c_wchar_p), ("pDatatype", ctypes.c_wchar_p)]

    # RAW é essencial: um driver gráfico poderia mudar margens e tamanhos.
    doc = DOC_INFO_1("Etiqueta Zebra", None, "RAW")
    # O ZPL gerado declara ^CI28 (UTF-8, ver services/zpl.py). Os bytes
    # enviados precisam usar o mesmo encoding, senão acentos (Ç, Ã, Á...)
    # chegam corrompidos ou somem — não use cp850 aqui.
    payload = content.encode("utf-8")
    document_started = False
    try:
        if not winspool.StartDocPrinterW(handle, 1, ctypes.byref(doc)):
            raise OSError(ctypes.get_last_error(), "Falha ao iniciar o documento.")
        document_started = True
        if not winspool.StartPagePrinter(handle):
            raise OSError(ctypes.get_last_error(), "Falha ao iniciar a página.")
        offset = 0
        while offset < len(payload):
            chunk = payload[offset:offset + 65536]
            written = ctypes.c_ulong()
            if not winspool.WritePrinter(handle, chunk, len(chunk), ctypes.byref(written)):
                raise OSError(ctypes.get_last_error(), "Falha ao enviar os dados RAW.")
            if not 0 < written.value <= len(chunk):
                raise OSError("O Windows não confirmou o recebimento dos dados da etiqueta.")
            offset += written.value
        if not winspool.EndPagePrinter(handle):
            raise OSError(ctypes.get_last_error(), "Falha ao finalizar a página de impressão.")
        if not winspool.EndDocPrinter(handle):
            raise OSError(ctypes.get_last_error(), "Falha ao concluir o envio para a fila de impressão.")
        document_started = False
    finally:
        if document_started:
            winspool.AbortPrinter(handle)
        winspool.ClosePrinter(handle)
    return printer
