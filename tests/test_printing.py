import ctypes
import unittest
from unittest.mock import MagicMock, patch
from services.impressao import raw_print, resolve_printer


class PrintTransportTests(unittest.TestCase):
    def send(self, spool):
        with patch("services.impressao.resolve_printer", return_value="Zebra"), patch("services.impressao.ctypes.WinDLL", return_value=spool):
            return raw_print("Zebra", "^XA^FDTESTE^FS^XZ")

    def spool(self):
        spool = MagicMock()
        for name in ("OpenPrinterW", "StartDocPrinterW", "StartPagePrinter", "EndPagePrinter", "EndDocPrinter"):
            getattr(spool, name).return_value = 1
        def write(handle, data, size, written):
            written._obj.value = size
            return 1
        spool.WritePrinter.side_effect = write
        return spool

    def test_partial_writes_send_only_remaining_bytes(self):
        spool = self.spool()
        received = bytearray()
        def write(handle, data, size, written):
            count = min(3, size)
            received.extend(data[:count])
            written._obj.value = count
            return 1
        spool.WritePrinter.side_effect = write
        self.assertEqual(self.send(spool), "Zebra")
        self.assertEqual(received, b"^XA^FDTESTE^FS^XZ")
        spool.EndDocPrinter.assert_called_once()
        spool.AbortPrinter.assert_not_called()
        spool.ClosePrinter.assert_called_once()

    def test_finalization_failure_aborts_and_reports_error(self):
        for stage in ("StartPagePrinter", "EndPagePrinter", "EndDocPrinter"):
            with self.subTest(stage=stage):
                spool = self.spool()
                getattr(spool, stage).return_value = 0
                with self.assertRaises(OSError):
                    self.send(spool)
                spool.AbortPrinter.assert_called_once()
                spool.ClosePrinter.assert_called_once()

    def test_zero_byte_write_aborts_without_looping(self):
        spool = self.spool()
        spool.WritePrinter.side_effect = lambda *args: 1
        with self.assertRaises(OSError):
            self.send(spool)
        spool.WritePrinter.assert_called_once()
        spool.AbortPrinter.assert_called_once()

    def test_missing_selected_printer_does_not_redirect_job(self):
        with patch("services.impressao.installed_printers", return_value=["Zebra outra"]), patch("services.impressao._printer_can_open", return_value=False):
            with self.assertRaises(RuntimeError):
                resolve_printer("Zebra selecionada")
